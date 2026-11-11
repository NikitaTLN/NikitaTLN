"""Check that account-wide PR totals survive into the public cards safely."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import update_stats


class ProfileStatsTest(unittest.TestCase):
    def test_private_inclusive_pr_total_without_private_repository_details(self):
        def api(path, payload=None):
            if path == "users/NikitaTLN":
                return {"public_repos": 1, "followers": 1}
            if path.startswith("users/NikitaTLN/repos?"):
                return [
                    {"name": "public", "private": False, "fork": False, "stargazers_count": 3},
                    {"name": "PRIVATE_NAME_MUST_NOT_APPEAR", "private": True, "fork": False, "stargazers_count": 9},
                ]
            if path == "graphql":
                self.assertIn("pullRequests { totalCount }", payload["query"])
                self.assertNotIn("nodes", payload["query"])
                self.assertNotIn("edges", payload["query"])
                return {"data": {"user": {
                    "pullRequests": {"totalCount": 153},
                    "contributionsCollection": {
                        "totalPullRequestContributions": 2,
                        "totalCommitContributions": 301,
                        "contributionCalendar": {"totalContributions": 1218},
                    },
                }}}
            if path == "repos/NikitaTLN/public/languages":
                return {"Python": 100}
            self.fail(f"Unexpected API call: {path}")

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(update_stats, "api", api), patch.object(update_stats, "TOKEN", "test"), patch.object(update_stats, "ASSETS", Path(directory)):
                update_stats.main()
            for name in ("stats.svg", "stats-mobile.svg"):
                svg = (Path(directory) / name).read_text()
                self.assertIn("153 Pull requests", svg)
                self.assertIn("public + private / all time", svg)
                self.assertIn("public / past year", svg)
                self.assertIn("3 Stars earned", svg)
            for path in Path(directory).glob("*.svg"):
                self.assertNotIn("PRIVATE_NAME_MUST_NOT_APPEAR", path.read_text())


if __name__ == "__main__":
    unittest.main()
