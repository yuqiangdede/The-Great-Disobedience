#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""python -m unittest test_review_quality_parity.py"""
import unittest
from verify_chapter_consistency import compute_seven_dimensions


class QualityParityTests(unittest.TestCase):
    def test_length_is_not_a_quality_dimension(self):
        clean = {"issues": [], "warnings": []}
        lang = {"ai_score": 1, "warnings": []}
        short = compute_seven_dimensions({"issues": ["篇幅不足"]}, clean, clean, clean, lang)
        normal = compute_seven_dimensions({"issues": []}, clean, clean, clean, lang)
        self.assertEqual(short["total_score"], normal["total_score"])
        self.assertEqual(short["dimension_scores"]["pacing_readability"],
                         normal["dimension_scores"]["pacing_readability"])
        self.assertEqual(short["scoring_kind"], "MECHANICAL_REFERENCE_ONLY")
        self.assertEqual(short["quality_review_status"], "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
