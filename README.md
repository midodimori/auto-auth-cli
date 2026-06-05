# auto-auth-cli

Profile-aware auth switching for coder agent CLIs.

[![PyPI - Version](https://img.shields.io/pypi/v/auto-auth-cli?logo=pypi&logoColor=white)](https://pypi.org/project/auto-auth-cli/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/auto-auth-cli?logo=pypi&logoColor=white)](https://pypi.org/project/auto-auth-cli/)
[![Python Version](https://img.shields.io/pypi/pyversions/auto-auth-cli?logo=python&logoColor=white)](https://pypi.org/project/auto-auth-cli/)
[![License](https://img.shields.io/github/license/midodimori/auto-auth-cli)](https://github.com/midodimori/auto-auth-cli/blob/main/LICENSE)

`auto-auth` lets you keep multiple authentication profiles for a supported CLI and launch that CLI with the profile you choose. For Codex, it only replaces:

```text
~/.codex/auth.json
```

Everything else in `~/.codex` stays shared across profiles.

## Table of Contents

- [Supported Tools](#supported-tools)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [Quick Try from GitHub](#quick-try-from-github)
  - [Install from GitHub](#install-from-github)
  - [From Source](#from-source)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Codex](#codex)
  - [Claude Code](#claude-code)
- [Stored Files](#stored-files)
- [Development](#development)

## Supported Tools

| Tool | Status | Command category |
|------|--------|------------------|
| Codex | Supported | `auto-auth codex ...` |
| Claude Code | Planned | Not available yet |

## Prerequisites

- **Python 3.13+** - Required by the package.
- **[uv](https://docs.astral.sh/uv/)** - Used for installation and local development.
- **Codex CLI** - Required for the current `codex` category. The `codex` executable must be available in `PATH`.

## Installation

Use `--python 3.13` so uv builds the isolated tool environment with a supported Python version.

### From PyPI

Use this for the latest published release.

**Quick try (no installation):**

```sh
uvx --python 3.13 --from auto-auth-cli@latest auto-auth codex --status
```

**Install globally:**

```sh
uv tool install --python 3.13 auto-auth-cli
```

Then run from any directory:

```sh
auto-auth codex --status
```

> **Upgrading:** Run `uv tool upgrade --python 3.13 auto-auth-cli`.

### Quick Try from GitHub

Run `auto-auth` directly from GitHub without installing it globally:

```sh
uvx --python 3.13 --from git+https://github.com/midodimori/auto-auth-cli auto-auth codex --status
```

You can use the same `uvx` form for any Codex command:

```sh
uvx --python 3.13 --from git+https://github.com/midodimori/auto-auth-cli auto-auth codex --setup
uvx --python 3.13 --from git+https://github.com/midodimori/auto-auth-cli auto-auth codex --auto
uvx --python 3.13 --from git+https://github.com/midodimori/auto-auth-cli auto-auth codex --profile you -- -m gpt-5.5
```

### Install from GitHub

Recommended when you want the latest version from the repository available as a normal command.

```sh
uv tool install --python 3.13 git+https://github.com/midodimori/auto-auth-cli
```

Then run from any directory:

```sh
auto-auth codex --status
```

> **Upgrading:** Re-run `uv tool install --force --python 3.13 git+https://github.com/midodimori/auto-auth-cli`.

### From Source

```sh
git clone https://github.com/midodimori/auto-auth-cli.git
cd auto-auth-cli
uv sync
uv run auto-auth codex --status
```

To install globally from source:

```sh
uv tool install --python 3.13 --editable .
```

Then run from any directory:

```sh
auto-auth codex --status
```

## Quick Start

Create a Codex profile:

```sh
auto-auth codex --setup
```

List saved profiles:

```sh
auto-auth codex --status
```

Run Codex with a saved profile:

```sh
auto-auth codex --profile you@example.com
```

Run Codex with the first profile that has available quota:

```sh
auto-auth codex --auto
```

Pass Codex arguments after `--`:

```sh
auto-auth codex --profile you -- -m gpt-5.5  # Run Codex with a specific profile and model
auto-auth codex --auto -- -m gpt-5.5  # Auto-select a profile, then run Codex with a model
auto-auth codex --auto -- --yolo app  # Auto-select a profile, then run the Codex app in yolo mode
```

## Usage

The first positional argument is the tool category. Codex is the only supported category today.

```sh
auto-auth <tool> [OPTIONS] [-- TOOL_ARGS...]
```

### Codex

#### Create a Profile

```sh
auto-auth codex --setup
```

`--setup` runs `codex login` in a temporary Codex home, extracts the account metadata from the generated auth file, and saves it as a reusable profile. It does not overwrite your active `~/.codex/auth.json`.

If setup cannot detect an email or account id, provide a label:

```sh
auto-auth codex --setup --label work
```

#### List Profiles

```sh
auto-auth codex --status
```

The status output shows the active profile, saved profiles, detected plan type, and active marker when the saved account matches the current `~/.codex/auth.json`.

#### Select a Profile

```sh
auto-auth codex --profile you@example.com
```

`--profile` accepts a profile email, profile key, account id, or unique prefix:

```sh
auto-auth codex --profile you
```

Before switching, `auto-auth` backs up the current Codex auth file, then installs the selected profile into:

```text
~/.codex/auth.json
```

#### Auto-Select a Profile

```sh
auto-auth codex --auto
```

`--auto` checks saved profiles and launches Codex with the first account that has available quota. Smaller subscriptions are checked first.

#### Pass Codex Arguments

Put Codex arguments after `--`:

```sh
auto-auth codex --profile you -- -m gpt-5.5  # Run Codex with a specific profile and model
auto-auth codex --auto -- -m gpt-5.5  # Auto-select a profile, then run Codex with a model
auto-auth codex --auto -- --yolo app  # Auto-select a profile, then run the Codex app in yolo mode
```

The last example runs the Codex app in yolo mode after selecting an available profile.

#### Codex Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CODEX_HOME` | Active Codex config directory | `~/.codex` |
| `AUTO_AUTH_HOME` | Root directory for saved profiles and backups | `~/.auto-auth` |

### Claude Code

Claude Code support is planned for a future tool category. Until that adapter exists, `auto-auth` only accepts:

```sh
auto-auth codex ...
```

## Stored Files

Codex profiles:

```text
~/.auto-auth/codex/profiles/
```

Codex auth backups:

```text
~/.auto-auth/codex/backups/
```

If `AUTO_AUTH_HOME` is set, those paths move under that directory.

## Development

```sh
uv sync
uv run pytest -q
uv run ruff check .
uv run ty check
```
