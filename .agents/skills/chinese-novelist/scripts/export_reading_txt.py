#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从正文 Markdown 生成逐章 TXT 阅读版与分卷合订本（仅标准库）。"""
import argparse
import re
from pathlib import Path

CHAPTER = re.compile(r"^第(\d+)章(?:[-_ ].*)?\.md$")
INTERLUDE = re.compile(r"^插(?:章)?(\d{3})(?:[-_ ].*)?\.md$")  # 兼容既有“插章NNN”和“插NNN”命名
SCENE = re.compile(r"^(?:\*\s*\*\s*\*+|-{3,}|_{3,})$")

def order(path):
    chapter = CHAPTER.fullmatch(path.name)
    if chapter:
        return int(chapter.group(1)), 0, path.name
    insert = INTERLUDE.fullmatch(path.name)
    if insert:
        return int(insert.group(1)), 1, path.name
    raise ValueError("无法识别章节/插章文件名: " + path.name)

def inline(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    for p in [r"\x60([^\x60]*)\x60", r"\*\*([^*]+)\*\*", r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"__([^_]+)__", r"~~([^~]+)~~"]:
        text = re.sub(p, r"\1", text)
    return text.strip()

def txt_filename(md_path, title, chapter_offset=0):
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title).strip()
    chapter = CHAPTER.fullmatch(md_path.name)
    if chapter:
        if re.match(r"^第\d+章", safe_title):
            return safe_title + ".txt"
        return f"{md_path.stem} {safe_title}".strip() + ".txt"
    insert = INTERLUDE.fullmatch(md_path.name)
    if insert:
        if chapter_offset:
            local_number = int(insert.group(1)) - chapter_offset
            return re.sub(r'^(插(?:章)?)\d{3}', lambda match: match.group(1) + f'{local_number:03d}', md_path.stem) + '.txt'
        if re.match(r"^插(?:章)?\d{3}[-_ ].+", md_path.stem):
            return md_path.stem + ".txt"
        return f"{md_path.stem}-{safe_title}".strip() + ".txt"
    return md_path.stem + ".txt"

def chapter_txt(markdown, fallback):
    title, body, seen = fallback, [], False
    for line in markdown.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").split("\n"):
        value = line.strip()
        if not value:
            continue
        if SCENE.fullmatch(value):
            if body and body[-1] != "":
                body.append("")
            continue
        h = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", value)
        if h:
            val = h.group(1).strip()
            if not seen and (re.match(r"^第\d+章", val) or val.startswith("插章") or val.startswith("插")):
                title, seen = inline(val), True
                continue
        body.append("\u3000\u3000" + inline(value))
    while body and body[-1] == "":
        body.pop()
    body_txt = "\n".join(body) + "\n" if body else ""
    return title, body_txt

