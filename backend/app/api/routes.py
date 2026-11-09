
import json
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    UploadFile,
    File,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.core.config import MODEL_NAME
from app.rag.ingestion import ingest_pdf

from app.db.conversations import (
    create_conversation,
    list_conversations,
    get_conversation,
    rename_conversation,
    update_conversation_time,
    delete_conversation,
)


router = APIRouter(prefix="/api", tags=["Chat"])


# ==========================================
# REQUEST / RESPONSE MODELS
# ==========================================

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    model: str
    thread_id: str
    status: str = "completed"
    interrupt: dict | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str


class CreateConversationRequest(BaseModel):
    title: str = "New conversation"


class RenameConversationRequest(BaseModel):
    title: str


# ==========================================
# NORMAL CHAT ENDPOINT
# ==========================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):

    try:
        graph = http_request.app.state.graph

        config = {
            "configurable": {
                "thread_id": request.thread_id
            }
        }

        result = await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(content=request.message)
                ]
            },
            config=config,
        )

        conversation = await get_conversation(request.thread_id)

        if not conversation:
            await create_conversation(
                request.thread_id,
                request.message[:40] or "New conversation",
            )
        else:
            await update_conversation_time(request.thread_id)

        interrupts = result.get("__interrupt__", [])

        if interrupts:
            return ChatResponse(
                response="This action requires your approval.",
                model=MODEL_NAME,
                thread_id=request.thread_id,
                status="approval_required",
                interrupt=interrupts[0].value,
            )

        answer = result["messages"][-1].content

        return ChatResponse(
            response=answer,
            model=MODEL_NAME,
            thread_id=request.thread_id,
            status="completed",
        )

    except Exception as e:
        print(f"Agent error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Agent execution failed.",
        )


# ==========================================
# RESUME CHAT AFTER HUMAN APPROVAL
# ==========================================

@router.post("/chat/resume", response_model=ChatResponse)
async def resume_chat(
    request: ResumeRequest,
    http_request: Request,
):

    if request.decision not in ["approve", "reject"]:
        raise HTTPException(
            status_code=400,
            detail="Decision must be approve or reject.",
        )

    try:
        graph = http_request.app.state.graph

        config = {
            "configurable": {
                "thread_id": request.thread_id
            }
        }

        result = await graph.ainvoke(
            Command(resume=request.decision),
            config=config,
        )

        await update_conversation_time(request.thread_id)

        interrupts = result.get("__interrupt__", [])

        if interrupts:
            return ChatResponse(
                response="Another approval is required.",
                model=MODEL_NAME,
                thread_id=request.thread_id,
                status="approval_required",
                interrupt=interrupts[0].value,
            )

        answer = result["messages"][-1].content

        return ChatResponse(
            response=answer,
            model=MODEL_NAME,
            thread_id=request.thread_id,
            status="completed",
        )

    except Exception as e:
        print(f"Resume error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to resume agent execution.",
        )


# ==========================================
# STREAMING CHAT ENDPOINT (SSE)
# Supports normal streaming + HITL interrupts
# ==========================================

@router.post("/chat/stream")
async def stream_chat(
    request: ChatRequest,
    http_request: Request,
):

    graph = http_request.app.state.graph

    config = {
        "configurable": {
            "thread_id": request.thread_id
        }
    }

    async def event_generator():

        try:
            # Stream LangGraph events
            async for event in graph.astream_events(
                {
                    "messages": [
                        HumanMessage(content=request.message)
                    ]
                },
                config=config,
                version="v2",
            ):

                if (
                    event["event"] == "on_chat_model_stream"
                    and event.get("metadata", {}).get("langgraph_node") == "chatbot"
                ):

                    chunk = event["data"]["chunk"]
                    content = chunk.content

                    if isinstance(content, str):
                        token = content

                    elif isinstance(content, list):
                        token = "".join(
                            block.get("text", "")
                            for block in content
                            if isinstance(block, dict)
                            and block.get("type") == "text"
                        )

                    else:
                        token = ""

                    if token:
                        yield (
                            f"data: {json.dumps({
                                'type': 'token',
                                'content': token
                            })}\n\n"
                        )

            # Check graph state after execution.
            # An interrupt is stored in the checkpoint.
            snapshot = await graph.aget_state(config)

            pending_interrupts = []

            if snapshot and snapshot.tasks:
                for task in snapshot.tasks:
                    for interrupt in task.interrupts:
                        pending_interrupts.append(interrupt.value)

            # Update conversation metadata
            conversation = await get_conversation(request.thread_id)

            if conversation:
                await update_conversation_time(request.thread_id)

            else:
                await create_conversation(
                    request.thread_id,
                    request.message[:40] or "New conversation",
                )

            # If LangGraph paused for approval, notify frontend.
            if pending_interrupts:

                yield (
                    f"data: {json.dumps({
                        'type': 'approval_required',
                        'interrupt': pending_interrupts[0]
                    })}\n\n"
                )

            else:

                yield (
                    f"data: {json.dumps({
                        'type': 'done',
                        'thread_id': request.thread_id,
                        'model': MODEL_NAME
                    })}\n\n"
                )

        except Exception as e:

            print(f"Streaming error: {e}")

            yield (
                f"data: {json.dumps({
                    'type': 'error',
                    'message': 'Response generation failed.'
                })}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==========================================
