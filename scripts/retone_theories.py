"""이미 등재된 이론의 문체를 평서체(~한다, ~이다, ~된다)로 바꿔 '검수 대기열'에 넣는다. (일회성 변환 도구)

- 정식 목록(theories.json)은 건드리지 않는다.
- 해요체/합니다체 어미가 많은 이론만 골라, 내용·구조·소제목·표·수식은 그대로 두고 어미만 바꾼 버전을 draft 에 넣는다.
  초안은 기존 이론과 같은 id 를 쓰고 `replaces` 를 달아 둔다 → 검수소에서 [등재]하면 같은 자리에서 기존 이론이 교체되고,
  이 이론에 연결된 문제·면접(theory_id)도 그대로 이어진다.
- 변환이 원문을 훼손했는지(소제목·표·수식 개수, 분량) 코드로 확인하고, 어긋나면 한 번 다시 시도한 뒤 건너뛴다.
- 변환한 이론은 data/retone_log.json 에 기록해 다시 변환하지 않는다.

사용법 (저장소 루트에서):  python scripts/retone_theories.py --limit 5
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_all as g  # noqa: E402

LOG_PATH = "data/retone_log.json"
MIN_HITS = 3          # 해요체/합니다체 어미가 이 정도 이상 있어야 변환 대상
MAX_SKIPS = 2         # 두 번 실패한 이론은 더 시도하지 않음

RETONE_SYSTEM = """당신은 학습서 편집자입니다. 받은 반도체 학습 글의 '문체'만 평서체로 바꿉니다. 내용은 바꾸지 않습니다.

[바꾸는 것]
- 문장 끝의 해요체(~해요, ~예요, ~거든요, ~죠)와 합니다체(~합니다, ~입니다)를 평서체(~한다, ~이다, ~된다, ~있다, ~않는다)로 바꿉니다.
- 소제목·팁 박스·불릿·표 안의 문장도 같은 문체로 맞춥니다. 소제목이 의문형이면 평서문이나 명사구로 바꿉니다.
- 평서체로 바꾸며 어색해진 앞뒤 연결어만 최소한으로 다듬습니다.

[절대 바꾸지 않는 것]
- 사실, 수치, 용어, 문장 순서, 문단 구성, 분량. 내용을 더하거나 빼거나 요약하지 않습니다.
- 마크다운 구조: `### [뱃지] 제목` 소제목의 [뱃지], 표, 불릿, `> 💡 [..]` 인용문 형식, **굵게**, 수식($...$, $$...$$)과 LaTeX 기호.
- 영문 병기, 괄호 표기.

출력은 변환한 마크다운 본문만 씁니다. 설명, 인사, 코드블록 감싸기는 쓰지 않습니다."""


def load_log():
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_log(log):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1, sort_keys=True)


def skeleton(text):
    """내용 훼손 여부를 보기 위한 구조 지표."""
    return {
        "headings": len(re.findall(r"^###", text, re.M)),
        "badges": re.findall(r"^###\s*\[([^\]]+)\]", text, re.M),
        "table_rows": len(re.findall(r"^\s*\|", text, re.M)),
        "display_math": text.count("$$"),
        "inline_math": text.replace("$$", "").count("$"),
        "quotes": len(re.findall(r"^>", text, re.M)),
        "bullets": len(re.findall(r"^\s*[-*]\s", text, re.M)),
    }


def check_conversion(old, new):
    """문제점 문자열 목록. 비어 있으면 통과."""
    probs = []
    ph = g.polite_hits(new)
    if ph:
        probs.append(f"해요체/합니다체 어미가 {ph}번 남아 있음")
    a, b = skeleton(old), skeleton(new)
    for k in a:
        if a[k] != b[k]:
            probs.append(f"구조가 달라짐: {k} {a[k]} → {b[k]}" if not isinstance(a[k], list) else f"뱃지가 달라짐: {a[k]} → {b[k]}")
    ratio = len(new) / max(1, len(old))
    if not 0.85 <= ratio <= 1.15:
        probs.append(f"분량이 크게 달라짐 (원문의 {ratio:.0%})")
    return probs


def convert(text):
    last = None
    for attempt in (1, 2):
        feedback = f"\n\n[직전 변환의 문제 - 이번에는 고쳐서 변환하세요]\n{last}" if last else ""
        res = g.client.chat.completions.create(
            model=g.M["review"],
            messages=[{"role": "system", "content": RETONE_SYSTEM}, {"role": "user", "content": text + feedback}],
            temperature=0.1, max_tokens=7000,
        )
        ch = res.choices[0]
        if ch.finish_reason == "length":
            last = "출력이 잘림 (원문 전체를 빠짐없이 변환)"
            continue
        new = g.normalize_markdown(ch.message.content or "")
        probs = check_conversion(text, new)
        if not probs:
            return new
        last = "; ".join(probs)
        print(f"   ↻ 변환 재시도 {attempt}/2: {last}")
    raise ValueError(last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="한 번에 변환할 이론 수")
    a = ap.parse_args()
    live = [t for t in g.load_json_list("data/theories.json") if isinstance(t, dict)]
    queued = {d.get("replaces") for d in g.load_json_list(g.draft_t_path) if d.get("replaces")}
    log = load_log()
    pool = []
    for t in live:
        c = str(t.get("content", ""))
        rec = log.get(t.get("id"), {})
        if "채워질 예정" in c or t.get("id") in queued or rec.get("v") == "done" or rec.get("n", 0) >= MAX_SKIPS:
            continue
        if g.polite_hits(c) >= MIN_HITS:
            pool.append(t)
    todo = pool[:a.limit]
    print(f"[이론 문체 변환] 정식 {len(live)}편 중 변환 대상 {len(pool)}편 → 이번에 {len(todo)}편 (대기열 {len(queued)}편 제외)")
    out = []
    for t in todo:
        try:
            new = convert(str(t["content"]))
        except Exception as e:
            rec = log.get(t["id"], {}); log[t["id"]] = {"v": "skip", "n": rec.get("n", 0) + 1}
            print(f"   ⚠️ {t['id']} {t.get('title', '')} 변환 실패, 건너뜀: {e}")
            continue
        log[t["id"]] = {"v": "done"}
        out.append(dict(t, content=new, replaces=t["id"], report_note="문체 변환 (해요체·합니다체 → 평서체). 내용·구조·수식은 그대로이고 문장 끝만 바뀌었습니다."))
        print(f"   ✏️ {t['id']} {t.get('title', '')} 변환 완료")
    if out:
        g.save_draft(g.draft_t_path, out)
    save_log(log)
    print(f"✅ 검수 대기열에 이론 {len(out)}편을 넣었습니다. 검수소에서 확인하세요." if out else "✅ 새로 넣을 이론이 없습니다.")


if __name__ == "__main__":
    main()
