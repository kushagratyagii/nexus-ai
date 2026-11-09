
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from app.core.config import OPENAI_API_KEY, MODEL_NAME
from app.tools.basic import tools


def build_graph(checkpointer, mcp_tools):

    # 1. Combine native tools and MCP tools
    all_tools = tools + mcp_tools

    print("\nALL AVAILABLE AGENT TOOLS:")

    for tool in all_tools:
        print(f"- {tool.name}")

    # 2. Initialize LLM
    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        temperature=0
    )

    # 3. Bind all tools to LLM
    llm_with_tools = llm.bind_tools(all_tools)

    # 4. Define chatbot node
    async def chatbot(state: MessagesState):

        system_message = SystemMessage(
            content="""
            You are NEXUS AI, an intelligent AI assistant.

            You have access to native tools, RAG tools and MCP tools.

            NATIVE TOOLS:
            - multiply: Multiply numbers.
            - add: Add numbers.
            - search_knowledge_base: Search uploaded PDF documents.

            MCP TOOLS:
            - get_current_datetime: Get current date and time.
            - word_count: Count words in text.
            - calculate_percentage: Calculate a percentage.

            RULES:

            - Use mathematical tools when appropriate.
            - For uploaded document questions, use search_knowledge_base.
            - For date and time questions, use get_current_datetime.
            - For word counting, use word_count.
            - For percentage calculations, use calculate_percentage.
            - Base document-related answers on retrieved information.
            - Mention source filenames and page numbers when available.
            - Never fabricate information from uploaded documents.
            - Always explain tool results clearly.
            """

        )

        response = await llm_with_tools.ainvoke(
            [system_message] + state["messages"]
        )

        print("TOOL CALLS:", response.tool_calls)

        return {"messages": [response]}

    # 5. Build LangGraph
    builder = StateGraph(MessagesState)

    builder.add_node("chatbot", chatbot)

    builder.add_node(
        "tools",
        ToolNode(all_tools)
    )

    builder.add_edge(START, "chatbot")

    builder.add_conditional_edges(
        "chatbot",
        tools_condition
    )

    builder.add_edge("tools", "chatbot")

    # 6. Compile with persistent checkpointing
    graph = builder.compile(
        checkpointer=checkpointer
    )

    return graph
