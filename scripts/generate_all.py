import os
import json
import random
import re
import uuid
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 이론 생성에 쓸 모델 (품질을 더 올리고 싶으면 "gpt-4o" 등으로 교체)
THEORY_MODEL = "gpt-4o-mini"

topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "keywords": ["에너지 밴드", "페르미 준위", "캐리어 농도", "PN 접합", "유효 질량"]},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자", "keywords": ["MOSFET", "채널 길이 변조", "단채널 효과 (SCE)", "누설 전류", "문턱 전압"]},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "keywords": ["건식 식각", "플라즈마 식각", "식각 선택비", "Bowing 현상"]},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)", "keywords": ["CVD 공정", "ALD 공정", "PVD 공정", "단차 피복성"]}
]

draft_t_path = "data/draft_theories.json"
draft_q_path = "data/draft_questions.json"
draft_i_path = "data/draft_interviews.json"

MAX_PENDING_DRAFTS = 10  # 검수 대기 이론이 이 개수 이상이면 생성을 건너뜀 (API 비용 낭비 방지)


def new_id(prefix):
    """충돌 가능성이 거의 없는 고유 ID (예: Q-3fa9c1d2)"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def load_json_list(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def pick_topic():
    """이미 등재됐거나 검수 대기 중인 키워드는 제외하고 고른다. 남은 키워드가 없으면 None."""
    used = {
        re.sub(r"\s+", "", str(t.get("title", "")))
        for p in ("data/theories.json", draft_t_path)
        for t in load_json_list(p)
        if isinstance(t, dict)
    }
    pool = [
        (t, kw) for t in topics for kw in t["keywords"]
        if re.sub(r"\s+", "", kw) not in used
    ]
    return random.choice(pool) if pool else None


_picked = pick_topic()
if _picked:
    selected, target_keyword = _picked
    sel_cat, sel_sub = selected["category"], selected["subject"]
else:
    selected = target_keyword = sel_cat = sel_sub = None


def clean_json_string(raw_str):
    cleaned = raw_str.replace("```json", "").replace("```", "").strip()
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', cleaned)
    return cleaned


def save_draft(path, new_data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    existing = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            try:
                existing = json.loads(content)
            except json.JSONDecodeError:
                # 기존 파일이 깨져 있으면 조용히 덮어써서 날리지 말고 백업부터 남긴다
                backup = path + ".bak"
                with open(backup, "w", encoding="utf-8") as b:
                    b.write(content)
                print(f"⚠️ 기존 {path} 파싱 실패 → {backup} 로 백업 후 새로 작성")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(new_data + existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ====================================================================
# 📖 이론 3단계 분할 생성
#   - 각 호출은 JSON이 아니라 '마크다운 본문'만 받는다.
#     (수식 백슬래시/따옴표 이스케이프 문제가 구조적으로 사라짐)
#   - JSON은 파이썬에서 조립해서 json.dump로 저장한다.
#   - 2, 3단계에는 앞 파트 내용을 넘겨 중복을 막고 용어·기호를 일관되게 유지한다.
# ====================================================================
THEORY_SYSTEM = """당신은 반도체 공정·소자 분야 10년차 현직 엔지니어이자, 기사/면접 대비 이론 요약 노트를 쓰는 강사입니다.
'양파 CBT 이론 노트'처럼 군더더기 없이 핵심만 짚는 깔끔한 스타일로 작성합니다.

[문체]
- 한국어 개조식 위주로 쓰고, 한 문단은 최대 3~4문장으로 제한합니다. 길어지면 불릿이나 표로 쪼갭니다.
- 핵심 용어는 **굵게** 표시하고, 영문 전문용어는 처음 한 번만 괄호로 병기합니다. 예: 식각 선택비(Selectivity)
- 비교·분류 내용은 마크다운 표로 정리합니다.
- 수식은 LaTeX로 쓰고, 인라인은 $...$, 독립 수식은 $$...$$ 로 감쌉니다. 백슬래시는 평소처럼 한 개만 씁니다. 예: $\\sigma$, $$I_D = \\frac{1}{2}\\mu C_{ox}\\frac{W}{L}(V_{GS}-V_{th})^2$$
- 확실하지 않은 구체 수치는 지어내지 말고, 증가/감소 같은 경향이나 정성적 표현으로 씁니다.

