#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目配置和 CLI 篇幅回归测试：python -m unittest test_project_config.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from project_config import chapter_limits, load_project_config, project_file

SCRIPT_DIR = Path(__file__).resolve().parent


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "AGENTS.md").write_text("# 测试工程\n", encoding="utf-8")
        self.chapter = self.root / "06-正文" / "第一卷" / "第001章.md"
        self.chapter.parent.mkdir(parents=True)
        self.chapter.write_text("# 第001章\n\n只写了两句。\n", encoding="utf-8")

    def write_config(self, **writing):
        cfg = {"schema_version": 1,
               "writing": {"chapter_min_han": 4500, "chapter_max_han": 5000,
                           "brief_target_han": 500, "interlude_unbounded": True,
                           "author_approval_required": True, **writing},
               "review": {"travel_location_terms": ["虚构港口"], "repeated_equipment_terms": ["装备A"]},
               "paths": {"story_rules": "04-文风/本书规则.md"}}
        (self.root / "novel.project.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    def test_generic_fallback(self):
        self.assertEqual(chapter_limits(self.chapter), (3000, 5000))

    def test_story_limits_and_override(self):
        self.write_config()
        self.assertEqual(chapter_limits(self.chapter), (4500, 5000))
        self.assertEqual(chapter_limits(self.chapter, min_words=3900), (3900, 5000))
        interlude = self.chapter.with_name("第一卷插章001.md")
        self.assertEqual(chapter_limits(interlude), (0, 0))
        self.assertEqual(chapter_limits(interlude, min_words=10), (10, 0))

    def test_invalid_config_blocks(self):
        self.write_config(chapter_min_han=6000)
        with self.assertRaises(ValueError):
            load_project_config(self.root)

    def test_story_terms_are_isolated(self):
        self.write_config()
        review = load_project_config(self.root)["review"]
        self.assertEqual(review["travel_location_terms"], ["虚构港口"])
        self.assertEqual(review["repeated_equipment_terms"], ["装备A"])

    def test_path_restriction(self):
        self.write_config()
        cfg = json.loads((self.root / "novel.project.json").read_text(encoding="utf-8"))
        cfg["paths"]["story_rules"] = "../outside.md"
        (self.root / "novel.project.json").write_text(json.dumps(cfg), encoding="utf-8")
        with self.assertRaises(ValueError):
            project_file(self.root, "story_rules")

    def test_scan_chapter_uses_project_limits(self):
        self.write_config(chapter_min_han=4, chapter_max_han=30)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "scan_chapter.py"), str(self.chapter), "--json"],
            text=True, encoding="utf-8", capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        details = json.loads(result.stdout)[0]
        self.assertEqual(details["min_words_required"], 4)
        self.assertEqual(details["max_words_suggested"], 30)


if __name__ == "__main__":
    unittest.main()
