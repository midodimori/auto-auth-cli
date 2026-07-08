from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from typing import Any

from auto_auth_cli.store import Profile
from auto_auth_cli.tools.base import QuotaStatus


def profile_has_available_quota(profile: Profile, executable_path: str) -> bool:
    response = read_profile_rate_limits(profile, executable_path)
    return is_usable_rate_limits(response)


def read_profile_rate_limits(profile: Profile, executable_path: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="auto-auth-codex-probe-") as temp_dir:
        temp_home = Path(temp_dir)
        shutil.copy2(profile.auth_path, temp_home / "auth.json")
        return read_account_rate_limits(executable_path, temp_home)


def read_profile_quota_status(profile: Profile, executable_path: str) -> QuotaStatus:
    try:
        response = read_profile_rate_limits(profile, executable_path)
        return describe_rate_limit_windows(response)
    except (OSError, RuntimeError) as error:
        return _same_status(_quota_error_status(error))


def describe_rate_limit_windows(response: dict[str, Any]) -> QuotaStatus:
    rate_limits = response.get("rateLimits")
    if not isinstance(rate_limits, dict):
        return QuotaStatus(primary="unknown", secondary="unknown")

    reached_type = rate_limits.get("rateLimitReachedType")
    return QuotaStatus(
        primary=_describe_window(rate_limits.get("primary"), "primary", reached_type),
        secondary=_describe_window(
            rate_limits.get("secondary"), "secondary", reached_type
        ),
    )


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
    env["AUTO_AUTH_CODEX_WRAPPER_ACTIVE"] = "1"
    env["CMUX_CODEX_AUTO_AUTH_DISABLED"] = "1"
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
    reader = threading.Thread(
        target=_read_stdout, args=(process.stdout, lines), daemon=True
    )
    reader.start()

    try:
        _send(
            process, {"method": "initialize", "id": 1, "params": _initialize_params()}
        )
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


def _describe_window(value: Any, window_name: str, reached_type: Any) -> str:
    if value is None:
        return "available"
    if not isinstance(value, dict):
        return "unknown"

    parts: list[str] = []
    used_percent = _number(value.get("usedPercent"))
    if used_percent is not None:
        parts.append(f"{_format_percent(used_percent)} used")

    resets_at = _number(value.get("resetsAt"))
    if resets_at is not None:
        parts.append(f"resets {_format_reset(resets_at)}")

    if _is_limit_reached(window_name, reached_type, used_percent):
        parts.append("limit reached")

    return ", ".join(parts) if parts else "available"


def _is_limit_reached(
    window_name: str, reached_type: Any, used_percent: float | None
) -> bool:
    if used_percent is not None and used_percent >= 100:
        return True
    if not isinstance(reached_type, str):
        return False
    normalized = reached_type.lower()
    return normalized in {window_name, "all", "both"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _format_percent(value: float) -> str:
    formatted = (
        str(int(value))
        if value.is_integer()
        else f"{value:.1f}".rstrip("0").rstrip(".")
    )
    return f"{formatted}%"


def _format_reset(resets_at: float) -> str:
    seconds = resets_at - datetime.now(timezone.utc).timestamp()
    return _format_duration(seconds)


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "now"

    total_seconds = int(round(seconds))
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(_duration_part(days, "day"))
    if hours and len(parts) < 2:
        parts.append(_duration_part(hours, "hour"))
    if minutes and len(parts) < 2:
        parts.append(_duration_part(minutes, "minute"))
    if not parts:
        parts.append(_duration_part(seconds, "second"))
    return "in " + " ".join(parts)


def _duration_part(value: int, unit: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value} {unit}{suffix}"


def _same_status(status: str) -> QuotaStatus:
    return QuotaStatus(primary=status, secondary=status)


def _quota_error_status(error: Exception) -> str:
    message = str(error)
    if "token_expired" in message:
        return "token expired"
    if "token_invalidated" in message:
        return "token invalidated"
    if "token_revoked" in message:
        return "token revoked"
    if "401 Unauthorized" in message:
        return "auth failed"
    return "unavailable"


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
