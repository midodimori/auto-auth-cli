import json
from io import StringIO
from pathlib import Path

from auto_auth_cli.metadata import AuthMetadata
from auto_auth_cli.store import Profile
from auto_auth_cli.tools.base import QuotaStatus
from auto_auth_cli.tools.codex.rate_limits import (
    read_account_rate_limits,
    read_profile_quota_status,
)


def test_read_profile_quota_status_maps_auth_errors(tmp_path: Path, monkeypatch):
    profile = Profile(
        metadata=AuthMetadata(
            key="limited",
            label="limited@example.com",
            email="limited@example.com",
            account_id="acct-limited",
            plan_type="pro",
        ),
        auth_path=tmp_path / "auth.json",
    )

    def fake_read_profile_rate_limits(profile, executable):
        raise RuntimeError("401 Unauthorized code=token_revoked")

    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.rate_limits.read_profile_rate_limits",
        fake_read_profile_rate_limits,
    )

    assert read_profile_quota_status(profile, "/bin/codex") == QuotaStatus(
        primary="token revoked",
        secondary="token revoked",
    )


def test_rate_limit_probe_disables_auto_auth_wrapper(tmp_path: Path, monkeypatch):
    captured = {}

    class FakeProcess:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            self.stdin = StringIO()
            self.stdout = StringIO(
                json.dumps({"id": 1, "result": {}})
                + "\n"
                + json.dumps({"id": 2, "result": {"rateLimits": {}}})
                + "\n"
            )

        def terminate(self):
            pass

        def wait(self, timeout):
            return 0

    monkeypatch.setattr("subprocess.Popen", FakeProcess)

    assert read_account_rate_limits("/wrapped/codex", tmp_path) == {"rateLimits": {}}

    assert captured["command"] == [
        "/wrapped/codex",
        "app-server",
        "--listen",
        "stdio://",
    ]
    assert captured["env"]["CODEX_HOME"] == str(tmp_path)
    assert captured["env"]["AUTO_AUTH_CODEX_WRAPPER_ACTIVE"] == "1"
    assert captured["env"]["CMUX_CODEX_AUTO_AUTH_DISABLED"] == "1"
