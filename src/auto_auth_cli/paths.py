from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol


class ToolPathAdapter(Protocol):
    name: str

    def default_auth_home(self) -> Path: ...

    def active_auth_path(self, auth_home: Path) -> Path: ...


@dataclass(frozen=True)
class ToolPaths:
    tool_name: str
    auto_auth_home: Path
    auth_home: Path
    active_auth_path: Path

    @classmethod
    def from_env(cls, adapter: ToolPathAdapter) -> ToolPaths:
        home = Path.home()
        auto_auth_root = Path(os.environ.get("AUTO_AUTH_HOME", home / ".auto-auth"))
        auth_home = Path(
            os.environ.get(f"{adapter.name.upper()}_HOME", adapter.default_auth_home())
        )
        return cls(
            tool_name=adapter.name,
            auto_auth_home=auto_auth_root / adapter.name,
            auth_home=auth_home,
            active_auth_path=adapter.active_auth_path(auth_home),
        )

    @property
    def profiles_dir(self) -> Path:
        return self.auto_auth_home / "profiles"

    @property
    def backups_dir(self) -> Path:
        return self.auto_auth_home / "backups"


AutoAuthPaths = ToolPaths
