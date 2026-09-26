#!/usr/bin/env python3
"""Read-only candidate finder. A clean report is NOT a grammar verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import re

RULES = [
    ("P-DUP", r"([，、；：。])\1+", "相同点号连写；检查是否误输入。"),
    ("P-ELLIPSIS", r"(?<!\.)\.{3,}(?!\.)|(?<!…)…(?!…)", "检查中文省略号形式；代码、英文及数学省略另判。"),
    ("P-ETC", r"(?:等等?|诸如此类)[，、 ]*……|……[，、 ]*(?:等等?|诸如此类)", "若同指列举未尽，检查是否重复；其他语用功能可保留。"),
    ("Q-APPROX", r"(?:约|大约|大概|近)\s*\d+(?:\.\d+)?\s*(?:[%％]|万|亿|人|个|名|次|年|月|天|小时)?\s*(?:左右|上下)", "可能叠用概数标记，先确认指向同一个数量。"),
    ("Q-REDUCE", r"(?:降低|减少|下降|缩减)(?:了)?\s*(?:[一二三四五六七八九十百]+|\d+(?:\.\d+)?)倍", "数量减少与倍数关系需核算；不得直接替换为50%。"),
    ("S-BLEND", r"原因(?:主要)?是[^。！？；\n]{1,70}(?:所)?造成的", "疑似原因是/由…造成两种框架混用，须读完整句。"),
    ("S-FRAME", r"围绕以[^。！？；\n]{1,45}为中心", "疑似围绕/以…为中心结构混用，须结合完整结构。"),
    ("W-REPEAT", r"的的|地地|得得", "叠字候选；专名、引用、拟声或有意重复需排除。"),
]

PAIRS = {"（": "）", "【": "】", "《": "》", "〈": "〉", "“": "”", "‘": "’"}


def scan(text):
    findings = []
    offset = 0
    fenced = False
    fence_char = None
    fence_len = 0
    stack = []
    for number, raw in enumerate(text.splitlines(keepends=True), 1):
        line = raw.rstrip("\r\n")
        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            marker = fence.group(1)
            if not fenced:
                fenced, fence_char, fence_len = True, marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                fenced = False
            offset += len(raw)
            continue
        if fenced:
            offset += len(raw)
            continue
        # Preserve character columns while excluding simple inline code and URLs.
        clean = re.sub(r"`[^`\n]+`|https?://\S+", lambda m: " " * len(m.group()), line)

        def add(rule, col, snippet, note):
            findings.append({"rule": rule, "line": number, "column": col + 1,
                             "offset": offset + col, "snippet": snippet,
                             "status": "needs_context_review", "note": note})

        for rule, pattern, note in RULES:
            for match in re.finditer(pattern, clean):
                add(rule, match.start(), match.group(), note)
        for col, char in enumerate(clean):
            if char in PAIRS:
                stack.append((char, number, col + 1, offset + col))
            elif char in PAIRS.values():
                if stack and PAIRS[stack[-1][0]] == char:
                    stack.pop()
                else:
                    add("P-PAIR", col, char, "配对符号未按嵌套顺序闭合；跨段引语、编号和摘录须人工判断。")
        offset += len(raw)
    for char, line, col, pos in stack:
        findings.append({"rule": "P-PAIR", "line": line, "column": col, "offset": pos,
                         "snippet": char, "status": "needs_context_review",
                         "note": "未找到对应闭符号；跨段长引语可每段重开引号，不能据此自动补号。"})
    return sorted(findings, key=lambda item: (item["offset"], item["rule"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="UTF-8 plain text or Markdown; source is never modified")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    raw = args.path.read_bytes()
    text = raw.decode("utf-8-sig")
    findings = scan(text)
    report = {
        "schema_version": 1,
        "source": str(args.path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "scope": "limited_surface_candidates_only",
        "semantic_review_completed": False,
        "warning": "候选不等于错误；零候选不等于没有病句。未改写源文件。",
        "candidate_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
