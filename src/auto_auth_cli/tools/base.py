from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from auto_auth_cli.metadata import AuthMetadata
from auto_auth_cli.store import Profile


class ToolAdapter(Protocol):
    name: str
    executable: str

    def default_auth_home(self) -> Path: ...

    def active_auth_path(self, auth_home: Path) -> Path: ...

    def setup_env(self, temp_home: Path) -> dict[str, str]: ...

    def login_command(self, executable_path: str) -> list[str]: ...

    def extract_metadata(self, auth_json: dict[str, Any]) -> AuthMetadata: ...

    def sort_profiles_for_auto(self, profiles: list[Profile]) -> list[Profile]: ...
