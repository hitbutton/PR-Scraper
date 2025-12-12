from dotenv import load_dotenv
import os
from github_api import run_graphql_query

load_dotenv()
# Load token from environment
TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise SystemExit("GITHUB_TOKEN not set in environment")

# Simple GraphQL query to get your GitHub username
TEST_QUERY = """
query {
  viewer {
    login
  }
}
"""

response = run_graphql_query(TEST_QUERY, {}, TOKEN)

print("Response from GitHub GraphQL:")
print(response)
