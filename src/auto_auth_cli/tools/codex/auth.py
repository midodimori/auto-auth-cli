from __future__ import annotations

from typing import Any

from auto_auth_cli.jwt import decode_jwt_payload
from auto_auth_cli.metadata import AuthMetadata, sanitize_profile_key

AUTH_CLAIMS_KEY = "https://api.openai.com/auth"


def extract_metadata(auth_json: dict[str, Any]) -> AuthMetadata:
    tokens = auth_json.get("tokens")
    if not isinstance(tokens, dict):
        tokens = {}

    payloads: list[dict[str, Any]] = []
    for token_name in ("id_token", "access_token"):
        token = tokens.get(token_name)
        if isinstance(token, str):
            payloads.append(decode_jwt_payload(token))

    email = _first_string(payloads, "email")
    account_id = _first_chatgpt_claim(payloads, "chatgpt_account_id")
    plan_type = _first_chatgpt_claim(payloads, "chatgpt_plan_type")
    label = email or account_id or "unknown"

    return AuthMetadata(
        key=sanitize_profile_key(label),
        label=label,
        email=email,
        account_id=account_id,
        plan_type=plan_type,
    )


def _first_string(payloads: list[dict[str, Any]], key: str) -> str | None:
    for payload in payloads:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_chatgpt_claim(payloads: list[dict[str, Any]], key: str) -> str | None:
    for payload in payloads:
        claims = payload.get(AUTH_CLAIMS_KEY)
        if isinstance(claims, dict):
            value = claims.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
