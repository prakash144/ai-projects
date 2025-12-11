"""
FastMCP quickstart - Leave Management example (in-memory)

Run from the repository root:
    uv run examples/snippets/servers/fastmcp_leave.py
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# ----------------------------
# In-memory mock database with 20 leave days to start
# ----------------------------
employee_leaves = {
    "E001": {"balance": 18, "history": ["2024-12-25", "2025-01-01"]},
    "E002": {"balance": 20, "history": []},
    "Prakash": {"balance": 20, "history": []}

}

# ----------------------------
# Logging setup
# ----------------------------
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("leave-mcp")

# Pretty emoji helpers (for responses)
SUCCESS = "✅"
INFO = "ℹ️"
WARNING = "⚠️"
ERROR = "❌"
SPARKLE = "✨"
CALENDAR = "📅"
PERSON = "👤"

# ----------------------------
# Create an MCP server
# ----------------------------
mcp = FastMCP("LeaveManager", json_response=True)


# ----------------------------
# Utility helpers (not exposed as tools directly)
# ----------------------------
def _employee_exists(emp_id: str) -> bool:
    return emp_id in employee_leaves


def _normalize_date(date_str: str) -> Optional[str]:
    """Try to normalize a date string (YYYY-MM-DD). Return normalized string or None."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


# ----------------------------
# Tools (MCP endpoints)
# ----------------------------

@mcp.tool()
def check_balance(employee_id: str) -> Dict[str, Any]:
    """
    Check the leave balance of an employee.
    Returns a dict with balance and message (with emojis).
    """
    logger.info("Checking balance for employee %s", employee_id)
    if not _employee_exists(employee_id):
        logger.warning("Employee %s not found", employee_id)
        return {
            "ok": False,
            "message": f"{ERROR} Employee {employee_id} not found.",
        }

    balance = employee_leaves[employee_id]["balance"]
    history = employee_leaves[employee_id]["history"]
    msg = f"{SUCCESS} {PERSON} *{employee_id}* has *{balance}* leave days remaining. {CALENDAR} Past leaves: {len(history)}"
    logger.info("Balance for %s: %d days", employee_id, balance)
    return {"ok": True, "employee_id": employee_id, "balance": balance, "history_count": len(history), "message": msg}


