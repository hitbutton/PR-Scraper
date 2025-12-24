# VS Code PR Exporter

Extracts Pull Request data from Microsoft's VSCode repo via GitHub GraphQL API, and writes the records to csv.

Fields extracted:
`number`, `title`, `created_at`, `merged_at`, `user.type`, `base.ref`, `comments`, `additions`, `deletions`

## Quick Start
1. **Install**: `pip install -r requirements.txt`
2. **Get token**: Create a [personal access token](https://github.com/settings/tokens)
3. **Configure**: Update `.env` with your token:
   ```
   GITHUB_TOKEN=your_token_here
   ```
4. **Run**: `python fetch_prs.py`

## Features
- Avoids GitHub Search 1000-result cap by subdividing time ranges
- Cursor pagination (handles all PRs across pages)
- Rate limit handling (auto-sleeps until reset time)
- Retry with exponential backoff on transient errors
- Graceful error recovery—skips failed ranges, writes to CSV incrementally

## Files
- `fetch_prs.py`: Main script
- `test_connection.py`: Test script to verify GitHub token and API connectivity
- `.env`: Configuration (add your API token here)
