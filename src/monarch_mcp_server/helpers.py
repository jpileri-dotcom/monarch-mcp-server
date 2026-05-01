"""Shared helpers for Monarch MCP Server tools."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from gql import gql

logger = logging.getLogger(__name__)

# Path to the joint-accounts config, relative to this file's package root
_JOINT_CONFIG = Path(__file__).parent.parent.parent / "joint_accounts.json"


def _load_joint_ids() -> set:
    """Load the set of account IDs that should be shown as 'Joint'."""
    try:
        data = json.loads(_JOINT_CONFIG.read_text())
        return set(data.get("joint_account_ids", []))
    except Exception:
        return set()


async def get_account_owner_map(client: Any) -> Dict[str, str]:
    """Return a mapping of account_id -> owner display name.

    Accounts listed in joint_accounts.json are mapped to 'Joint'.
    Accounts with a credential are mapped to that credential's user display name.
    Manual accounts with no credential and not in the joint list are omitted.
    """
    query = gql("""
    query GetAccountsOwner {
      accounts {
        id
        credential {
          user {
            id
            displayName
            name
          }
        }
      }
    }
    """)
    joint_ids = _load_joint_ids()
    try:
        result = await client.gql_call(
            operation="GetAccountsOwner", graphql_query=query
        )
        owner_map: Dict[str, str] = {}
        for acct in result.get("accounts", []):
            acct_id = acct.get("id")
            if not acct_id:
                continue
            if acct_id in joint_ids:
                owner_map[acct_id] = "Joint"
            else:
                credential = acct.get("credential") or {}
                user = credential.get("user") or {}
                owner = user.get("displayName") or user.get("name")
                if owner:
                    owner_map[acct_id] = owner
        return owner_map
    except Exception as exc:
        logger.warning("Could not fetch account owner map: %s", exc)
        return {}


def format_transaction(
    txn: Dict[str, Any],
    extended: bool = False,
    account_owner_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Format a raw Monarch transaction dict into a consistent output format.

    Args:
        txn: Raw transaction dict from the Monarch API.
        extended: If True, include extra fields like is_split, is_recurring,
                  has_attachments.
    """
    account = txn.get("account") or {}
    account_id = account.get("id")
    owner = (account_owner_map or {}).get(account_id) if account_id else None
    merchant = txn.get("merchant") or {}
    category = txn.get("category") or {}

    info: Dict[str, Any] = {
        "id": txn.get("id"),
        "date": txn.get("date"),
        "amount": txn.get("amount"),
        "merchant": merchant.get("name"),
        "merchant_id": merchant.get("id"),
        "original_name": txn.get("plaidName") or txn.get("originalName"),
        "category": category.get("name"),
        "category_id": category.get("id"),
        "account": account.get("displayName"),
        "account_id": account_id,
        "owner": owner,
        "notes": txn.get("notes"),
        "needs_review": txn.get("needsReview", False),
        "review_status": txn.get("reviewStatus"),
        "is_pending": txn.get("pending", False),
        "is_recurring": txn.get("isRecurring", False),
        "is_split": txn.get("isSplitTransaction", False),
        "hide_from_reports": txn.get("hideFromReports", False),
        "has_attachments": bool(txn.get("attachments")),
        "tags": [
            {"id": tag.get("id"), "name": tag.get("name"), "color": tag.get("color")}
            for tag in (txn.get("tags") or [])
        ],
        "created_at": txn.get("createdAt"),
        "updated_at": txn.get("updatedAt"),
    }

    if extended:
        info["attachments"] = [
            {
                "id": a.get("id"),
                "filename": a.get("filename"),
                "extension": a.get("extension"),
                "url": a.get("originalAssetUrl"),
                "size_bytes": a.get("sizeBytes"),
            }
            for a in (txn.get("attachments") or [])
        ]

    return info


def json_success(data: Any) -> str:
    """Serialize *data* to a JSON string for tool responses."""
    return json.dumps(data, indent=2, default=str)


def json_error(tool_name: str, exc: Exception) -> str:
    """Return a consistent JSON error string and log the failure."""
    logger.error(f"Failed in {tool_name}: {exc}")
    return json.dumps(
        {"error": True, "tool": tool_name, "message": str(exc)},
        indent=2,
        default=str,
    )