def write(path, text, check):
    old = path.read_text(encoding="utf-8-sig") if path.is_file() else None
    if old == text:
        return True
    if check:
        print("不同步:", path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("生成:", path)
    return True

def main():
    p = argparse.ArgumentParser(description="同步/校验小说 TXT 阅读副本")
    p.add_argument("--project-dir", default=".")
    p.add_argument("--source", default=None, help="Markdown 正文目录")
    p.add_argument("--output", default=None, help="TXT 输出目录")
    p.add_argument("--book-title", default=None)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--chapter", help="同步指定章节与对应合订本")
    mode.add_argument("--all", action="store_true", help="同步所有章节（默认）")
    p.add_argument("--check", action="store_true", help="只校验，不写入")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    src = (root / (a.source or ("06-正文" if (root / "06-正文").is_dir() else "正文"))).resolve()
    out = (root / a.output).resolve() if a.output else src.with_name(src.name + "-TXT")
    if not src.is_dir():
        p.error("正文目录不存在: " + str(src))
    if src == out or src in out.parents or out in src.parents:
        p.error("输出目录不能与源目录重叠")
    chapters = sorted([f for f in src.rglob("*.md") if CHAPTER.fullmatch(f.name) or INTERLUDE.fullmatch(f.name)], key=lambda f: (str(f.parent.relative_to(src)), order(f)))
    if not chapters:
        p.error("没有找到 Markdown 章节")
    if a.chapter:
        selected = (root / a.chapter).resolve()
        if selected not in chapters:
            p.error("指定章节不在正文目录中: " + str(selected))
        volumes, selected_files = {selected.parent}, {selected}
    else:
        volumes, selected_files = {f.parent for f in chapters}, set(chapters)
    readme = root / "README.md"
    match = re.search(r"《([^》\n]+)》", readme.read_text(encoding="utf-8-sig")) if readme.is_file() else None
    book = a.book_title or (match.group(1) if match else root.name)
    ok = True
    for volume in sorted(volumes):
        members = sorted([f for f in chapters if f.parent == volume], key=order)
        chapter_numbers = [int(CHAPTER.fullmatch(f.name).group(1)) for f in members if CHAPTER.fullmatch(f.name)]
        chapter_offset = 0
        if chapter_numbers:
            first = min((f for f in members if CHAPTER.fullmatch(f.name)), key=order)
            first_title, _ = chapter_txt(first.read_text(encoding="utf-8-sig"), first.stem)
            first_number = re.match(r"^第(\d+)章", first_title)
            if first_number:
                chapter_offset = int(CHAPTER.fullmatch(first.name).group(1)) - int(first_number.group(1))
        relative = volume.relative_to(src)
        texts = []
        target_names = {}
        for md in members:
            title, body = chapter_txt(md.read_text(encoding="utf-8-sig"), md.stem)
            chapter_match = CHAPTER.fullmatch(md.name)
            if chapter_match and title == md.stem and chapter_offset:
                title = f"第{int(chapter_match.group(1)) - chapter_offset:03d}章"
            target_name = txt_filename(md, title, chapter_offset)
            target_names[md] = target_name
            combined_entry = title + "\n\n" + body.rstrip("\n")
            texts.append(combined_entry)
            if md in selected_files:
                ok = write(out / relative / target_name, body, a.check) and ok
        label = volume.name if relative != Path(".") else "正文"
        combined = "《" + book + "》\n" + label + "\n\n" + "\n\n".join(texts) + "\n"
        ok = write(out / relative / ("《" + book + "》" + label + ".txt"), combined, a.check) and ok
        folder = out / relative
        if not a.chapter:
            names = set(target_names.values())
            if folder.is_dir():
                for stale in list(folder.glob("第*章*.txt")) + list(folder.glob("插*.txt")):
                    if (re.match(r"^第\d+章", stale.name) or INTERLUDE.fullmatch(stale.name.replace(".txt", ".md"))) and stale.name not in names:
                        if a.check:
                            print("过期副本:", stale)
                            ok = False
                        else:
                            stale.unlink()
        else:
            if folder.is_dir():
                for md in selected_files:
                    target_name = target_names[md]
                    c_match = CHAPTER.fullmatch(md.name)
                    i_match = INTERLUDE.fullmatch(md.name)
                    if c_match:
                        num = re.match(r"^第(\d+)章", target_name).group(1)
                        for old_f in folder.glob(f"第{num}章*.txt"):
                            if old_f.name != target_name:
                                if a.check:
                                    print("过期副本:", old_f)
                                    ok = False
                                else:
                                    old_f.unlink()
                    elif i_match:
                        num = INTERLUDE.fullmatch(target_name[:-4] + ".md").group(1)
                        for old_f in list(folder.glob(f"插章{num}*.txt")) + list(folder.glob(f"插{num}*.txt")):
                            if old_f.name != target_name:
                                if a.check:
                                    print("过期副本:", old_f)
                                    ok = False
                                else:
                                    old_f.unlink()
    if ok:
        print("TXT 同步校验通过：%d 章，%d 卷" % (len(selected_files), len(volumes)))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
