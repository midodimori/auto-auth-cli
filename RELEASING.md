# Releasing

Releases use GitHub Actions, Python Semantic Release, and PyPI Trusted Publishing.

## GitHub Release Workflow

The release workflow is `.github/workflows/release.yml`. It can run in two ways:

```text
GitHub Actions -> Release -> Run workflow -> choose patch, minor, or major
```

Or by merging a pull request into `main` with one of these labels:

```text
release:patch
release:minor
release:major
```

The workflow bumps the version, updates `CHANGELOG.md`, creates a git tag, and publishes a GitHub release.

Add this GitHub repository secret before running releases:

| Secret | Purpose |
|--------|---------|
| `RELEASE_PLEASE_TOKEN` | Personal access token used to push the release commit/tag and create the GitHub release |

Use a token that can write repository contents. A token is used instead of the default `GITHUB_TOKEN` so the published GitHub release can trigger the PyPI publish workflow.

## PyPI Trusted Publishing

Configure a trusted publisher on PyPI with:

| Setting | Value |
|---------|-------|
| PyPI project | `auto-auth-cli` |
| Owner | `midodimori` |
| Repository | `auto-auth-cli` |
| Workflow name | `publish-pypi.yml` |
| Environment name | Leave empty |

The PyPI workflow is `.github/workflows/publish-pypi.yml`. It publishes when a GitHub release is published and can also be run manually from GitHub Actions.
