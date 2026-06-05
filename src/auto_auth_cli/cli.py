from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from auto_auth_cli.metadata import AuthMetadata, sanitize_profile_key
from auto_auth_cli.paths import ToolPaths
from auto_auth_cli.store import ProfileStore
from auto_auth_cli.tools import get_tool, tool_names
from auto_auth_cli.tools.base import ToolAdapter


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    adapter = get_tool(args.tool)
    paths = ToolPaths.from_env(adapter)
    store = ProfileStore(paths)

    try:
        if args.status:
            return _status(adapter, store, paths)
        if args.setup:
            return _setup(adapter, store, args.label)
        if args.auto:
            return _auto(adapter, store, args.tool_args)
        if args.profile:
            profile = store.install_profile(args.profile)
            print(
                f"Using {adapter.name} auth profile: {profile.metadata.label}",
                file=sys.stderr,
            )
            return _exec_tool(adapter, args.tool_args)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"auto-auth: {error}", file=sys.stderr)
        return 1

    parser.error("provide --setup, --status, --auto, or --profile")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-auth")
    subparsers = parser.add_subparsers(dest="tool", required=True)

    for tool_name in tool_names():
        tool_parser = subparsers.add_parser(
            tool_name, help=f"manage and launch {tool_name} auth profiles"
        )
        group = tool_parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--setup", action="store_true", help=f"create a profile via {tool_name} login")
        group.add_argument("--status", action="store_true", help=f"list {tool_name} auth profiles")
        group.add_argument("--auto", action="store_true", help="use the first profile with available quota")
        group.add_argument("--profile", help="profile email, key, account id, or unique prefix")
        tool_parser.add_argument(
            "--label",
            help="fallback label for setup when the auth token has no email or account id",
        )
        tool_parser.add_argument("tool_args", nargs=argparse.REMAINDER)
    return parser


def _status(adapter: ToolAdapter, store: ProfileStore, paths: ToolPaths) -> int:
    active_metadata = None
    if paths.active_auth_path.exists():
        active_json = _read_json(paths.active_auth_path)
        active_metadata = adapter.extract_metadata(active_json)

    active_account = active_metadata.account_id if active_metadata else None
    print(f"Active: {active_metadata.label if active_metadata else 'none'}")
    print()
    print("Profiles:")

    profiles = store.list_profiles()
    if not profiles:
        print("  none")
        return 0

    for profile in profiles:
        marker = (
            " active"
            if active_account and profile.metadata.account_id == active_account
            else ""
        )
        plan = profile.metadata.plan_type or "unknown"
        print(f"  {profile.metadata.label}\t{plan}{marker}")
    return 0


def _setup(adapter: ToolAdapter, store: ProfileStore, label: str | None) -> int:
    executable = shutil.which(adapter.executable)
    if executable is None:
        raise OSError(f"{adapter.executable} executable not found in PATH")

    with tempfile.TemporaryDirectory(prefix=f"auto-auth-{adapter.name}-") as temp_dir:
        temp_home = Path(temp_dir)
        subprocess.run(
            adapter.login_command(executable),
            check=True,
            env=adapter.setup_env(temp_home),
        )
        auth_json = _read_json(adapter.active_auth_path(temp_home))
        metadata = _metadata_with_label_fallback(adapter, auth_json, label)
        if metadata.label == "unknown":
            raise ValueError("could not extract email or account id; rerun with --label")
        store.save_profile(metadata, auth_json)
        print(f"Saved {adapter.name} auth profile: {metadata.label}")
    return 0


def _auto(adapter: ToolAdapter, store: ProfileStore, tool_args: list[str]) -> int:
    executable = shutil.which(adapter.executable)
    if executable is None:
        raise OSError(f"{adapter.executable} executable not found in PATH")

    profiles = adapter.sort_profiles_for_auto(store.list_profiles())
    if not profiles:
        raise ValueError(f"no {adapter.name} auth profiles saved")

    selector = getattr(adapter, "select_usable_profile", None)
    if selector is None:
        raise ValueError(f"{adapter.name} does not support automatic profile selection")

    profile = selector(profiles, executable)
    if profile is None:
        raise ValueError(f"no usable {adapter.name} auth profiles found")

    store.install_profile(profile.metadata.key)
    print(
        f"Using {adapter.name} auth profile: {profile.metadata.label}",
        file=sys.stderr,
    )
    return _exec_tool(adapter, tool_args)


def _metadata_with_label_fallback(
    adapter: ToolAdapter, auth_json: dict, label: str | None
) -> AuthMetadata:
    metadata = adapter.extract_metadata(auth_json)
    if metadata.label != "unknown" or not label:
        return metadata
    return AuthMetadata(
        key=sanitize_profile_key(label),
        label=label,
        email=None,
        account_id=metadata.account_id,
        plan_type=metadata.plan_type,
    )


def _exec_tool(adapter: ToolAdapter, tool_args: list[str]) -> int:
    args = tool_args[1:] if tool_args and tool_args[0] == "--" else tool_args
    argv = [adapter.executable, *args]
    try:
        os.execvp(adapter.executable, argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data
