"""이미 있는 이론에 '눌러 보는 그림'({{diagram:id|캡션}} 한 줄)을 넣는다. (AI 호출 없음, 한 번 돌리면 되고 여러 번 돌려도 안전하다)

  python scripts/add_diagrams.py --dry-run   # 어디에 들어가는지만 보여 줌 (파일 변경 없음)
  python scripts/add_diagrams.py             # data/theories.json, data/draft_theories.json 에 실제로 넣음

그림 줄은 해당 이론의 '[원리]' 파트 끝(팁 박스 바로 앞)에 들어간다. 이미 그 그림이 있는 이론은 건드리지 않는다.
새 그림이 생기면 아래 RULES 에 (id, 이론 제목 조건, 캡션) 을 한 줄 추가하면 된다.
"""
import json
import os
import re
import sys

RULES = [
    ("dram-cell", re.compile(r"^DRAM\b"), "DRAM 셀에서 워드라인과 비트라인 전압이 바뀌며 값을 쓰고 읽는 과정"),
]
FILES = ["data/theories.json", "data/draft_theories.json"]


def insert_diagram(content, did, caption):
    token = "{{diagram:%s|%s}}" % (did, caption)
    if "{{diagram:%s" % did in content:
        return content, False
    lines = content.split("\n")
    heads = [i for i, ln in enumerate(lines) if re.match(r"^###\s*\[", ln)]
    start = next((i for i in heads if re.match(r"^###\s*\[[^\]]*(?:원리|동작|작동)", lines[i])), None)
    if start is None:
        return content, False
    end = next((i for i in heads if i > start), len(lines))
    tip = next((i for i in range(start + 1, end) if lines[i].lstrip().startswith(">")), None)
    at = tip if tip is not None else end
    while at > start + 1 and lines[at - 1].strip() == "":
        at -= 1
    lines[at:at] = ["", token, ""]
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out), True


def main():
    dry = "--dry-run" in sys.argv
    total = 0
    for path in FILES:
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        changed = 0
        for t in data:
            for did, title_re, cap in RULES:
                if title_re.search(str(t.get("title", ""))):
                    new, ok = insert_diagram(str(t.get("content", "")), did, cap)
                    if ok:
                        print(f"  ➕ {path} · {t.get('title')} ({t.get('id')}) ← {did}")
                        t["content"] = new
                        changed += 1
        if changed and not dry:
            json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        total += changed
    print(f"{'(확인만) ' if dry else ''}그림을 넣은 이론: {total}개")


if __name__ == "__main__":
    main()