@mcp.tool()
def apply_leave(employee_id: str, date: str, days: int = 1, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply leave for an employee on a specific date for `days` days.
    Updates the in-memory DB and returns a friendly message with logs.
    """
    logger.info("Apply leave request: emp=%s date=%s days=%s reason=%s", employee_id, date, days, reason)
    norm_date = _normalize_date(date)
    if not norm_date:
        logger.error("Invalid date format provided: %s", date)
        return {"ok": False, "message": f"{ERROR} Invalid date format. Please use YYYY-MM-DD."}

    if days <= 0:
        logger.error("Invalid days value: %s", days)
        return {"ok": False, "message": f"{ERROR} Number of days must be >= 1."}

    if not _employee_exists(employee_id):
        logger.warning("Employee %s not found", employee_id)
        return {"ok": False, "message": f"{ERROR} Employee `{employee_id}` not found."}

    # simple availability check (assume history stores dates - if multi-day you'd expand)
    balance = employee_leaves[employee_id]["balance"]
    if days > balance:
        logger.warning("Insufficient balance for %s: requested=%d available=%d", employee_id, days, balance)
        return {
            "ok": False,
            "message": f"{WARNING} Not enough leave balance. Requested {days}, available {balance}.",
        }

    # record each day as a separate entry (for simplicity)
    # For multi-day leaves we append date + offset
    applied_dates = []
    try:
        base = datetime.strptime(norm_date, "%Y-%m-%d")
        for i in range(days):
            d = (base).strftime("%Y-%m-%d") if i == 0 else (base.replace(day=base.day + i)).strftime("%Y-%m-%d")
            # NOTE: naive increment above is simple — in production use timedelta
            # but keep behavior predictable for this quick example
            applied_dates.append(d)
    except Exception:
        # fallback: just add the normalized date once
        applied_dates = [norm_date]

    # Deduct balance and append to history
    employee_leaves[employee_id]["balance"] -= days
    employee_leaves[employee_id]["history"].extend(applied_dates)

    logger.info("Leave applied for %s on %s for %d day(s). New balance: %d",
                employee_id, norm_date, days, employee_leaves[employee_id]["balance"])

    reason_text = f" Reason: {reason}." if reason else ""
    message = (
        f"{SUCCESS} Leave applied for *{employee_id}* on {', '.join(applied_dates)} for {days} day(s)."
        f"{reason_text} {SPARKLE} New balance: {employee_leaves[employee_id]['balance']} day(s)."
    )

    return {
        "ok": True,
        "employee_id": employee_id,
        "applied_dates": applied_dates,
        "days": days,
        "new_balance": employee_leaves[employee_id]["balance"],
        "message": message,
    }


@mcp.tool()
def cancel_leave(employee_id: str, date: str) -> Dict[str, Any]:
    """
    Cancel a previously applied leave for an employee on given date.
    """
    logger.info("Cancel leave request: emp=%s date=%s", employee_id, date)
    norm_date = _normalize_date(date)
    if not norm_date:
        logger.error("Invalid date format for cancellation: %s", date)
        return {"ok": False, "message": f"{ERROR} Invalid date format. Use YYYY-MM-DD."}

    if not _employee_exists(employee_id):
        logger.warning("Employee %s not found for cancel", employee_id)
        return {"ok": False, "message": f"{ERROR} Employee `{employee_id}` not found."}

    history = employee_leaves[employee_id]["history"]
    if norm_date not in history:
        logger.warning("No leave found on %s for %s", norm_date, employee_id)
        return {"ok": False, "message": f"{WARNING} No leave found on {norm_date} for {employee_id}."}

    # remove the date (first occurrence) and refund 1 day
    history.remove(norm_date)
    employee_leaves[employee_id]["balance"] += 1

    logger.info("Cancelled leave for %s on %s. New balance: %d", employee_id, norm_date, employee_leaves[employee_id]["balance"])
    message = (
        f"{SUCCESS} Cancelled leave for *{employee_id}* on {norm_date}. "
        f"🪙 1 day refunded. New balance: {employee_leaves[employee_id]['balance']} day(s)."
    )

    return {"ok": True, "employee_id": employee_id, "cancelled_date": norm_date, "message": message}


@mcp.tool()
def leave_history(employee_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Return the leave history for an employee (most recent first).
    """
    logger.info("Fetching leave history for %s", employee_id)
    if not _employee_exists(employee_id):
        logger.warning("Employee %s not found for history", employee_id)
        return {"ok": False, "message": f"{ERROR} Employee `{employee_id}` not found."}

    history = list(reversed(employee_leaves[employee_id]["history"]))
    truncated = history[:limit]
    logger.info("History returned for %s - %d records (limit=%d)", employee_id, len(truncated), limit)

    msg = f"{INFO} Showing up to {limit} past leave entries for *{employee_id}* ({len(truncated)} items)."
    return {"ok": True, "employee_id": employee_id, "history": truncated, "message": msg}


@mcp.tool()
def admin_adjust_balance(admin_id: str, employee_id: str, delta: int, note: Optional[str] = None) -> Dict[str, Any]:
    """
    Admin tool to adjust leave balance (positive or negative).
    """
    logger.info("Admin %s adjusting balance for %s by %d (%s)", admin_id, employee_id, delta, note)
    if not _employee_exists(employee_id):
        logger.warning("Employee %s not found for admin adjust", employee_id)
        return {"ok": False, "message": f"{ERROR} Employee `{employee_id}` not found."}

    employee_leaves[employee_id]["balance"] += delta
    if employee_leaves[employee_id]["balance"] < 0:
        # Prevent negative balances in this example; bring to zero and log warning
        logger.warning("Balance would go negative for %s; setting to 0", employee_id)
        employee_leaves[employee_id]["balance"] = 0

    note_text = f" Note: {note}." if note else ""
    logger.info("Balance adjusted: %s new_balance=%d", employee_id, employee_leaves[employee_id]["balance"])
    message = (
        f"{SPARKLE} Admin `{admin_id}` adjusted balance for *{employee_id}* by {delta} days.{note_text} "
        f"New balance: {employee_leaves[employee_id]['balance']} day(s)."
    )

    return {"ok": True, "employee_id": employee_id, "new_balance": employee_leaves[employee_id]["balance"], "message": message}


# ----------------------------
# Resources (dynamic endpoints)
# ----------------------------
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting (small demo resource)."""
    logger.info("Greeting resource requested for %s", name)
    return f"Hello, {name}! {SPARKLE} Welcome to the Leave Management MCP."


# ----------------------------
# Prompts (templates) - could be used by LLM to craft responses
# ----------------------------
@mcp.prompt()
def leave_apply_prompt(employee_id: str, date: str, days: int = 1) -> str:
    """Generate a friendly leave application prompt for an LLM to expand or format."""
    return (
        f"Please create a short, friendly notification for employee `{employee_id}` stating that their leave "
        f"for {days} day(s) on {date} has been applied successfully. Use an emoji and one sentence."
    )


# ----------------------------
# Add a lightweight example tool: list all employees (for demo/admin)
# ----------------------------
@mcp.tool()
def list_employees() -> Dict[str, Any]:
    """Return a quick list of employees and basic balances."""
    logger.info("Listing employees")
    data = [{"employee_id": k, "balance": v["balance"], "history_count": len(v["history"])} for k, v in employee_leaves.items()]
    message = f"{INFO} {len(data)} employees found."
    return {"ok": True, "employees": data, "message": message}


# ----------------------------
# Run with streamable HTTP transport (or whichever transport FastMCP supports)
# ----------------------------
if __name__ == "__main__":
    logger.info("Starting LeaveManager MCP server... 🚀")
    # Use streamable-http as in the template; change transport if your environment differs
    mcp.run(transport="streamable-http")
