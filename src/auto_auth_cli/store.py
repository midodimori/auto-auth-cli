from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from auto_auth_cli.metadata import AuthMetadata
from auto_auth_cli.paths import ToolPaths


@dataclass(frozen=True)
class Profile:
    metadata: AuthMetadata
    auth_path: Path


class ProfileStore:
    def __init__(self, paths: ToolPaths):
        self.paths = paths

    def save_profile(self, metadata: AuthMetadata, auth_json: dict) -> Profile:
        profile_dir = self.paths.profiles_dir / metadata.key
        profile_dir.mkdir(parents=True, exist_ok=True)
        auth_path = profile_dir / "auth.json"
        metadata_path = profile_dir / "metadata.json"
        _write_json_atomic(auth_path, auth_json, mode=0o600)
        _write_json_atomic(metadata_path, asdict(metadata), mode=0o600)
        return Profile(metadata=metadata, auth_path=auth_path)

    def list_profiles(self) -> list[Profile]:
        if not self.paths.profiles_dir.exists():
            return []

        profiles: list[Profile] = []
        for metadata_path in sorted(self.paths.profiles_dir.glob("*/metadata.json")):
            try:
                raw = json.loads(metadata_path.read_text())
                metadata = AuthMetadata(**raw)
            except (OSError, TypeError, ValueError):
                continue
            profiles.append(
                Profile(metadata=metadata, auth_path=metadata_path.parent / "auth.json")
            )
        return profiles

    def resolve_profile(self, selector: str) -> Profile:
        selector_lower = selector.lower()
        prefix_matches: list[Profile] = []

        for profile in self.list_profiles():
            candidates = [
                profile.metadata.key,
                profile.metadata.label,
                profile.metadata.email or "",
                profile.metadata.account_id or "",
            ]
            lowered = [candidate.lower() for candidate in candidates if candidate]
            if selector_lower in lowered:
                return profile
            if any(candidate.startswith(selector_lower) for candidate in lowered):
                prefix_matches.append(profile)

        if len(prefix_matches) == 1:
            return prefix_matches[0]
        if len(prefix_matches) > 1:
            labels = ", ".join(profile.metadata.label for profile in prefix_matches)
            raise ValueError(f"profile selector {selector!r} is ambiguous: {labels}")
        raise ValueError(f"profile {selector!r} not found")

    def install_profile(self, selector: str) -> Profile:
        profile = self.resolve_profile(selector)
        self.paths.auth_home.mkdir(parents=True, exist_ok=True)
        self.paths.backups_dir.mkdir(parents=True, exist_ok=True)

        active_auth = self.paths.active_auth_path
        if active_auth.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = self.paths.backups_dir / f"auth.{timestamp}.json"
            shutil.copy2(active_auth, backup_path)
            _chmod_private(backup_path)

        tmp_path = active_auth.with_name("auth.json.tmp")
        shutil.copy2(profile.auth_path, tmp_path)
        _chmod_private(tmp_path)
        os.replace(tmp_path, active_auth)
        _chmod_private(active_auth)
        return profile


def _write_json_atomic(path: Path, data: dict, mode: int) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.chmod(tmp_path, mode)
    os.replace(tmp_path, path)


def _chmod_private(path: Path) -> None:
    if os.name == "posix":
        os.chmod(path, 0o600)
