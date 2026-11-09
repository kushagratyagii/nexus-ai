
import asyncio
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


async def main():

    server_path = Path("app/mcp/server.py").resolve()

    client = MultiServerMCPClient(
        {
            "nexus": {
                "command": sys.executable,
                "args": [str(server_path)],
                "transport": "stdio"
            }
        }
    )

    tools = await client.get_tools()

    print("\nMCP SERVER CONNECTED!")
    print("\nDISCOVERED TOOLS:")

    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    word_tool = next(
        tool for tool in tools
        if tool.name.endswith("word_count")
    )

    result = await word_tool.ainvoke(
        {"text": "NEXUS AI is an intelligent agentic chatbot"}
    )

    print("\nWORD COUNT TEST:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
