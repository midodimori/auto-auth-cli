from pathlib import Path

import pytest

from auto_auth_cli.metadata import AuthMetadata
from auto_auth_cli.paths import ToolPaths
from auto_auth_cli.store import ProfileStore


def metadata(key: str, label: str, account_id: str) -> AuthMetadata:
    return AuthMetadata(
        key=key,
        label=label,
        email=label if "@" in label else None,
        account_id=account_id,
        plan_type="pro",
    )


def test_resolve_profile_rejects_ambiguous_prefix(tmp_path: Path):
    store = ProfileStore(
        ToolPaths(
            tool_name="codex",
            auto_auth_home=tmp_path / "auto" / "codex",
            auth_home=tmp_path / "codex",
            active_auth_path=tmp_path / "codex" / "auth.json",
        )
    )
    store.save_profile(metadata("minh_work_example_com", "minh.work@example.com", "account-1"), {})
    store.save_profile(metadata("minh_home_example_com", "minh.home@example.com", "account-2"), {})

    with pytest.raises(ValueError, match="ambiguous"):
        store.resolve_profile("minh")
