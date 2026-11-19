"""Batch alignment tests. Pure code, no API keys: python -m unittest test_llm"""
import asyncio
import json
import unittest
from unittest import mock

import llm


def _rows(*idxs):
    return [{"idx": i, "score": 10 - i} for i in idxs]


class AlignRowsTests(unittest.TestCase):
    def test_rows_in_order_are_kept(self):
        self.assertEqual(llm.align_rows(_rows(0, 1, 2), 3), _rows(0, 1, 2))

    def test_reordered_rows_go_back_to_their_idx(self):
        aligned = llm.align_rows(_rows(2, 0, 1), 3)
        self.assertEqual([r["idx"] for r in aligned], [0, 1, 2])

    def test_a_dropped_and_a_repeated_row_leave_a_gap_not_a_shift(self):
        aligned = llm.align_rows(_rows(0, 2, 2), 3)
        self.assertEqual(aligned[0]["idx"], 0)
        self.assertIsNone(aligned[1])
        self.assertEqual(aligned[2]["idx"], 2)

    def test_string_idx_is_accepted(self):
        aligned = llm.align_rows([{"idx": "1"}, {"idx": "0"}], 2)
        self.assertEqual([r["idx"] for r in aligned], ["0", "1"])

    def test_a_dropped_row_becomes_none(self):
        aligned = llm.align_rows(_rows(1, 0), 3)
        self.assertEqual([r and r["idx"] for r in aligned], [0, 1, None])

    def test_rows_without_idx_keep_their_order(self):
        rows = [{"score": 1}, {"score": 2}]
        self.assertEqual(llm.align_rows(rows, 2), rows)

    def test_idx_outside_the_batch_keeps_the_order(self):
        # e.g. a model that numbers from 1: idx 3 is not a position in a batch of 3
        rows = _rows(1, 2, 3)
        self.assertEqual(llm.align_rows(rows, 3), rows)

    def test_count_mismatch_without_idx_is_refused(self):
        with self.assertRaisesRegex(ValueError, "sent 3, got 2"):
            llm.align_rows([{"score": 1}, {"score": 2}], 3)

    def test_empty_reply_for_a_batch_is_refused(self):
        with self.assertRaisesRegex(ValueError, "sent 2, got 0"):
            llm.align_rows([], 2)


class MapBatchesTests(unittest.TestCase):
    def _run(self, replies, items, batch_size):
        replies = iter(replies)

        async def fake_chat(client, model, messages, temperature=0.0):
            return next(replies)

        with mock.patch.object(llm, "chat", fake_chat):
            return asyncio.run(llm.map_batches(
                None, "m", "{{ITEMS}}", items, batch_size,
                render=lambda b: "\n".join(b), concurrency=1))

    def test_a_reply_sorted_by_score_is_mapped_back_to_its_items(self):
        reply = json.dumps([
            {"idx": 2, "score": 9, "why": "c"},
            {"idx": 0, "score": 5, "why": "a"},
            {"idx": 1, "score": 1, "why": "b"},
        ])
        rows = self._run([reply], ["a", "b", "c"], batch_size=3)
        self.assertEqual([r["why"] for r in rows], ["a", "b", "c"])

    def test_each_batch_is_aligned_on_its_own_positions(self):
        first = json.dumps([{"idx": 1, "why": "b"}, {"idx": 0, "why": "a"}])
        second = json.dumps([{"idx": 0, "why": "c"}])
        rows = self._run([first, second], ["a", "b", "c"], batch_size=2)
        self.assertEqual([r["why"] for r in rows], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
