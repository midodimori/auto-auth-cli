from __future__ import annotations

from auto_auth_cli.tools.base import ToolAdapter
from auto_auth_cli.tools.codex import CodexAdapter

_TOOLS: dict[str, ToolAdapter] = {
    "codex": CodexAdapter(),
}


def get_tool(name: str) -> ToolAdapter:
    try:
        return _TOOLS[name]
    except KeyError:
        supported = ", ".join(sorted(_TOOLS))
        raise ValueError(f"unsupported tool {name!r}; supported tools: {supported}") from None


def tool_names() -> list[str]:
    return sorted(_TOOLS)
