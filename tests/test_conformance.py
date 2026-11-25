"""Lock the conformance report so a check cannot silently change status."""

import unittest

from osamp.conformance import run_all

EXPECTED = {
    "WP-01": "pass",
    "WP-02": "pass",
    "WP-03": "pass",
    "WP-04": "partial",
    "WP-05": "pass",
    "WP-06": "pass",
    "WP-07": "pass",
    "WP-08": "pass",
    "WP-09": "pass",
    "WP-10": "partial",
    "WP-11": "pass",
    "WP-12": "pending",
    "WP-13": "pass",
    "WP-14": "pass",
    "WP-15": "pass",
    "WP-16": "pass",
    "WP-17": "pass",
    "WP-18": "pass",
    "WP-19": "pass",
    "WP-20": "pass",
    "WP-21": "pass",
    "CZ-22": "pass",
    "CZ-23": "pass",
    "CZ-24": "pass",
    "CZ-25": "pass",
    "CZ-26": "pass",
    "CZ-27": "pass",
    "CZ-28": "partial",
    "CZ-29": "partial",
}


class ConformanceReportTests(unittest.TestCase):
    def test_statuses_match_the_recorded_report(self):
        results = run_all()
        got = {item.check_id: item.status for item in results}
        self.assertEqual(got, EXPECTED)
        self.assertNotIn("fail", got.values())
        self.assertEqual(len(results), 29)


if __name__ == "__main__":
    unittest.main()
