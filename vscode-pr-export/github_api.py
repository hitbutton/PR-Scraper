"""
Lightweight GitHub GraphQL API wrapper with retry and rate limit handling.
"""
import time
import requests


def run_graphql_query(query, variables, token):
    """
    Execute a GraphQL query against GitHub's API with retry logic.

    Args:
        query (str): GraphQL query string
        variables (dict): Variables for the query
        token (str): GitHub personal access token

    Returns:
        dict: Parsed JSON response or raises Exception on final retry failure

    Handles:
        - Rate limit exhaustion (sleeps until resetAt)
        - 502/503 errors and timeouts (exponential backoff)
        - Up to 5 retry attempts total
    """
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    max_retries = 5
    backoff_factor = 2  # Exponential backoff: 1s, 2s, 4s, 8s, 16s

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=30,
            )

            # Check for rate limiting in response headers
            if "X-RateLimit-Remaining" in response.headers:
                remaining = int(response.headers["X-RateLimit-Remaining"])
                if remaining < 100:
                    print(
                        f"[WARN] Rate limit low ({remaining} remaining). "
                        "Consider slowing requests."
                    )

            # Parse response
            data = response.json()

            # Check for rate limit error in GraphQL response
            if "errors" in data:
                errors = data.get("errors", [])
                for error in errors:
                    if "API rate limit exceeded" in str(error.get("message", "")):
                        # Extract resetAt from rateLimit node if available
                        rate_limit_info = data.get("data", {}).get("rateLimit", {})
                        reset_at = rate_limit_info.get("resetAt")
                        if reset_at:
                            # Parse ISO 8601 timestamp and calculate sleep time
                            import datetime
                            reset_time = datetime.datetime.fromisoformat(
                                reset_at.replace("Z", "+00:00")
                            )
                            now = datetime.datetime.now(datetime.timezone.utc)
                            sleep_seconds = max(
                                1, (reset_time - now).total_seconds() + 5
                            )
                            print(
                                f"[RATE LIMIT] Sleeping {sleep_seconds:.0f}s "
                                f"until {reset_at}"
                            )
                            time.sleep(sleep_seconds)
                            continue
                        else:
                            # Fallback: wait 60 seconds
                            print("[RATE LIMIT] No resetAt. Sleeping 60s...")
                            time.sleep(60)
                            continue

            # Success or other GraphQL error
            if response.status_code == 200:
                return data

            # HTTP errors (non-200)
            if response.status_code in (502, 503):
                if attempt < max_retries:
                    wait_time = backoff_factor ** (attempt - 1)
                    print(
                        f"[RETRY {attempt}/{max_retries}] HTTP {response.status_code} "
                        f"error. Waiting {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"HTTP {response.status_code} after {max_retries} retries"
                    )

            # Unexpected status code
            raise Exception(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait_time = backoff_factor ** (attempt - 1)
                print(
                    f"[RETRY {attempt}/{max_retries}] Timeout. "
                    f"Waiting {wait_time}s..."
                )
                time.sleep(wait_time)
                continue
            else:
                raise Exception(f"Timeout after {max_retries} retries")

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = backoff_factor ** (attempt - 1)
                print(
                    f"[RETRY {attempt}/{max_retries}] Request error: {e}. "
                    f"Waiting {wait_time}s..."
                )
                time.sleep(wait_time)
                continue
            else:
                raise Exception(f"Request failed after {max_retries} retries: {e}")

    raise Exception("Max retries exceeded (no successful response)")
