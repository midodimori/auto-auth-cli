from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
from typing import Any

from auto_auth_cli.store import Profile


def profile_has_available_quota(profile: Profile, executable_path: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="auto-auth-codex-probe-") as temp_dir:
        temp_home = Path(temp_dir)
        shutil.copy2(profile.auth_path, temp_home / "auth.json")
        response = read_account_rate_limits(executable_path, temp_home)
    return is_usable_rate_limits(response)


def is_usable_rate_limits(response: dict[str, Any]) -> bool:
    rate_limits = response.get("rateLimits")
    if not isinstance(rate_limits, dict):
        return False
    if rate_limits.get("rateLimitReachedType") is not None:
        return False
    return _window_allows(rate_limits.get("primary")) and _window_allows(
        rate_limits.get("secondary")
    )


def read_account_rate_limits(executable_path: str, codex_home: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    process = subprocess.Popen(
        [executable_path, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("failed to open codex app-server pipes")

    lines: queue.Queue[str] = queue.Queue()
    reader = threading.Thread(target=_read_stdout, args=(process.stdout, lines), daemon=True)
    reader.start()

    try:
        _send(process, {"method": "initialize", "id": 1, "params": _initialize_params()})
        _read_response(lines, request_id=1, timeout_seconds=10)
        _send(process, {"method": "initialized", "params": {}})
        _send(process, {"method": "account/rateLimits/read", "id": 2})
        message = _read_response(lines, request_id=2, timeout_seconds=10)
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    if "error" in message:
        error = message["error"]
        if isinstance(error, dict):
            raise RuntimeError(error.get("message") or json.dumps(error))
        raise RuntimeError(str(error))

    result = message.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("codex app-server returned an invalid rate limit response")
    return result


def _window_allows(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict):
        return False
    used_percent = value.get("usedPercent")
    if not isinstance(used_percent, int | float):
        return False
    return used_percent < 100


def _initialize_params() -> dict[str, Any]:
    return {
        "clientInfo": {
            "name": "auto_auth_cli",
            "title": "auto-auth-cli",
            "version": "0.1.0",
        }
    }


def _send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if process.stdin is None:
        raise RuntimeError("codex app-server stdin is closed")
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _read_stdout(stdout, lines: queue.Queue[str]) -> None:
    for line in stdout:
        lines.put(line)


def _read_response(
    lines: queue.Queue[str], request_id: int, timeout_seconds: int
) -> dict[str, Any]:
    while True:
        try:
            line = lines.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise RuntimeError("timed out waiting for codex rate limits") from exc
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        if message.get("id") == request_id:
            return message
