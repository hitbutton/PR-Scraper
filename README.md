# VS Code PR Exporter

Extracts all PRs from the Microsoft VS Code repo via GitHub GraphQL API, and writes them to csv.

Fields extracted:
`number`, `title`, `created_at`, `merged_at`, `user.type`, `base.ref`, `comments`, `additions`, `deletions`

##Features
- Avoids GitHub Search 1000-result cap by subdividing time ranges
- Cursor pagination (handles all PRs across pages)
- Rate limit handling (auto-sleeps until reset time)
- Retry with exponential backoff on transient errors
- Graceful error recovery—skips failed ranges, writes to CSV incrementally

## Quick Start
1. **Install**: `pip install -r requirements.txt`
2. **Get token**: Create a [personal access token](https://github.com/settings/tokens) (no special scopes needed)
3. **Configure**: Update `.env` with your token:
   ```
   GITHUB_TOKEN=your_token_here
   ```
4. **Run**: `python fetch_prs.py`

## Files
- `fetch_prs.py`: Main script—time range logic, CSV writing, pagination
- `github_api.py`: GitHub GraphQL wrapper—retry logic, rate limit handling
- `test_connection.py`: Quick test script to verify GitHub token and API connectivity
- `.env`: Configuration (add your API token here)
