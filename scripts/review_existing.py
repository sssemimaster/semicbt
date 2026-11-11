"""이미 등재된 문제·면접을 새 검수 기준으로 다시 점검해서 '검수 대기열'에 넣는다.

- 정식 목록(questions.json / interviews.json)은 절대 건드리지 않는다.
- 고칠 점이 있는 문항은 고친 버전을 draft 에 넣고, `replaces`(기존 문항 ID)와 `report_note`(문제점)를 붙인다.
  → 검수소에서 [등재]하면 기존 문항이 새 문항으로 교체된다.
- 고쳐서 살릴 수 없는 문항은 원본을 draft 에 넣고 '삭제 권장' 표시를 붙인다.
  → 검수소에서 [폐기] 후 '기존 문항도 삭제'를 확인하면 정식 목록에서 지워진다.
- 문제 없는 문항(verdict=ok)은 아무것도 하지 않는다.

사용법 (저장소 루트에서):  python scripts/review_existing.py --kind all --limit 12
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_all as g  # noqa: E402  (같은 프롬프트·규칙을 그대로 재사용)

BATCH = 4
NO_THEORY = "(연결된 이론 글이 없습니다. 반도체 교과서·업계 상식으로 판단하고, 확실하지 않은 내용은 drop 하세요.)"


def norm(x):
    return re.sub(r"\s+", "", str(x or ""))


def find_theory(item, theories):
    tid = item.get("theory_id")
    if tid:
        for t in theories:
            if t.get("id") == tid:
                return t
    topic = norm(item.get("topic"))
    if topic:
        for t in theories:
            title = norm(t.get("title"))
            if title and (title in topic or topic in title):
                return t
    return None


def quiz_to_review(q):
    opts, ans = q.get("options") or [], q.get("answer")
    if not isinstance(ans, int) or not (0 <= ans < len(opts)):
        raise ValueError("answer/options 형식 오류")
    return {
        "type": "concept", "difficulty": q.get("difficulty", "중급"), "question": q["question"],
        "correct": opts[ans],
        "distractors": [{"text": o, "why_wrong": ""} for n, o in enumerate(opts) if n != ans],
        "why_correct": q.get("explanation", ""), "takeaway": "",
    }


def interview_to_review(i):
    return {
        "difficulty": i.get("difficulty", "고급"), "question": i["question"], "follow_up": i.get("follow_up", ""),
        "follow_up_answer": i.get("follow_up_answer", ""), "key_points": i.get("key_points") or [],
        "interview_answer": i.get("interview_answer", ""),
    }


def groups_of(items, theories):
    """같은 이론에 묶이는 문항끼리 BATCH 개씩 나눈다."""
    by = {}
    for it in items:
        th = find_theory(it, theories)
        by.setdefault(th.get("id") if th else None, (th, []))[1].append(it)
    for th, lst in by.values():
        for k in range(0, len(lst), BATCH):
            yield th, lst[k:k + BATCH]


def run_kind(kind, limit, theories):
    live_path = "data/questions.json" if kind == "quiz" else "data/interviews.json"
    draft_path = g.draft_q_path if kind == "quiz" else g.draft_i_path
    live = g.load_json_list(live_path)
    queued = {d.get("replaces") for d in g.load_json_list(draft_path) if d.get("replaces")}
    todo = [x for x in live if isinstance(x, dict) and x.get("id") not in queued][:limit]
    label = "객관식" if kind == "quiz" else "면접"
    print(f"[{label}] 정식 {len(live)}개 중 이번에 점검할 문항 {len(todo)}개 (이미 대기열에 있는 {len(queued)}개 제외)")
    out, stats = [], {"ok": 0, "fix": 0, "drop": 0, "skip": 0}

    for th, batch in groups_of(todo, theories):
        theory_text = th["content"] if th else NO_THEORY
        conv, olds = [], []
        for old in batch:
            try:
                conv.append(quiz_to_review(old) if kind == "quiz" else interview_to_review(old)); olds.append(old)
            except Exception as e:
                print(f"   ⚠️ {old.get('id')} 변환 실패, 건너뜀: {e}"); stats["skip"] += 1
        if not conv:
            continue
        try:
            if kind == "quiz":
                prompt, system = g.build_quiz_review_prompt(theory_text, conv), g.QUIZ_REVIEW_SYSTEM
            else:
                prompt, system = g.build_interview_review_prompt(theory_text, conv), g.INTERVIEW_REVIEW_SYSTEM
            reviews = g.call_json(g.CHECK_MODEL, system, prompt, 0.2, 4500).get("reviews") or []
        except Exception as e:
            print(f"   ⚠️ 검수 호출 실패, 이 묶음은 다음에 다시 시도됩니다: {e}"); stats["skip"] += len(olds); continue
        by_idx = {r.get("index"): r for r in reviews if isinstance(r, dict)}

        for n, old in enumerate(olds):
            r = by_idx.get(n) or {}
            verdict, issues = r.get("verdict"), "; ".join(map(str, r.get("issues") or []))[:300]
            before = str(old.get("question", ""))[:160]
            if verdict == "ok" or verdict not in ("fix", "drop"):
                stats["ok"] += 1; continue
            if verdict == "drop":
                stats["drop"] += 1
                out.append(dict(old, replaces=old["id"], before=before, report_note=f"삭제 권장 — {issues or '고쳐서 살리기 어려움'}"))
                print(f"   🗑️ {old['id']} 삭제 권장: {issues[:80]}"); continue
            cand = r.get("final")
            probs = (g.check_quiz_item(cand) if kind == "quiz" else g.check_interview_item(cand)) if isinstance(cand, dict) else ["final 없음"]
            if probs:
                print(f"   ⚠️ {old['id']} 수정안이 규칙 위반이라 건너뜀: {probs}"); stats["skip"] += 1; continue
            g.sel_cat, g.target_keyword = old.get("category", ""), old.get("topic", "")
            new = g.compose_quiz(cand, old.get("theory_id")) if kind == "quiz" else g.compose_interview(cand, old.get("theory_id"))
            if not old.get("theory_id"):
                new.pop("theory_id", None)
            new.update(replaces=old["id"], before=before, report_note=issues or "표현·해설 보강")
            out.append(new); stats["fix"] += 1
            print(f"   🔧 {old['id']} 수정안 생성: {issues[:80]}")

    if out:
        g.save_draft(draft_path, out)
    print(f"→ {label}: 수정안 {stats['fix']} · 삭제 권장 {stats['drop']} · 이상 없음 {stats['ok']} · 건너뜀 {stats['skip']}")
    return len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["quiz", "interview", "all"], default="all")
    ap.add_argument("--limit", type=int, default=12, help="종류별로 한 번에 점검할 문항 수")
    a = ap.parse_args()
    theories = [t for t in g.load_json_list("data/theories.json") if isinstance(t, dict) and "채워질 예정" not in str(t.get("content", ""))]
    total = 0
    for kind in (["quiz", "interview"] if a.kind == "all" else [a.kind]):
        total += run_kind(kind, a.limit, theories)
    print(f"✅ 검수 대기열에 {total}개를 넣었습니다. 검수소에서 확인하세요." if total else "✅ 새로 넣을 문항이 없습니다.")


if __name__ == "__main__":
    main()
