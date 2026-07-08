import base64
import json
from pathlib import Path

from auto_auth_cli.cli import run
from auto_auth_cli.tools.base import QuotaStatus


def jwt_for(payload: dict) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode())
        .rstrip(b"=")
        .decode()
    )
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}."


def write_saved_profile(root: Path) -> None:
    profile_dir = root / "auto" / "codex" / "profiles" / "minh_example_com"
    profile_dir.mkdir(parents=True)
    (profile_dir / "auth.json").write_text(
        json.dumps({"tokens": {"refresh_token": "new"}})
    )
    (profile_dir / "metadata.json").write_text(
        json.dumps(
            {
                "key": "minh_example_com",
                "label": "minh@example.com",
                "email": "minh@example.com",
                "account_id": "account-123",
                "plan_type": "pro",
            }
        )
    )


def write_named_profile(
    root: Path,
    key: str,
    label: str,
    refresh_token: str,
    account_id: str,
    plan_type: str = "pro",
    last_refresh: str | None = None,
) -> None:
    profile_dir = root / "auto" / "codex" / "profiles" / key
    profile_dir.mkdir(parents=True)
    auth_json: dict = {"tokens": {"refresh_token": refresh_token}}
    if last_refresh is not None:
        auth_json["last_refresh"] = last_refresh
    (profile_dir / "auth.json").write_text(json.dumps(auth_json))
    (profile_dir / "metadata.json").write_text(
        json.dumps(
            {
                "key": key,
                "label": label,
                "email": label,
                "account_id": account_id,
                "plan_type": plan_type,
            }
        )
    )


def write_active_profile(
    root: Path,
    email: str,
    account_id: str,
    plan_type: str = "pro",
    last_refresh: str | None = None,
) -> None:
    active_auth = root / "codex" / "auth.json"
    active_auth.parent.mkdir(parents=True)
    auth_json: dict = {
        "tokens": {
            "id_token": jwt_for(
                {
                    "email": email,
                    "https://api.openai.com/auth": {
                        "chatgpt_account_id": account_id,
                        "chatgpt_plan_type": plan_type,
                    },
                }
            )
        }
    }
    if last_refresh is not None:
        auth_json["last_refresh"] = last_refresh
    active_auth.write_text(json.dumps(auth_json))


def test_setup_logs_in_with_temp_codex_home_and_saves_profile(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )

    def fake_run(command, check, env):
        assert command == ["/bin/codex", "login"]
        assert check is True
        assert env["AUTO_AUTH_CODEX_WRAPPER_ACTIVE"] == "1"
        assert env["CMUX_CODEX_AUTO_AUTH_DISABLED"] == "1"
        temp_auth = Path(env["CODEX_HOME"]) / "auth.json"
        temp_auth.write_text(
            json.dumps(
                {
                    "tokens": {
                        "id_token": jwt_for(
                            {
                                "email": "minh@example.com",
                                "https://api.openai.com/auth": {
                                    "chatgpt_account_id": "account-123",
                                    "chatgpt_plan_type": "pro",
                                },
                            }
                        )
                    }
                }
            )
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    assert run(["codex", "--setup"]) == 0

    assert "Saved codex auth profile: minh@example.com" in capsys.readouterr().out
    assert (
        tmp_path / "auto" / "codex" / "profiles" / "minh_example_com" / "auth.json"
    ).exists()
    assert not (tmp_path / "codex" / "auth.json").exists()


def test_profile_switch_replaces_only_active_auth_then_execs_codex(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_saved_profile(tmp_path)
    active_auth = tmp_path / "codex" / "auth.json"
    active_auth.parent.mkdir()
    active_auth.write_text(json.dumps({"tokens": {"refresh_token": "old"}}))
    calls = []

    def fake_execvp(program, args):
        calls.append((program, args))
        raise SystemExit(0)

    monkeypatch.setattr("os.execvp", fake_execvp)

    assert run(["codex", "--profile", "minh", "--", "-m", "gpt-5.2"]) == 0

    assert json.loads(active_auth.read_text()) == {"tokens": {"refresh_token": "new"}}
    backups = list((tmp_path / "auto" / "codex" / "backups").glob("auth.*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == {"tokens": {"refresh_token": "old"}}
    assert calls == [("codex", ["codex", "-m", "gpt-5.2"])]


def test_profile_switch_syncs_current_active_auth_before_install(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path,
        "active_example_com",
        "active@example.com",
        "stale",
        "acct-active",
    )
    write_named_profile(
        tmp_path,
        "target_example_com",
        "target@example.com",
        "target",
        "acct-target",
    )
    write_active_profile(tmp_path, "active@example.com", "acct-active")

    def fake_execvp(program, args):
        raise SystemExit(0)

    monkeypatch.setattr("os.execvp", fake_execvp)

    assert run(["codex", "--profile", "target"]) == 0

    synced_auth = json.loads(
        (
            tmp_path
            / "auto"
            / "codex"
            / "profiles"
            / "active_example_com"
            / "auth.json"
        ).read_text()
    )
    assert "id_token" in synced_auth["tokens"]
    assert "refresh_token" not in synced_auth["tokens"]


def test_status_does_not_sync_older_active_auth_over_newer_saved_profile(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path,
        "active_example_com",
        "active@example.com",
        "fresh",
        "acct-active",
        last_refresh="2026-07-08T17:10:00Z",
    )
    write_active_profile(
        tmp_path,
        "active@example.com",
        "acct-active",
        last_refresh="2026-07-07T17:10:00Z",
    )
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )
    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.adapter.read_profile_quota_status",
        lambda profile, executable: QuotaStatus(
            primary="available", secondary="available"
        ),
    )

    assert run(["codex", "--status"]) == 0

    saved_auth = json.loads(
        (
            tmp_path
            / "auto"
            / "codex"
            / "profiles"
            / "active_example_com"
            / "auth.json"
        ).read_text()
    )
    assert saved_auth["tokens"]["refresh_token"] == "fresh"
    assert saved_auth["last_refresh"] == "2026-07-08T17:10:00Z"
    assert "active@example.com" in capsys.readouterr().out


def test_auto_uses_first_usable_profile_then_execs_codex(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path, "limited_example_com", "limited@example.com", "limited", "acct-1"
    )
    write_named_profile(
        tmp_path, "usable_example_com", "usable@example.com", "usable", "acct-2"
    )
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )
    calls = []

    def fake_select(self, profiles, executable):
        assert executable == "/bin/codex"
        assert [profile.metadata.email for profile in profiles] == [
            "limited@example.com",
            "usable@example.com",
        ]
        return profiles[1]

    def fake_execvp(program, args):
        calls.append((program, args))
        raise SystemExit(0)

    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.adapter.CodexAdapter.select_usable_profile",
        fake_select,
    )
    monkeypatch.setattr("os.execvp", fake_execvp)

    assert run(["codex", "--auto", "--", "-m", "gpt-5.2"]) == 0

    active_auth = tmp_path / "codex" / "auth.json"
    assert json.loads(active_auth.read_text()) == {
        "tokens": {"refresh_token": "usable"}
    }
    assert calls == [("codex", ["codex", "-m", "gpt-5.2"])]


