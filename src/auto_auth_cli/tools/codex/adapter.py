from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
import os
from pathlib import Path
from typing import Any

from auto_auth_cli.metadata import AuthMetadata
from auto_auth_cli.store import Profile
from auto_auth_cli.tools.base import QuotaStatus
from auto_auth_cli.tools.codex.auth import extract_metadata
from auto_auth_cli.tools.codex.plans import plan_priority
from auto_auth_cli.tools.codex.rate_limits import (
    profile_has_available_quota,
    read_profile_quota_status,
)


class CodexAdapter:
    name = "codex"
    executable = "codex"

    def default_auth_home(self) -> Path:
        return Path.home() / ".codex"

    def active_auth_path(self, auth_home: Path) -> Path:
        return auth_home / "auth.json"

    def setup_env(self, temp_home: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(temp_home)
        env["AUTO_AUTH_CODEX_WRAPPER_ACTIVE"] = "1"
        env["CMUX_CODEX_AUTO_AUTH_DISABLED"] = "1"
        return env

    def login_command(self, executable_path: str) -> list[str]:
        return [executable_path, "login"]

    def extract_metadata(self, auth_json: dict[str, Any]) -> AuthMetadata:
        return extract_metadata(auth_json)

    def sort_profiles_for_auto(self, profiles: list[Profile]) -> list[Profile]:
        return sorted(
            profiles,
            key=lambda profile: (
                plan_priority(profile.metadata.plan_type),
                profile.metadata.label.lower(),
            ),
        )

    def select_usable_profile(
        self, profiles: list[Profile], executable_path: str
    ) -> Profile | None:
        for profile in profiles:
            try:
                has_available_quota = profile_has_available_quota(
                    profile, executable_path
                )
            except (OSError, RuntimeError):
                has_available_quota = False
            if has_available_quota:
                return profile
        return None

    def profile_quota_statuses(
        self, profiles: list[Profile], executable_path: str
    ) -> dict[str, QuotaStatus]:
        if not profiles:
            return {}

        max_workers = min(len(profiles), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            quota_statuses = executor.map(
                read_profile_quota_status, profiles, repeat(executable_path)
            )
            return {
                profile.metadata.key: status
                for profile, status in zip(profiles, quota_statuses, strict=True)
            }
