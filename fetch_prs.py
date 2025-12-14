#!/usr/bin/env python3
"""
Fetch PRs from microsoft/vscode and write to CSV.

This script avoids GitHub Search's 1000-result cap by subdividing time ranges
until each query returns fewer than 1000 results, then paginates those windows.

Output fields: number, title, created_at, merged_at, user.type, base.ref, comments, additions, deletions
"""
import os
import json
import re
import csv
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from github_api import run_graphql_query

# Configuration
OWNER = "microsoft"
REPO = "vscode"
# Inclusive start date; modify if you want a different range
START_DATE = "2020-01-01T00:00:00Z"
OUTPUT_CSV = "vscode_prs.csv"

# GraphQL query for fetching PRs with pagination (includes issueCount)
QUERY = """
query($queryString: String!, $after: String) {
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
  search(query: $queryString, type: ISSUE, first: 100, after: $after) {
    issueCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on PullRequest {
        number
        title
        createdAt
        mergedAt
        author {
          __typename
        }
        baseRefName
        comments {
          totalCount
        }
        additions
        deletions
      }
    }
  }
}
"""


def normalize_pr(pr_node):
    return {
        "number": pr_node.get("number"),
        "title": pr_node.get("title"),
        "created_at": pr_node.get("createdAt"),
        "merged_at": pr_node.get("mergedAt"),
        "user.type": (pr_node.get("author") or {}).get("__typename", "null"),
        "base.ref": pr_node.get("baseRefName"),
        "comments": pr_node.get("comments", {}).get("totalCount", 0),
        "additions": pr_node.get("additions", 0),
        "deletions": pr_node.get("deletions", 0),
    }


