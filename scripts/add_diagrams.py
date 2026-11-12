"""이미 있는 이론에 '눌러 보는 그림'({{diagram:id|캡션}} 한 줄)을 넣는다. (AI 호출 없음, 여러 번 돌려도 안전하다)

  python scripts/add_diagrams.py --dry-run   # 어디에 들어가는지만 보여 줌 (파일 변경 없음)
  python scripts/add_diagrams.py             # data/theories.json, data/draft_theories.json 에 실제로 넣음

어떤 이론에 어떤 그림을 붙일지는 scripts/diagram_rules.py 의 RULES 에 있다. 이미 그림이 있는 이론은 건드리지 않는다.
"""
import json
import os
import sys

from diagram_rules import ensure_diagrams

FILES = ["data/theories.json", "data/draft_theories.json"]


def main():
    dry = "--dry-run" in sys.argv
    total = 0
    for path in FILES:
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        changed = 0
        for t in data:
            new, added = ensure_diagrams(t.get("title", ""), str(t.get("content", "")))
            if added:
                print(f"  ➕ {path} · {t.get('title')} ({t.get('id')}) ← {', '.join(added)}")
                t["content"] = new
                changed += 1
        if changed and not dry:
            json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        total += changed
    print(f"{'(확인만) ' if dry else ''}그림을 넣은 이론: {total}개")


if __name__ == "__main__":
    main()
