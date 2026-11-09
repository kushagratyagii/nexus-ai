from mcp.server.fastmcp import FastMCP
from datetime import datetime

mcp = FastMCP("NEXUS Utility Server")


@mcp.tool()
def get_current_datetime() -> str:
    """Get the current date and time."""

    return datetime.now().astimezone().isoformat()


@mcp.tool()
def word_count(text: str) -> str:
    """Count the number of words in the supplied text."""

    count = len(text.split())

    return f"The text contains {count} words."


@mcp.tool()
def calculate_percentage(value: float, percentage: float) -> str:
    """Calculate a percentage of a given value."""

    result = value * percentage / 100

    return f"{percentage}% of {value} is {result}."


if __name__ == "__main__":
    mcp.run(transport="stdio")