def iso_z(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_run_query(query, variables, token, max_retries=1):
    """Run the GraphQL query and retry once on invalid (None/non-dict) responses.

    Returns the response dict or None if still invalid after retries.
    """
    import time

    last_resp = None
    for attempt in range(max_retries + 1):
        resp = run_graphql_query(query, variables, token)
        last_resp = resp
        if isinstance(resp, dict):
            return resp
        if attempt < max_retries:
            wait = 2 ** attempt
            print(f"[WARN] Invalid API response (attempt {attempt+1}/{max_retries+1}). Retrying in {wait}s...")
            time.sleep(wait)

    # persist raw invalid response to disk for debugging
    try:
        save_invalid_response(last_resp)
    except Exception as e:
        print(f"[ERROR] Could not save invalid response: {e}")

    return None


def save_invalid_response(resp):
    """Save `resp` to the first available filename invalid_responseNNNN.

    The file is written next to the script. If `resp` is None, the file will
    contain the text 'None'. For dict-like objects we write pretty JSON; for
    others we write str(resp).
    """
    base = os.path.dirname(__file__) or "."
    names = [n for n in os.listdir(base) if n.startswith("invalid_response")]
    max_index = 0
    pat = re.compile(r"invalid_response(\d{4})$")
    for n in names:
        m = pat.match(n)
        if m:
            try:
                idx = int(m.group(1))
                if idx > max_index:
                    max_index = idx
            except Exception:
                continue

    next_index = max_index + 1
    filename = f"invalid_response{next_index:04d}"
    path = os.path.join(base, filename)

    if resp is None:
        body = "None\n"
    else:
        try:
            body = json.dumps(resp, indent=2, ensure_ascii=False)
        except Exception:
            body = str(resp)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def fetch_range_and_write(start_dt, end_dt, writer, token, totals):
    """
    For a given time window [start_dt, end_dt), page through results and write to CSV.
    Returns number written.
    """
    written = 0
    start_iso = iso_z(start_dt)
    end_iso = iso_z(end_dt)
    query_string = f"repo:{OWNER}/{REPO} is:pr created:{start_iso}..{end_iso}"

    after_cursor = None
    page = 0
    while True:
        page += 1
        print(f"[Range {start_iso} -> {end_iso}] Page {page} (after={after_cursor[:20] if after_cursor else 'None'})")
        variables = {"queryString": query_string, "after": after_cursor}
        resp = safe_run_query(QUERY, variables, token, max_retries=1)

        # If we still get an invalid response after retry, skip remaining pages of this range
        if resp is None:
            print(f"[WARN] Invalid API response for range {start_iso} -> {end_iso}; skipping remaining pages of this range.")
            return written

        if "errors" in resp:
            print("ERROR: GraphQL errors in response:")
            for error in resp["errors"]:
                print(f"  - {error.get('message')}")
            raise SystemExit(1)

        data = resp.get("data", {})
        rate_limit = data.get("rateLimit", {})
        search = data.get("search", {})
        nodes = search.get("nodes", [])
        page_info = search.get("pageInfo", {})

        remaining = rate_limit.get("remaining")
        print(f"[Rate Limit] {remaining} remaining (cost: {rate_limit.get('cost')})")
        print(f"[Fetched] {len(nodes)} PRs on this page")

        for pr in nodes:
            if not isinstance(pr, dict):
                print(f"[WARN] Skipping unexpected node (not a dict): {pr!r}")
                try:
                    save_invalid_response(pr)
                except Exception:
                    pass
                continue
            try:
                writer.writerow(normalize_pr(pr))
            except Exception as e:
                print(f"[WARN] Failed to write PR row: {e}")
                try:
                    save_invalid_response(pr)
                except Exception:
                    pass
                continue
            written += 1
            totals["count"] += 1

        if not page_info.get("hasNextPage", False):
            break
        after_cursor = page_info.get("endCursor")

    return written


def main():
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable not set.")
        print("Set it before running: export GITHUB_TOKEN=your_token")
        sys.exit(1)

    # prepare CSV
    csv_file = open(OUTPUT_CSV, "w", newline="", encoding="utf-8")
    fieldnames = [
        "number",
        "title",
        "created_at",
        "merged_at",
        "user.type",
        "base.ref",
        "comments",
        "additions",
        "deletions",
    ]
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()

    # convert START_DATE to datetime
    try:
        start_dt = datetime.strptime(START_DATE, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        # try parsing without Z
        start_dt = datetime.fromisoformat(START_DATE.replace("Z", ""))

    end_dt = datetime.utcnow()

    # stack of ranges to process (start inclusive, end exclusive)
    ranges = [(start_dt, end_dt)]
    totals = {"count": 0}

    try:
        while ranges:
            s, e = ranges.pop(0)
            if s >= e:
                continue

            s_iso = iso_z(s)
            e_iso = iso_z(e)
            print(f"\n[Range] Processing {s_iso} -> {e_iso}")

            # quick check of issueCount for this range
            qs = f"repo:{OWNER}/{REPO} is:pr created:{s_iso}..{e_iso}"
            variables = {"queryString": qs, "after": None}
            resp = safe_run_query(QUERY, variables, token, max_retries=1)

            if resp is None:
                print(f"[WARN] Invalid API response during count check for {s_iso} -> {e_iso}; skipping this range.")
                continue

            if "errors" in resp:
                print("ERROR: GraphQL errors in response (during count check):")
                for error in resp["errors"]:
                    print(f"  - {error.get('message')}")
                raise SystemExit(1)

            data = resp.get("data", {})
            search = data.get("search", {})
            issue_count = search.get("issueCount", 0)
            print(f"[Range Count] {issue_count} matching PRs in this window")

            # GitHub search caps results at 1000; subdivide if at or above cap
            if issue_count >= 1000:
                # if the range is already very small, still attempt to paginate to avoid infinite split
                duration = (e - s)
                if duration <= timedelta(seconds=1):
                    print("[Warning] Range is <=1s but >=1000 results — paginating anyway.")
                    fetch_range_and_write(s, e, writer, token, totals)
                else:
                    mid = s + (e - s) / 2
                    print(f"[Split] Too many results; splitting into {iso_z(s)}..{iso_z(mid)} and {iso_z(mid)}..{iso_z(e)}")
                    # Push the second half first so we process the earlier half next (keeps ordering)
                    ranges.insert(0, (mid, e))
                    ranges.insert(0, (s, mid))
            else:
                # Safe to fetch this range fully (may still page)
                written = fetch_range_and_write(s, e, writer, token, totals)
                print(f"[Done Range] Wrote {written} PRs for {s_iso} -> {e_iso}")

    except KeyboardInterrupt:
        print("\n[Interrupted] Exiting gracefully...")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)
    finally:
        csv_file.close()
        print(f"\n[Summary] Wrote {totals['count']} PRs to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
