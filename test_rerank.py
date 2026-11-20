"""Rerank tests. Pure code, no API keys: python -m unittest test_rerank"""
import asyncio
import math
import unittest
from unittest import mock

import llm
from wrapper import rerank


def _candidates(n):
    return [{"name": f"c{i}", "domain": f"c{i}.com", "source_rank": i} for i in range(n)]


def _run(candidates, rows):
    async def fake_map_batches(*args, **kwargs):
        return rows

    with mock.patch.object(llm, "deepseek_client", return_value=None), \
            mock.patch.object(llm, "map_batches", fake_map_batches):
        return asyncio.run(rerank.rerank(candidates, "Seed", "seed.com", "A seed company."))


class ScoreTests(unittest.TestCase):
    def test_numbers_and_numeric_strings_are_read(self):
        self.assertEqual(rerank._score(7), 7.0)
        self.assertEqual(rerank._score(6.5), 6.5)
        self.assertEqual(rerank._score("8"), 8.0)

    def test_a_missing_null_or_non_numeric_score_is_zero(self):
        for value in (None, "high", "", [], {}, True):
            with self.subTest(value=value):
                self.assertEqual(rerank._score(value), 0.0)

    def test_a_nan_or_infinite_score_is_zero(self):
        for value in ("nan", "inf", "-inf", math.nan, math.inf):
            with self.subTest(value=value):
                self.assertEqual(rerank._score(value), 0.0)


class RerankTests(unittest.TestCase):
    def test_rows_are_ranked_by_score(self):
        rows = [{"idx": 0, "score": 2}, {"idx": 1, "score": 9}, {"idx": 2, "score": 5}]
        final = _run(_candidates(3), rows)
        self.assertEqual([c["name"] for c in final], ["c1", "c2", "c0"])
        self.assertEqual([c["rank"] for c in final], [1, 2, 3])

    def test_a_null_score_ranks_last_instead_of_crashing_the_run(self):
        rows = [{"idx": 0, "score": None, "why": "?"}, {"idx": 1, "score": 4, "why": "ok"}]
        final = _run(_candidates(2), rows)
        self.assertEqual([(c["name"], c["rerank_score"]) for c in final],
                         [("c1", 4.0), ("c0", 0.0)])

    def test_a_non_numeric_score_ranks_last_instead_of_crashing_the_run(self):
        rows = [{"idx": 0, "score": "high"}, {"idx": 1, "score": 1}]
        final = _run(_candidates(2), rows)
        self.assertEqual([c["name"] for c in final], ["c1", "c0"])

    def test_a_nan_score_does_not_scramble_the_order(self):
        # NaN compares false with everything, so sorted() would leave it wherever it was
        rows = [{"idx": 0, "score": 3}, {"idx": 1, "score": "nan"}, {"idx": 2, "score": 8}]
        final = _run(_candidates(3), rows)
        self.assertEqual([c["name"] for c in final], ["c2", "c0", "c1"])

    def test_a_dropped_or_non_object_row_scores_zero(self):
        rows = [None, "not a row", {"idx": 2, "score": 6, "why": "peer"}]
        final = _run(_candidates(3), rows)
        self.assertEqual([c["name"] for c in final], ["c2", "c0", "c1"])
        self.assertEqual([c["rerank_why"] for c in final], ["peer", "", ""])

    def test_equal_scores_keep_the_source_order(self):
        rows = [{"idx": i, "score": 5} for i in range(3)]
        final = _run(_candidates(3), rows)
        self.assertEqual([c["name"] for c in final], ["c0", "c1", "c2"])


if __name__ == "__main__":
    unittest.main()
