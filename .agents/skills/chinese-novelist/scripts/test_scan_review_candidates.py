#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""python -m unittest test_scan_review_candidates.py"""
import json
import tempfile
import unittest
from pathlib import Path
from scan_review_candidates import review_candidates


class ReviewCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chapter = self.root / "06-正文" / "第一卷" / "第001章.md"
        self.chapter.parent.mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# 测试小说\n", encoding="utf-8")
        config = {"schema_version": 1, "review": {"repeated_equipment_terms": ["仪器甲"]},
                  "writing": {"chapter_min_han": 5, "chapter_max_han": 100}}
        (self.root / "novel.project.json").write_text(json.dumps(config, ensure_ascii=False),
                                                      encoding="utf-8")

    def test_prose_collects_only_actual_candidate_evidence(self):
        self.chapter.write_text(
            "# 第001章\n\n"
            "研究员把仪器甲放到桌上。\n\n"
            "“签了字，我认。”他说。\n\n"
            "仪器甲亮了一下。\n", encoding="utf-8")
        result = review_candidates([self.chapter], project_dir=self.root)
        self.assertEqual(result["status"], "CANDIDATES_ONLY")
        self.assertEqual(result["quality_review_status"], "NOT_EVALUATED")
        matches = {x["type"]: x for x in result["candidates"]}
        self.assertEqual(matches["SLOGAN_DIALOGUE_CANDIDATE"]["line"], 5)
        self.assertEqual(matches["EQUIPMENT_REPEAT_CANDIDATE"]["occurrences"], 2)
        self.assertEqual(matches["EQUIPMENT_REPEAT_CANDIDATE"]["first_mention"]["line"], 3)

    def test_can_detect_take_responsibility_or_custody(self):
        self.chapter.write_text("“这人我带。”值班员说。\n", encoding="utf-8")
        result = review_candidates([self.chapter], project_dir=self.root)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["type"], "SLOGAN_DIALOGUE_CANDIDATE")

    def test_outline_skips_all_wording_checks(self):
        self.chapter.write_text("“错我担。”\n仪器甲、仪器甲。\n", encoding="utf-8")
        result = review_candidates([self.chapter], mode="outline", project_dir=self.root)
        self.assertEqual(result["status"], "SKIPPED_BY_DESIGN")
        self.assertEqual(result["candidates"], [])

    def test_does_not_fabricate_severity_on_normal_usage(self):
        self.chapter.write_text("“我认得他。”\n仪器甲只有一次。\n", encoding="utf-8")
        result = review_candidates([self.chapter], project_dir=self.root)
        self.assertEqual(result["candidates"], [])

    def test_missing_file_is_not_a_pass(self):
        with self.assertRaises(FileNotFoundError):
            review_candidates([self.chapter], project_dir=self.root)


if __name__ == "__main__":
    unittest.main()
