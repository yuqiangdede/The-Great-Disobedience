#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用小说项目配置：从项目根目录读取小说专属参数。"""
import json
from pathlib import Path

FILENAME = "novel.project.json"
DEFAULT_WRITING = {"brief_target_han": 500, "chapter_min_han": 3000,
                   "chapter_max_han": 5000, "interlude_unbounded": False,
                   "author_approval_required": True}
DEFAULT_REVIEW = {"travel_location_terms": ["千里", "数百里"],
                  "instant_travel_terms": ["顷刻间", "瞬息", "眨眼之间", "半盏茶", "片刻便已抵达", "数步之内"],
                  "repeated_equipment_terms": []}


def project_root(start):
    path = Path(start).resolve()
    if path.is_file():
        path = path.parent
    for current in (path, *path.parents):
        if (current / FILENAME).is_file():
            return current
    for current in (path, *path.parents):
        if (current / "AGENTS.md").is_file():
            return current
    return path


def load_project_config(start):
    root = project_root(start)
    path = root / FILENAME
    if not path.exists():
        return {"schema_version": 1, "writing": dict(DEFAULT_WRITING),
                "review": dict(DEFAULT_REVIEW), "paths": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"项目配置无法解析 {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError(f"{path}: schema_version 必须为 1")
    config = dict(raw)
    for group, defaults in (("writing", DEFAULT_WRITING), ("review", DEFAULT_REVIEW)):
        values = raw.get(group, {})
        if not isinstance(values, dict):
            raise ValueError(f"{path}: {group} 必须是对象")
        config[group] = {**defaults, **values}
    w = config["writing"]
    for key in ("brief_target_han", "chapter_min_han", "chapter_max_han"):
        if type(w[key]) is not int or w[key] < 0:
            raise ValueError(f"{path}: writing.{key} 必须是非负整数")
    if w["chapter_min_han"] > w["chapter_max_han"]:
        raise ValueError(f"{path}: 字数下限不得超过上限")
    for key in ("interlude_unbounded", "author_approval_required"):
        if type(w[key]) is not bool:
            raise ValueError(f"{path}: writing.{key} 必须是布尔值")
    for key in DEFAULT_REVIEW:
        values = config["review"][key]
        if not isinstance(values, list) or not all(isinstance(x, str) and x.strip() for x in values):
            raise ValueError(f"{path}: review.{key} 必须是字符串列表")
    paths = config.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError(f"{path}: paths 必须是对象")
    return config


def chapter_limits(chapter, project_dir=None, min_words=None, max_words=None):
    config = load_project_config(project_dir or chapter)
    w = config["writing"]
    if "插章" in Path(chapter).stem and w["interlude_unbounded"]:
        return (0 if min_words is None else min_words, 0 if max_words is None else max_words)
    return (w["chapter_min_han"] if min_words is None else min_words,
            w["chapter_max_han"] if max_words is None else max_words)


def project_file(start, key):
    config = load_project_config(start)
    rel = config.get("paths", {}).get(key)
    if not rel:
        return None
    root = project_root(start)
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"配置 paths.{key} 不得越过小说根目录: {rel}")
    return target
