#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行：python -m unittest discover -s .agents/skills/chinese-novelist/scripts -p 'test_translationese_ai_review.py'"""
import tempfile
import unittest
from pathlib import Path

import scan_ai_tone as scan


class TranslationeseScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scan(self, text):
        p = self.root / "第001章.md"
        p.write_text(text, encoding="utf-8")
        return scan.scan_file(p, min_words=0)

    def warnings(self, text):
        result = self.scan(text)
        return [i for i in result["issues"] if i["rule_id"].startswith("TR-")]

    def test_all_new_patterns_are_review_warnings(self):
        rules = [r for r in scan.RULES if r["id"].startswith("TR-")]
        self.assertEqual(len(rules), 9)
        self.assertEqual(len({r["id"] for r in rules}), 9)
        self.assertTrue(all(r["severity"] == "WARN" and r["gate"] == "G3" for r in rules))

    def test_europeanized_subject_and_causal_shell(self):
        hits = self.warnings("他的离开让她感到悲伤。\n由于电台断电，导致山口失联。")
        ids = {i["rule_id"] for i in hits}
        self.assertIn("TR-02", ids)
        self.assertIn("TR-11", ids)
        self.assertTrue(all(i["line"] in (1, 2) for i in hits))

    def test_jargon_warns_but_is_not_auto_blocked(self):
        result = self.scan("工程师调了门控参数。")
        self.assertTrue(any(i["rule_id"] == "TR-13" and i["severity"] == "WARN" for i in result["issues"]))
        self.assertEqual(result["block_count"], 0)
        self.assertEqual(result["overall_status"], "PASS_WITH_WARNINGS")

    def test_normal_action_has_no_translationese_warning(self):
        self.assertEqual(self.warnings("队长关掉电台，走出岗哨。"), [])

    def test_dialogue_masking_for_narration_rules(self):
        hits = self.warnings("“由于夜里断电，导致电台失联。”机械师说。")
        self.assertNotIn("TR-11", {i["rule_id"] for i in hits})

    def test_report_keeps_location_and_context(self):
        hit = next(i for i in self.warnings("队伍具有很高的重要性。") if i["rule_id"] == "TR-03")
        self.assertEqual(hit["line"], 1)
        self.assertIn("具有", hit["match"])
        self.assertTrue(hit["context"])


if __name__ == "__main__":
    unittest.main()