# PDF UPLOAD / RAG
# ==========================================

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


@router.post("/rag/upload")
async def upload_document(file: UploadFile = File(...)):

    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    original_filename = Path(file.filename).name
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Maximum PDF upload size is 20 MB.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"

    try:
        file_path.write_bytes(content)

        result = await run_in_threadpool(
            ingest_pdf,
            str(file_path),
            original_filename,
        )

        return {
            "message": "Document successfully indexed.",
            **result,
        }

    except Exception as e:
        file_path.unlink(missing_ok=True)

        print(f"Document ingestion error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed. Check backend logs.",
        )

    finally:
        await file.close()


# ==========================================
# CREATE CONVERSATION
# ==========================================

@router.post("/conversations")
async def create_new_conversation(
    request: CreateConversationRequest,
):

    try:
        thread_id = str(uuid.uuid4())

        conversation = await create_conversation(
            thread_id=thread_id,
            title=request.title,
        )

        return {
            "message": "Conversation created successfully.",
            "conversation": conversation,
        }

    except Exception as e:
        print(f"Create conversation error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to create conversation.",
        )


# ==========================================
# LIST CONVERSATIONS
# ==========================================

@router.get("/conversations")
async def get_all_conversations():

    try:
        conversations = await list_conversations()

        return {
            "conversations": conversations,
            "total": len(conversations),
        }

    except Exception as e:
        print(f"List conversations error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch conversations.",
        )


# ==========================================
# GET CONVERSATION HISTORY
# ==========================================

@router.get("/conversations/{thread_id}")
async def get_conversation_history(
    thread_id: str,
    http_request: Request,
):

    try:
        conversation = await get_conversation(thread_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        graph = http_request.app.state.graph

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        state = await graph.aget_state(config)

        messages = []

        if state and state.values:
            for message in state.values.get("messages", []):

                messages.append({
                    "type": message.type,
                    "content": message.content,
                    "tool_calls": getattr(
                        message,
                        "tool_calls",
                        [],
                    ),
                })

        return {
            "conversation": conversation,
            "messages": messages,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Conversation history error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch conversation history.",
        )


# ==========================================
# RENAME CONVERSATION
# ==========================================

@router.patch("/conversations/{thread_id}")
async def update_conversation(
    thread_id: str,
    request: RenameConversationRequest,
):

    try:
        title = request.title.strip()

        if not title:
            raise HTTPException(
                status_code=400,
                detail="Conversation title cannot be empty.",
            )

        updated = await rename_conversation(
            thread_id,
            title,
        )

        if not updated:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        conversation = await get_conversation(thread_id)

        return {
            "message": "Conversation renamed successfully.",
            "conversation": conversation,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Rename conversation error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to rename conversation.",
        )


# ==========================================
# DELETE CONVERSATION
# ==========================================

@router.delete("/conversations/{thread_id}")
async def remove_conversation(
    thread_id: str,
    http_request: Request,
):

    try:
        conversation = await get_conversation(thread_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        # Delete LangGraph checkpoint
        checkpointer = http_request.app.state.checkpointer

        await checkpointer.adelete_thread(thread_id)

        # Delete conversation metadata
        await delete_conversation(thread_id)

        return {
            "message": "Conversation and its agent memory deleted successfully.",
            "thread_id": thread_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Delete conversation error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to delete conversation.",
        )