def test_auto_syncs_active_profile_before_selecting(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path,
        "active_example_com",
        "active@example.com",
        "stale",
        "acct-active",
        last_refresh="2026-07-07T17:10:00Z",
    )
    write_active_profile(
        tmp_path,
        "active@example.com",
        "acct-active",
        last_refresh="2026-07-08T17:10:00Z",
    )
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )

    def fake_select(self, profiles, executable):
        saved_auth = json.loads(profiles[0].auth_path.read_text())
        assert "id_token" in saved_auth["tokens"]
        assert saved_auth["last_refresh"] == "2026-07-08T17:10:00Z"
        return profiles[0]

    def fake_execvp(program, args):
        raise SystemExit(0)

    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.adapter.CodexAdapter.select_usable_profile",
        fake_select,
    )
    monkeypatch.setattr("os.execvp", fake_execvp)

    assert run(["codex", "--auto"]) == 0


def test_auto_prioritizes_smaller_subscription_profiles(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path,
        "aaa_pro_example_com",
        "pro@example.com",
        "pro",
        "acct-pro",
        plan_type="pro",
    )
    write_named_profile(
        tmp_path,
        "zzz_plus_example_com",
        "plus@example.com",
        "plus",
        "acct-plus",
        plan_type="plus",
    )
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )
    seen_order = []

    def fake_select(self, profiles, executable):
        seen_order.extend(profile.metadata.email for profile in profiles)
        return profiles[0]

    def fake_execvp(program, args):
        raise SystemExit(0)

    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.adapter.CodexAdapter.select_usable_profile",
        fake_select,
    )
    monkeypatch.setattr("os.execvp", fake_execvp)

    assert run(["codex", "--auto"]) == 0

    assert seen_order == ["plus@example.com", "pro@example.com"]


def test_status_renders_profiles_with_quota_table(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path, "limited_example_com", "limited@example.com", "limited", "acct-1"
    )
    write_named_profile(
        tmp_path, "usable_example_com", "usable@example.com", "usable", "acct-2", "plus"
    )
    write_active_profile(tmp_path, "usable@example.com", "acct-2", "plus")
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )

    def fake_read_profile_quota_status(profile, executable):
        assert executable == "/bin/codex"
        if profile.metadata.key == "limited_example_com":
            return QuotaStatus(
                primary="100% used, limit reached",
                secondary="20% used",
            )
        return QuotaStatus(primary="30% used", secondary="available")

    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.adapter.read_profile_quota_status",
        fake_read_profile_quota_status,
    )

    assert run(["codex", "--status"]) == 0

    output = capsys.readouterr().out
    assert "Active: usable@example.com" in output
    assert "Profile" in output
    assert "Primary quota" in output
    assert "Secondary quota" in output
    assert "limited@example.com" in output
    assert "100% used, limit reached" in output
    assert "20% used" in output
    assert "usable@example.com" in output
    assert "plus" in output
    assert "active" in output
    assert "30% used" in output
    assert "available" in output


def test_auto_errors_when_no_profile_is_usable(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("AUTO_AUTH_HOME", str(tmp_path / "auto"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    write_named_profile(
        tmp_path, "limited_example_com", "limited@example.com", "limited", "acct-1"
    )
    monkeypatch.setattr(
        "shutil.which", lambda name: "/bin/codex" if name == "codex" else None
    )
    monkeypatch.setattr(
        "auto_auth_cli.tools.codex.adapter.CodexAdapter.select_usable_profile",
        lambda self, profiles, executable: None,
    )

    assert run(["codex", "--auto"]) == 1

    assert "no usable codex auth profiles found" in capsys.readouterr().err
