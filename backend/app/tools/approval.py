
from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def protected_action(action: str, details: str) -> str:
    """
    Perform a sensitive operation only after explicit human approval.

    Use this tool whenever an operation requires user permission.
    """

    approval = interrupt({
        "type": "human_approval",
        "action": action,
        "details": details,
        "message": "This action requires human approval."
    })

    if approval == "approve":
        # Simulated execution
        return (
            f"Action approved and executed successfully: {action}. "
            f"Details: {details}"
        )

    return f"Action rejected by user: {action}"
