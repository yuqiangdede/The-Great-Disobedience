#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行：python -m unittest discover -s .agents/skills/chinese-novelist/scripts -p 'test_novel_style_statistics.py'"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import novel_style_statistics as style


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_lines_and_repetition(self):
        p = self.make("a.md", "# 第一章\n\n　　队长把灯放在桌角，知道电池只剩半格。\n\n　　陈渡把灯放在桌角，知道电池只剩半格。\n")
        chunks = style.paragraphs(p)
        self.assertEqual([x["line"] for x in chunks], [3, 5])
        candidates, totals = style.scan(chunks)
        self.assertTrue(any(i["type"] == "跨段连续表达复现" and i["line"] == 5 for i in candidates))
        self.assertTrue(totals["跨段连续表达复现"]["total"] >= 1)

    def test_insufficient_baseline(self):
        p = self.make("a.md", "陈渡检查了两次弹仓。")
        m = style.metrics(style.paragraphs(p))
        result = style.baseline_compare(m, [p])
        self.assertEqual(result["status"], "INSUFFICIENT")

    def test_no_network_without_opt_in(self):
        p = self.make("a.md", "陈渡关掉电台。")
        with patch("novel_style_statistics.zhuque_check", side_effect=RuntimeError("unexpected network")):
            self.assertEqual(style.main([str(p), "--json"]), 0)

    def test_outline_rejected(self):
        p = self.make("outline.md", "概要：边境驻地前线遭遇封锁。")
        with self.assertRaises(SystemExit) as ctx:
            style.main([str(p), "--mode", "outline"])
        self.assertEqual(ctx.exception.code, 2)

    def test_zhuque_key_missing(self):
        with patch.dict("os.environ", {"MAKERS_MODELS_KEY": ""}):
            self.assertEqual(style.zhuque_check([{"text": "正文"}])["status"], "SKIPPED")


if __name__ == "__main__":
    unittest.main()
