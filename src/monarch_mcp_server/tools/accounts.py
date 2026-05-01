"""Account management tools."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from monarch_mcp_server.app import mcp
from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.helpers import json_success, json_error, get_account_owner_map

logger = logging.getLogger(__name__)


@mcp.tool()
async def get_accounts() -> str:
    """Get all financial accounts from Monarch Money."""
    try:
        client = await get_monarch_client()
        accounts, owner_map = await asyncio.gather(
            client.get_accounts(),
            get_account_owner_map(client),
        )

        account_list = []
        for account in accounts.get("accounts", []):
            acct_id = account.get("id")
            institution = account.get("institution") or {}
            credential = account.get("credential") or {}
            cred_institution = credential.get("institution") or {}
            account_info = {
                "id": acct_id,
                "name": account.get("displayName"),
                "mask": account.get("mask"),
                "type": (account.get("type") or {}).get("name"),
                "type_display": (account.get("type") or {}).get("display"),
                "subtype": (account.get("subtype") or {}).get("name"),
                "subtype_display": (account.get("subtype") or {}).get("display"),
                "balance": account.get("currentBalance"),
                "display_balance": account.get("displayBalance"),
                "is_asset": account.get("isAsset"),
                "include_in_net_worth": account.get("includeInNetWorth"),
                "include_balance_in_net_worth": account.get("includeBalanceInNetWorth"),
                "include_in_goal_balance": account.get("includeInGoalBalance"),
                "hide_transactions_from_reports": account.get("hideTransactionsFromReports"),
                "institution": institution.get("name"),
                "institution_url": institution.get("url"),
                "institution_color": institution.get("primaryColor"),
                "institution_status": cred_institution.get("status"),
                "data_provider": account.get("dataProvider"),
                "is_manual": account.get("isManual"),
                "sync_disabled": account.get("syncDisabled"),
                "connection_update_required": credential.get("updateRequired"),
                "disconnected_at": credential.get("disconnectedFromDataProviderAt"),
                "transactions_count": account.get("transactionsCount"),
                "holdings_count": account.get("holdingsCount"),
                "logo_url": account.get("logoUrl"),
                "owner": owner_map.get(acct_id),
                "is_active": not account.get("deactivatedAt"),
                "is_hidden": account.get("isHidden", False),
                "hide_from_list": account.get("hideFromList"),
                "created_at": account.get("createdAt"),
                "updated_at": account.get("updatedAt"),
                "last_synced_at": account.get("displayLastUpdatedAt"),
            }
            account_list.append(account_info)

        return json_success(account_list)
    except Exception as e:
        return json_error("get_accounts", e)


@mcp.tool()
async def refresh_accounts() -> str:
    """Request account data refresh from financial institutions."""
    try:
        client = await get_monarch_client()
        result = await client.request_accounts_refresh()
        return json_success(result)
    except Exception as e:
        return json_error("refresh_accounts", e)


@mcp.tool()
async def get_account_holdings(account_id: str) -> str:
    """
    Get investment holdings for a specific account.

    Args:
        account_id: The ID of the investment account
    """
    try:
        client = await get_monarch_client()
        holdings = await client.get_account_holdings(account_id)
        return json_success(holdings)
    except Exception as e:
        return json_error("get_account_holdings", e)


@mcp.tool()
async def get_account_balance_history(account_id: str) -> str:
    """
    Get historical balance data for a specific account.

    Returns all historical balance snapshots for tracking account growth over time.

    Args:
        account_id: The ID of the account (use get_accounts to find IDs)

    Returns:
        Historical balance snapshots for the account.

    Examples:
        Track savings account growth:
            get_account_balance_history(account_id="acc_123")
    """
    try:
        client = await get_monarch_client()
        snapshots = await client.get_account_history(account_id=int(account_id))

        formatted = {
            "account_id": account_id,
            "snapshot_count": len(snapshots),
            "snapshots": []
        }

        if snapshots:
            balances = [s.get("signedBalance", 0) for s in snapshots if s.get("signedBalance") is not None]
            if balances:
                formatted["current_balance"] = balances[-1] if balances else 0
                formatted["earliest_balance"] = balances[0] if balances else 0
                formatted["change"] = balances[-1] - balances[0] if len(balances) > 1 else 0
                formatted["highest"] = max(balances)
                formatted["lowest"] = min(balances)

        for snapshot in snapshots:
            formatted["snapshots"].append({
                "date": snapshot.get("date"),
                "balance": snapshot.get("signedBalance"),
            })

        return json_success(formatted)
    except Exception as e:
        return json_error("get_account_balance_history", e)


@mcp.tool()
async def upload_account_balance_history(account_id: str, corrections: str) -> str:
    """
    Upload corrected balance snapshots for an account.

    Fetches the full existing balance history, applies the corrections,
    and re-uploads the complete history.

    Args:
        account_id: The ID of the account to correct
        corrections: JSON object mapping dates to corrected balances,
                     e.g. '{"2026-04-23": 24846.45, "2026-04-24": 24846.45}'
    """
    try:
        from monarchmoney.monarchmoney import BalanceHistoryRow

        date_to_balance = json.loads(corrections)

        client = await get_monarch_client()
        snapshots = await client.get_account_history(account_id=int(account_id))

        applied = []
        rows = []
        for snapshot in snapshots:
            date_str = snapshot.get("date")
            balance = snapshot.get("signedBalance", 0)
            account_name = snapshot.get("accountName", "")

            if date_str in date_to_balance:
                balance = date_to_balance[date_str]
                applied.append(date_str)

            rows.append(BalanceHistoryRow(
                date=datetime.strptime(date_str, "%Y-%m-%d"),
                amount=balance,
                account_name=account_name,
            ))

        if not applied:
            return json_success({"updated": False, "message": "No matching dates found in history"})

        result = await client.upload_account_balance_history(
            account_id=account_id,
            csv_content=rows,
        )

        return json_success({
            "updated": result,
            "dates_corrected": applied,
            "total_snapshots": len(rows),
        })
    except Exception as e:
        return json_error("upload_account_balance_history", e)
