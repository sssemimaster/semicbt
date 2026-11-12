"""문제·면접이 모자란 이론에 모자란 만큼만 채워서 '검수 대기열'에 넣는다. (여러 번 돌려도 안전)

- 기본: 검수 대기 중인 이론(draft_theories.json)만 본다.  --include-published: 정식 등재된 이론도 본다.
- 이론 하나당 목표는 객관식 3개, 면접 2개. 정식 목록 + 대기열에 이미 있는 개수를 세고, 모자란 만큼만 만든다.
- 기존 문항과 겹치지 않게 만든다. 새로 만든 문항은 draft_questions.json / draft_interviews.json 에만 들어간다.
- 목표를 다 못 채워도 검수를 통과한 문항은 일단 저장한다(다음에 다시 돌리면 모자란 만큼만 이어서 채움). 하나도 못 만들면 건너뛴다.

사용법 (저장소 루트에서):  python scripts/fill_missing_items.py [--include-published] [--limit 5] [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_all as g  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-published", action="store_true")
    ap.add_argument("--limit", type=int, default=5, help="한 번에 처리할 이론 수 (API 비용 상한)")
    ap.add_argument("--dry-run", action="store_true", help="무엇이 모자란지만 보여 주고 끝")
    a = ap.parse_args()

    load = g.load_json_list
    theories = load(g.draft_t_path) + (load("data/theories.json") if a.include_published else [])
    quizzes = load("data/questions.json") + load(g.draft_q_path)
    interviews = load("data/interviews.json") + load(g.draft_i_path)

    todo = []
    for t in theories:
        if not isinstance(t, dict) or "채워질 예정" in str(t.get("content", "")) or t.get("replaces"):
            continue
        qs = [x for x in quizzes if x.get("theory_id") == t.get("id")]
        its = [x for x in interviews if x.get("theory_id") == t.get("id")]
        nq, ni = max(0, g.QUIZ_PER_THEORY - len(qs)), max(0, g.INTERVIEW_PER_THEORY - len(its))
        if nq or ni:
            todo.append((t, qs, its, nq, ni))

    print(f"문항이 모자란 이론: {len(todo)}개")
    for t, qs, its, nq, ni in todo:
        print(f" - {t.get('title')}: 문제 {len(qs)}/{g.QUIZ_PER_THEORY}, 면접 {len(its)}/{g.INTERVIEW_PER_THEORY}")
    if a.dry_run or not todo:
        return

    for t, qs, its, nq, ni in todo[:a.limit]:
        print(f"\n[{t.get('title')}] 채우는 중... (문제 +{nq}, 면접 +{ni})")
        g.sel_cat, g.target_keyword = t.get("category"), t.get("title")   # compose_* 가 쓰는 값
        new_q, new_i = [], []
        if nq:   # 문제와 면접은 따로 시도한다 (한쪽이 실패해도 다른 쪽 성과는 저장)
            try:
                new_q = g.generate_quiz(t["content"], t["id"], want=nq, existing=qs, allow_partial=True)
            except Exception as e:
                print(f"⚠️ 문제는 못 채웠어요: {e}")
        if ni:
            try:
                new_i = g.generate_interview(t["content"], t["id"], want=ni, existing=its, allow_partial=True)
            except Exception as e:
                print(f"⚠️ 면접은 못 채웠어요: {e}")
        if not (new_q or new_i):
            print("⚠️ 건너뜀(저장 안 함): 검수를 통과한 문항이 없어요")
            continue
        if new_q:
            g.save_draft(g.draft_q_path, new_q)
        if new_i:
            g.save_draft(g.draft_i_path, new_i)
        print(f"✅ 저장: 문제 +{len(new_q)}, 면접 +{len(new_i)}")


if __name__ == "__main__":
    main()
