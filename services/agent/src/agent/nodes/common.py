"""Helpers shared by stage nodes."""

from typing import Any

from contracts.actions import ToolResult, UpdateDeclaredDataInput

DECLARABLE = set(UpdateDeclaredDataInput.model_fields)

REJECTION_ES = {
    "owner_mismatch": "el auto no está a tu nombre, y para usarlo como garantía tiene que estarlo",
    "lien_or_debt": "el auto tiene un adeudo o gravamen, y para usarlo como garantía tiene que estar libre",
    "no_offer_for_profile": "con tu perfil actual no tenemos una oferta disponible",
    "advisor_rejected": "un asesor revisó tu caso y no es posible continuar",
}


def declared_updates(fields: dict[str, Any]) -> dict[str, Any]:
    """Confirmed fields the client gave in this message that update_declared_data accepts."""
    data = {k: v for k, v in fields.items() if k in DECLARABLE and v is not None}
    if "income_amount" in data:
        data["income_amount"] = str(data["income_amount"])
    return data


def merge(state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    return {**state, **updates}


def rejection_facts(result: ToolResult) -> dict[str, Any]:
    reason = result.result.get("reason")
    return {"reason_es": REJECTION_ES.get(reason, reason)} if reason else {}
