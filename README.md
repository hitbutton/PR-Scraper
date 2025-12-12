# VS Code PR Exporter

Extracts all PRs from [microsoft/vscode](https://github.com/microsoft/vscode) (2020-01-01 to present) via GraphQL API.

## Quick Start

1. **Install**: `pip install -r requirements.txt`
2. **Get token**: Create a [personal access token](https://github.com/settings/tokens) (no special scopes needed)
3. **Configure**: Update `.env` with your token:
   ```
   GITHUB_TOKEN=your_token_here
   ```
4. **Run**: `python fetch_prs.py`

Output goes to `vscode_prs.csv` with fields:
`number`, `created_at`, `merged_at`, `user.type`, `base.ref`, `comments`, `additions`, `deletions`

## Features

- ✅ Cursor pagination (handles all PRs across pages)
- ✅ Rate limit handling (auto-sleeps until reset)
- ✅ Retry with exponential backoff (up to 5 attempts)
- ✅ Minimal deps (just `requests` + `python-dotenv`)
- ✅ Graceful Ctrl+C interruption

## How It Works

- `fetch_prs.py`: Main script—queries GraphQL, writes CSV
- `github_api.py`: API wrapper—retry logic, rate limit handling
- `.env`: Configuration (add your real token here)
