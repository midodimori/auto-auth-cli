from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AuthMetadata:
    key: str
    label: str
    email: str | None
    account_id: str | None
    plan_type: str | None


def sanitize_profile_key(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return key or "profile"
