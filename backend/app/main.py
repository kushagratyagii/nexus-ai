
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.agents.graph import build_graph
from app.api.routes import router

from app.db.conversations import init_conversation_db

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "nexus_checkpoints.sqlite"
MCP_SERVER_PATH = BASE_DIR / "mcp" / "server.py"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_conversation_db()
    # 1. Initialize MCP client
    mcp_client = MultiServerMCPClient(
        {
            "nexus": {
                "command": sys.executable,
                "args": [str(MCP_SERVER_PATH)],
                "transport": "stdio"
            }
        }
    )

    # 2. Discover MCP tools
    mcp_tools = await mcp_client.get_tools()

    print("\nMCP TOOLS DISCOVERED:")

    for tool in mcp_tools:
        print(f"- {tool.name}")

    # 3. Initialize SQLite checkpointing
    async with AsyncSqliteSaver.from_conn_string(
        str(DB_PATH)
    ) as checkpointer:

        await checkpointer.setup()
        app.state.checkpointer = checkpointer
        # 4. Build graph with MCP tools
        app.state.graph = build_graph(
            checkpointer,
            mcp_tools
        )

        app.state.mcp_client = mcp_client

        print("\nNEXUS AI STARTED SUCCESSFULLY!")

        yield


app = FastAPI(
    title="NEXUS AI",
    description="Agentic AI Chatbot Platform",
    version="1.0.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router)


@app.get("/")
async def root():
    return {"message": "Welcome to NEXUS AI"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
