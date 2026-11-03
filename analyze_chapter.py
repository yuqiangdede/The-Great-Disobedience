#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import re
from pathlib import Path

def analyze_chapter_paragraphs(md_path):
    text = Path(md_path).read_text(encoding="utf-8-sig")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    
    paragraphs = []
    line_no = 0
    for line in lines:
        line_no += 1
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped in ("---", "***", "___", "……", "..."):
            continue
        paragraphs.append((line_no, stripped))
        
    return paragraphs

if __name__ == "__main__":
    if len(sys.argv) > 1:
        p = analyze_chapter_paragraphs(sys.argv[1])
        print(f"Total non-empty non-heading paragraphs: {len(p)}")
        for idx, (lno, text) in enumerate(p[:5], 1):
            print(f"P{idx:03d} (Line {lno}): {text[:60]}")