[형식]
- 출력은 마크다운 본문만 쓰세요. JSON, 서두 인사, 맺음말, 최상위 제목(#, ##)은 쓰지 않습니다.
- 전체를 코드블록(```)으로 감싸지 않습니다.
- 소제목은 `### [뱃지] 제목` 형식입니다. 예: `### [핵심 개념] 식각 선택비란?`
- 인라인 팁은 `> 💡 [실무 코멘트] ...` 또는 `> 💡 [면접 팁] ...` 처럼 한 줄 인용문으로 씁니다."""

THEORY_PARTS = [
    {
        "no": 1,
        "name": "개념 & 원리",
        "badges": "[핵심 개념], [정의], [등장 배경], [원리]",
        "tip": "[면접 팁]",
        "guide": """- 이 파트의 역할: 처음 보는 사람도 이해할 수 있는 '뼈대'입니다.
- 반드시 포함: (1) 한두 문장의 정의 (2) 왜 필요한지, 어디에 쓰이는지 (3) 동작 원리를 단계 또는 인과 관계로 설명
- 소제목 2~3개, 전체 약 700~1,000자.
- 수식, 세부 분류, 장단점, 실무 이슈는 다음 파트에서 다루므로 여기서는 쓰지 않습니다.""",
        "min_headings": 2,
        "min_chars": 400,
        "last_badge": None,
    },
    {
        "no": 2,
        "name": "세부 메커니즘 & 분류/수식",
        "badges": "[메커니즘], [수식], [분류], [비교], [변수 영향]",
        "tip": "[실무 코멘트]",
        "guide": """- 이 파트의 역할: 시험과 면접에서 구체적으로 묻는 '세부 내용'입니다.
- 반드시 포함: 마크다운 표 1개 이상. 단, '종류/분류' 표는 교과서에 실제로 정립된 분류가 있을 때만 쓰고 절대 지어내지 마세요. 마땅한 분류가 없으면 '변수 → 결과' 관계 표를 쓰세요.
- 주제에 자연스러울 때만 핵심 수식 1~2개를 넣고, 수식에 쓰인 기호는 바로 아래에 한 줄씩 설명합니다.
- 수식이 어울리지 않는 주제는 억지로 넣지 말고 '변수 → 결과' 관계 표로 대체합니다.
- 소제목 2~3개, 전체 약 900~1,300자.
- 정의와 배경은 반복하지 않고, 장단점과 실무 이슈는 다음 파트에서 다룹니다.""",
        "min_headings": 2,
        "min_chars": 500,
        "last_badge": None,
    },
    {
        "no": 3,
        "name": "실무 포인트 & 암기 요약",
        "badges": "[장단점], [실무 이슈], [트러블슈팅], [암기 포인트]",
        "tip": "[면접 팁]",
        "guide": """- 이 파트의 역할: 현업 감각과 시험 직전 복습용 '마무리'입니다.
- 반드시 포함: (1) 장단점 또는 한계 (2) 실제 공정/소자에서 겪는 문제와 해결 방향
- 마지막 소제목은 반드시 `### [암기 포인트] 시험·면접 직전 체크` 로 하고, 3~5개의 짧은 불릿으로 핵심을 요약합니다.
- 소제목 3개, 전체 약 700~1,000자.
- 앞 파트 내용은 반복하지 말고 새로운 관점만 추가합니다.""",
        "min_headings": 3,
        "min_chars": 400,
        "last_badge": "[암기 포인트]",
    },
]

HEADING_RE = re.compile(r"^###\s*\[[^\]]+\]", re.M)


def normalize_markdown(text):
    t = text.strip()
    # 응답 전체를 감싼 ```markdown 펜스 제거 (본문 안의 코드블록은 건드리지 않음)
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    # LaTeX 구분자 통일: \[...\] -> $$...$$, \(...\) -> $...$
    t = re.sub(r"\\\[(.+?)\\\]", lambda mo: "$$" + mo.group(1) + "$$", t, flags=re.DOTALL)
    t = re.sub(r"\\\((.+?)\\\)", lambda mo: "$" + mo.group(1) + "$", t, flags=re.DOTALL)
    # 모델이 #, ## 제목을 쓴 경우 ### 로 강등
    t = re.sub(r"^#{1,2}\s", "### ", t, flags=re.M)
    # 과한 빈 줄 정리
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def validate_part(text, part):
    if len(text) < part["min_chars"]:
        raise ValueError(f"내용이 너무 짧음 ({len(text)}자)")
    headings = HEADING_RE.findall(text)
    if len(headings) < part["min_headings"]:
        raise ValueError(f"소제목 부족 ({len(headings)}개, 최소 {part['min_headings']}개)")
    if text.count("$$") % 2 != 0:
        raise ValueError("독립 수식($$) 짝이 맞지 않음 (잘렸을 가능성)")
    if text.replace("$$", "").count("$") % 2 != 0:
        raise ValueError("인라인 수식($) 짝이 맞지 않음 (잘렸을 가능성)")
    last_badge = part.get("last_badge")
    if last_badge and last_badge not in headings[-1]:
        raise ValueError(f"마지막 소제목이 {last_badge} 가 아님")


def build_part_prompt(part, previous_text):
    prev_block = ""
    if previous_text:
        prev_block = f"""
[앞 파트에서 이미 작성된 내용 - 중복 서술 금지, 용어와 기호 표기는 그대로 유지]
<<<
{previous_text}
>>>
"""
    return f"""'{target_keyword}'에 대한 이론 노트를 3개 파트로 나눠 쓰고 있습니다. 지금은 {part['no']}/3 파트 「{part['name']}」입니다.

- 분류: {sel_cat} > {sel_sub}
- 주제: {target_keyword}
{prev_block}
[이 파트 작성 지침]
{part['guide']}

[형식 재확인]
- 소제목은 `### [뱃지] 제목` 형식이며, 뱃지는 내용에 맞게 다음 중에서 고르세요: {part['badges']}
- 인라인 팁 `> 💡 {part['tip']} ...` 를 1개 포함하세요.
- 이 파트 범위 밖의 내용은 쓰지 말고, 마크다운 본문만 출력하세요."""


def ask_markdown(user_prompt, part, retries=2):
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            res = client.chat.completions.create(
                model=THEORY_MODEL,
                messages=[
                    {"role": "system", "content": THEORY_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,   # 이론은 사실성이 중요하므로 낮게
                max_tokens=2500,
            )
            choice = res.choices[0]
            if choice.finish_reason == "length":
                raise ValueError("토큰 한도에서 출력이 잘림")
            text = normalize_markdown(choice.message.content or "")
            validate_part(text, part)
            return text
        except Exception as e:
            last_err = e
            print(f"   ↻ 이론 {part['no']}/3 재시도 {attempt}/{retries + 1}: {e}")
    raise RuntimeError(f"이론 {part['no']}/3 생성 실패: {last_err}")


def generate_theory():
    sections = []
    for part in THEORY_PARTS:
        print(f"   📖 이론 {part['no']}/3 「{part['name']}」 생성 중...")
        previous = "\n\n".join(sections)
        sections.append(ask_markdown(build_part_prompt(part, previous), part))
    return "\n\n".join(sections)


def generate_unified_content():
    if target_keyword is None:
        print("✅ topics의 모든 키워드가 이미 등재/대기 중입니다. 새 키워드를 추가해 주세요. (API 호출 없이 종료)")
        return
    pending = len(load_json_list(draft_t_path))
    if pending >= MAX_PENDING_DRAFTS:
        print(f"⏸️ 검수 대기 이론이 {pending}개 쌓여 있어 이번 실행은 건너뜁니다. (API 호출 없이 종료)")
        return

    print(f"[{target_keyword}] 기반 통합 콘텐츠 생성 시작...")
    theory_content = ""

    # ----------------------------------------------------
    # 1. 📖 이론 백과사전 생성 및 저장 (3단계 분할)
    # ----------------------------------------------------
    try:
        theory_content = generate_theory()
        theory_json = [{
            "id": new_id("TH"),
            "category": sel_cat,
            "subject": sel_sub,
            "title": target_keyword,
            "tags": [target_keyword.replace(" ", ""), "핵심이론"],
            "content": theory_content,
        }]
        save_draft(draft_t_path, theory_json)
        print("✅ 1/3 이론 백과사전 생성 및 저장 성공! (3단계 분할 생성)")
    except Exception as e:
        # 3파트 중 하나라도 실패하면 미완성 이론을 저장하지 않고 종료
        print(f"⚠️ 이론 생성 실패 (이후 단계 취소됨): {e}")
        return

    # ----------------------------------------------------
    # 2. 📝 이론 기반 객관식 생성 및 저장
    # ----------------------------------------------------
    try:
        msg_quiz = [
            {"role": "system", "content": "You strictly output a valid JSON array. 수식의 역슬래시는 반드시 두 개(\\\\) 작성하세요."},
            {"role": "user", "content": f"""
다음 이론 내용만을 바탕으로, 이론 이해도를 검증하는 긍정형 객관식 기출문제 3개를 만들어주세요. 부정형("아닌 것은?") 질문은 금지합니다:
{theory_content}

[
  {{
    "id": "Q-{random.randint(10000,99999)}",
    "category": "{sel_cat}",
    "topic": "{target_keyword}",
    "difficulty": "중급",
    "question": "문제 지문",
    "options": ["보기1", "보기2", "보기3", "보기4"],
    "answer": 0,
    "explanation": "해설"
  }}
]
"""}
        ]
        res_q = client.chat.completions.create(model="gpt-4o-mini", messages=msg_quiz, temperature=0.7)
        quiz_json = json.loads(clean_json_string(res_q.choices[0].message.content))
        for q in quiz_json:
            q["id"] = new_id("Q")  # AI가 만든 ID는 신뢰하지 않고 항상 새로 부여
            correct_text = q["options"][q["answer"]]
            random.shuffle(q["options"])
            q["answer"] = q["options"].index(correct_text)

        save_draft(draft_q_path, quiz_json)
        print("✅ 2/3 이론 연계 객관식 생성 및 저장 성공!")
    except Exception as e:
        print(f"⚠️ 객관식 생성 실패 (건너뜀): {e}")

    # ----------------------------------------------------
    # 3. 🗣️ 이론 기반 면접 생성 및 저장
    # ----------------------------------------------------
    try:
        msg_int = [
            {"role": "system", "content": "You strictly output a valid JSON array. 수식의 역슬래시는 반드시 두 개(\\\\) 작성하세요."},
            {"role": "user", "content": f"""
다음 이론을 바탕으로 실무 적용 역량을 묻는 날카로운 면접 질문 2개를 만드세요:
{theory_content}

[
  {{
    "id": "INT-{random.randint(10000,99999)}",
    "category": "{sel_cat}",
    "topic": "{target_keyword}",
    "difficulty": "고급",
    "question": "면접 지문",
    "key_points": ["키워드1", "키워드2"],
    "interview_answer": "두괄식 답변 스크립트"
  }}
]
"""}
        ]
        res_i = client.chat.completions.create(model="gpt-4o-mini", messages=msg_int, temperature=0.7)
        interview_json = json.loads(clean_json_string(res_i.choices[0].message.content))
        for i in interview_json:
            i["id"] = new_id("INT")

        save_draft(draft_i_path, interview_json)
        print("✅ 3/3 이론 연계 실무 면접 생성 및 저장 성공!")
    except Exception as e:
        print(f"⚠️ 면접 생성 실패 (건너뜀): {e}")


if __name__ == "__main__":
    generate_unified_content()
