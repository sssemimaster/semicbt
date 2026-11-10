import json
import shutil
import sys
import uuid
 
APPLY = "--apply" in sys.argv
 
FILES = [
    ("data/questions.json", "Q", "question"),
    ("data/interviews.json", "INT", "question"),
    ("data/theories.json", "TH", "title"),
]
 
 
def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
 
 
for path, prefix, text_key in FILES:
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        print(f"- {path}: 파일 없음, 건너뜀")
        continue
 
    seen = set()
    changed = 0
    for item in items:
        cur = item.get("id")
        if not cur or cur in seen:
            item["id"] = new_id(prefix)
            changed += 1
        seen.add(item["id"])
 
    texts = {}
    for item in items:
        key = " ".join(str(item.get(text_key, "")).split())
        texts.setdefault(key, []).append(item["id"])
    same = {k: v for k, v in texts.items() if k and len(v) > 1}
 
    print(f"- {path}: 총 {len(items)}개 / 새 ID 부여 {changed}개 / 내용이 같은 항목 묶음 {len(same)}개")
    for k, ids in list(same.items())[:10]:
        print(f"    · {k[:50]}... -> {ids}")
 
    if APPLY and changed:
        shutil.copyfile(path, path + ".bak")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print("    ✔ 저장 완료 (백업: %s.bak)" % path)
 
if not APPLY:
    print("\n미리보기였습니다. 실제로 고치려면 --apply 를 붙여 다시 실행하세요.")
