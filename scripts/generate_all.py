import os
import json
import random
import re
import uuid
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 품질/비용 프리셋. GitHub 저장소 Variables 의 QUALITY_PRESET (또는 수동 실행 시 입력)으로 고릅니다.
#   high     : 전부 gpt-4o            (품질 최고, 비용 최대)
#   balanced : 이론 본문·이론 교정만 gpt-4o, 구성안·문제/면접 초안·검수는 gpt-4o-mini  (기본값)
#   economy  : 전부 gpt-4o-mini       (비용 최소)
PRESETS = {
    "high":     {"plan": "gpt-4o",      "theory": "gpt-4o",      "audit": "gpt-4o",      "qa": "gpt-4o",      "review": "gpt-4o"},
    "balanced": {"plan": "gpt-4o-mini", "theory": "gpt-4o",      "audit": "gpt-4o",      "qa": "gpt-4o-mini", "review": "gpt-4o-mini"},
    "economy":  {"plan": "gpt-4o-mini", "theory": "gpt-4o-mini", "audit": "gpt-4o-mini", "qa": "gpt-4o-mini", "review": "gpt-4o-mini"},
}
PRESET = (os.environ.get("QUALITY_PRESET") or "balanced").strip().lower()
if PRESET not in PRESETS:
    print(f"⚠️ 알 수 없는 QUALITY_PRESET '{PRESET}' → balanced 로 진행")
    PRESET = "balanced"
M = PRESETS[PRESET]
CHECK_MODEL = M["review"]  # review_existing.py 호환용
print(f"⚙️ 품질 프리셋: {PRESET} {M}")

topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "keywords": ["에너지 밴드", "페르미 준위", "캐리어 농도", "PN 접합", "유효 질량"]},
    {"category": "반도체 소자", "subject": "트랜지스터 소자", "keywords": ["MOSFET", "채널 길이 변조", "단채널 효과 (SCE)", "누설 전류", "문턱 전압"]},
    {"category": "반도체 소자", "subject": "메모리 반도체", "keywords": ["DRAM 동작 원리", "NAND 플래시 구조", "SRAM 셀 구조", "리프레시 동작"]},
    {"category": "반도체 8대 공정", "subject": "1. 웨이퍼 제조 공정", "keywords": ["초크랄스키 공정", "웨이퍼 연마(CMP)", "에피택시 성장", "실리콘 잉곳"]},
    {"category": "반도체 8대 공정", "subject": "2. 산화 공정 (Oxidation)", "keywords": ["건식 산화", "습식 산화", "Deal-Grove 모델", "게이트 산화막"]},
    {"category": "반도체 8대 공정", "subject": "3. 포토 공정 (Photo)", "keywords": ["노광 공정", "포토레지스트", "해상도와 초점 심도", "EUV 리소그래피"]},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "keywords": ["건식 식각", "플라즈마 식각", "식각 선택비", "Bowing 현상"]},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)", "keywords": ["CVD 공정", "ALD 공정", "PVD 공정", "단차 피복성"]},
    {"category": "반도체 8대 공정", "subject": "6. 금속 배선 공정 (Metallization)", "keywords": ["구리 다마신 공정", "전자 이동(Electromigration)", "배리어 메탈", "RC 지연"]},
    {"category": "반도체 8대 공정", "subject": "7. EDS 공정 (Testing)", "keywords": ["EDS 테스트 흐름", "번인 테스트", "수율(Yield)", "리페어와 리던던시"]},
    {"category": "반도체 8대 공정", "subject": "8. 패키징 공정 (Packaging)", "keywords": ["와이어 본딩", "플립칩 패키지", "몰딩 공정", "패키지 열 방출"]},
    {"category": "차세대 첨단 기술", "subject": "차세대 소자 기술", "keywords": ["FinFET 구조", "GAA 나노시트", "High-k/Metal Gate", "BSPDN 후면 전력"]},
    {"category": "차세대 첨단 기술", "subject": "어드밴스드 패키징", "keywords": ["HBM 구조", "TSV 공정", "2.5D 인터포저", "하이브리드 본딩"]}
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
    """폴더(subject)별로 이론이 골고루 쌓이도록 고른다.
    - 등재된 이론 + 검수 대기 중인 이론 수가 '가장 적은' 폴더를 먼저 뽑는다 (동률이면 무작위)
    - 이미 만든 키워드는 제외한다. 남은 키워드가 하나도 없으면 None.
    """
    norm = lambda x: re.sub(r"\s+", "", str(x))
    used, per_subject = set(), {}
    for path in ("data/theories.json", draft_t_path):
        for t in load_json_list(path):
            if not isinstance(t, dict) or "채워질 예정" in str(t.get("content", "")):
                continue  # 자리표시자는 실제 이론이 아니므로 세지 않음
            used.add(norm(t.get("title", "")))
            key = (t.get("category"), t.get("subject"))
            per_subject[key] = per_subject.get(key, 0) + 1

    candidates = []
    for t in topics:
        left = [kw for kw in t["keywords"] if norm(kw) not in used]
        if left:
            candidates.append((per_subject.get((t["category"], t["subject"]), 0), t, left))
    if not candidates:
        return None
    fewest = min(c[0] for c in candidates)
    _, topic, left = random.choice([c for c in candidates if c[0] == fewest])
    return topic, random.choice(left)


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
THEORY_SYSTEM = """당신은 반도체 공정·소자 분야 10년차 현직 엔지니어입니다. 이제 막 반도체를 배우는 후배(전공자와 비전공 취준생이 섞여 있음)에게 옆에서 차근차근 설명해 주는 마음으로 학습 글을 씁니다.
목표는 '외워지는 글'이 아니라 '읽고 나면 이해되는 글'입니다. 이 주제만의 글이어야 하며, 다른 주제 이름만 바꿔도 통하는 글은 실패입니다.

[문체]
- 평서체(~한다, ~이다, ~된다, ~있다)로 씁니다. 해요체(~해요, ~예요, ~거든요)와 합니다체(~합니다, ~입니다)는 쓰지 않습니다. 담백하고 또렷하게 쓰되 딱딱한 개조식 나열이나 사전식 정의 나열은 피합니다.
- 항목을 나열하기 전에 '왜 그런지'를 인과로 먼저 풀어 줍니다. (A 때문에 B가 되고, 그래서 C를 신경 써야 한다)
- 한 문단은 3~4문장 이내. 문장 길이와 시작 표현을 다양하게 합니다. 같은 어미·접속어를 반복하지 않습니다.
- 독자에게 질문을 던지며 시작하지 않고, 본문에서도 수사 의문문("~일까?")을 쓰지 않습니다. 궁금할 만한 점은 평서문으로 짚고 바로 설명합니다.
- 처음 보는 용어는 쉬운 말로 먼저 풀고, 영문 용어는 처음 한 번만 괄호로 병기합니다. 예: 식각 선택비(Selectivity)
- 핵심 용어와 꼭 기억할 문장은 **굵게** 표시하되, 문단마다 남발하지 않습니다.
- 비유는 글 전체에서 많아야 1개, 정확히 들어맞을 때만 쓰고 어디까지 맞는지 한 줄로 한계도 말합니다.
- 표는 '둘 이상을 둘 이상의 기준으로 비교'할 때만 씁니다.
- 수식은 LaTeX로 쓰고, 인라인은 $...$, 독립 수식은 $$...$$ 로 감쌉니다. 백슬래시는 평소처럼 한 개만 씁니다. 예: $\\sigma$, $$I_D = \\frac{1}{2}\\mu C_{ox}\\frac{W}{L}(V_{GS}-V_{th})^2$$

[정확성 - 가장 중요]
- 교과서·업계에서 정립된 내용만 씁니다. 지어낸 분류, 지어낸 수치·공식, 확실하지 않은 구체 숫자는 쓰지 않고 '커진다/줄어든다' 같은 경향으로 씁니다.
- 널리 알려진 수치는 '대략'이라고 밝히고 자릿수 수준으로만 씁니다.
- 주제와 직접 상관없는 일반론으로 분량을 채우지 않습니다. 해당되지 않는 항목(예: 지표에 '동작 원리', 장단점이 없는 개념에 '장단점')은 쓰지 않습니다.

[쓰지 말아야 할 상투적 표현]
'중요한 역할을 한다', '필수적이다', '다양한 분야에서', '이를 통해', '뿐만 아니라', '큰 영향을 미친다'(어떻게 미치는지 안 밝히고 쓰는 경우), '~을 명확히 이해하고', '핵심적인 역할'. 이런 말 대신 '구체적으로 무엇이 어떻게 되는지'를 씁니다.

[소제목]
- `### [뱃지] 제목` 형식. 제목은 이 주제에서만 나올 구체적인 명사구나 평서문으로 씁니다. 예: `### [핵심 개념] 식각은 '깎는 일'이 아니라 '고르는 일'이다`
- 이론은 면접이 아니라 설명하는 글입니다. 제목에 물음표(?)나 의문형(~란?, ~일까, ~할까)을 쓰지 않습니다.
- '~의 중요성' 같은 어느 주제에나 붙는 제목도 피합니다.

[팁 박스]
- `> 💡 [실무 코멘트]`, `> 💡 [면접 팁]`, `> 💡 [흔한 오해]` 중 하나로 한 줄 인용문으로 씁니다.
- 반드시 구체적인 정보를 담습니다: 학습자가 자주 하는 오해와 바로잡기, 시험·면접에서 헷갈리는 포인트, 현장에서 실제로 보는 단서 등. '~을 이해하고 설명할 수 있어야 한다' 같은 빈 조언은 금지입니다.

[형식]
- 출력은 마크다운 본문만 씁니다. JSON, 인사, 맺음말, 최상위 제목(#, ##)은 쓰지 않습니다. 전체를 코드블록으로 감싸지 않습니다."""

DEFAULT_PARTS = [  # 계획 단계가 실패했을 때만 쓰는 기본 틀
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


# 이론 글에 넣을 수 있는 '눌러 보는 그림' 목록과 자동 삽입 규칙은 scripts/diagram_rules.py 에 있다. (그림 자체는 index.html 의 DIAGRAMS)
from diagram_rules import DIAGRAMS, ensure_diagrams
DIAGRAM_LINE_RE = re.compile(r"^[ \t]*\{\{\s*diagram:([^|}\s]+)(?:\|([^}\n]*))?\}\}[ \t]*$", re.M)


def diagram_menu():
    return "\n".join(f"  - {k}: {v}" for k, v in DIAGRAMS.items())


def sanitize_diagrams(text, seen=None):
    """AI 가 쓴 {{diagram:id|캡션}} 줄을 점검한다. 목록에 없는 id 와 같은 그림의 중복은 줄째로 지운다."""
    seen = set() if seen is None else seen

    def fix(m):
        did = m.group(1).strip()
        if did not in DIAGRAMS or did in seen:
            return ""
        seen.add(did)
        cap = re.sub(r"[{}|]", "", (m.group(2) or "")).strip()
        return "{{diagram:%s%s}}" % (did, "|" + cap if cap else "")
    out = DIAGRAM_LINE_RE.sub(fix, text)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


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
    t = sanitize_diagrams(t)
    return t


CLICHES = [r"중요한 역할", r"핵심적인 역할", r"필수적", r"다양한 (?:분야|산업|응용)", r"이를 통해", r"뿐만 아니라",
           r"매우 중요", r"큰 영향을 (?:미|끼)", r"중요성을 (?:이해|명확)", r"명확히 이해", r"효과적으로 활용"]


# 해요체·합니다체 어미 탐지 (이론·문제는 평서체 ~한다/~이다/~된다 로 쓴다). '필요', '주요', '중요', '수요' 같은 명사는 걸리지 않도록 예외로 뺀다.
POLITE_RE = re.compile(r"(?:(?<=[가-힣])(?<![필중주수소개긴절])요|죠|습니다|입니다|합니다|됩니다|줍니다|립니다)(?=[\s.?!,)\"'*`~]|$)")


def polite_hits(text):
    return len(POLITE_RE.findall(text))


def cliche_hits(text):
    return sum(len(re.findall(p, text)) for p in CLICHES)


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
    hits = cliche_hits(text)
    if hits >= 3:
        raise ValueError(f"상투적 표현이 {hits}번 쓰임 (구체적으로 다시 쓰기)")
    ph = polite_hits(text)
    if ph >= 2:
        raise ValueError(f"해요체/합니다체 어미가 {ph}번 쓰임 → 모든 문장을 평서체(~한다, ~이다, ~된다)로 쓰기")
    q_heads = [h for h in re.findall(r"^###.*$", text, re.M) if "?" in h or re.search(r"(?:까|나요|니까|란)\s*$", h.strip())]
    if q_heads:
        raise ValueError(f"소제목이 질문형임 ({q_heads[0][:40]}...) → 명사구/평서문으로 바꾸기")
    body_q = [ln for ln in text.splitlines() if "?" in ln and not ln.lstrip().startswith(("###", ">"))]
    if len(body_q) > 1:
        raise ValueError(f"본문에 물음표 문장이 {len(body_q)}개 있음 (수사 의문문 금지, 평서문으로)")


def digest(text):
    """앞 파트 전체를 다시 보내면 토큰이 낭비되므로, 소제목·굵은 용어·수식 기호만 추린다."""
    heads = re.findall(r"^###.*$", text, re.M)
    bolds = list(dict.fromkeys(re.findall(r"\*\*([^*\n]{1,30})\*\*", text)))[:25]
    maths = list(dict.fromkeys(re.findall(r"\$([^$\n]{1,40})\$", text)))[:10]
    out = "소제목:\n" + "\n".join(heads)
    if bolds: out += "\n쓰인 핵심 용어: " + ", ".join(bolds)
    if maths: out += "\n쓰인 기호: " + ", ".join(f"${m}$" for m in maths)
    return out


def build_part_prompt(part, previous_text, outline=""):
    prev_block = ""
    if previous_text:
        prev_block = f"""
[앞 파트에서 이미 다룬 내용 요약 - 같은 설명을 반복하지 말고, 용어와 기호 표기는 그대로 유지]
<<<
{digest(previous_text)}
>>>
"""
    return f"""'{target_keyword}'에 대한 이론 노트를 3개 파트로 나눠 쓰고 있습니다. 지금은 {part['no']}/3 파트 「{part['name']}」입니다.

- 분류: {sel_cat} > {sel_sub}
- 주제: {target_keyword}
{outline}{prev_block}
[이 파트 작성 지침]
{part['guide']}

[형식 재확인]
- 소제목은 `### [뱃지] 제목` 형식이며, 뱃지는 내용에 맞게 다음 중에서 고르세요: {part['badges']}
- 인라인 팁 `> 💡 {part['tip']} ...` 를 1개 포함하세요.
- (선택) 아래 '눌러 보는 그림' 중 이 글의 설명에 꼭 맞는 것이 있을 때만, 그 그림이 필요한 소제목의 본문 뒤에 단독 한 줄로 `{{{{diagram:그림id|한 문장 캡션}}}}` 을 넣을 수 있습니다. 맞는 그림이 없으면 아무것도 넣지 않습니다. 같은 그림은 글 전체에서 한 번만 쓰고, 그림이 설명하는 내용을 글에서도 말로 설명해야 합니다.
{diagram_menu()}
- 이 파트 범위 밖의 내용은 쓰지 말고, 마크다운 본문만 출력하세요."""


def ask_markdown(user_prompt, part, retries=2):
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            feedback = f"\n\n[직전 시도가 실패한 이유 - 이번에는 고쳐서 쓰세요]\n{last_err}" if last_err else ""
            res = client.chat.completions.create(
                model=M["theory"],
                messages=[
                    {"role": "system", "content": THEORY_SYSTEM},
                    {"role": "user", "content": user_prompt + feedback},
                ],
                temperature=0.6,   # 문장이 틀에 박히지 않도록 약간 열어 두되, 사실성은 아래 교정 단계에서 다시 확인
                max_tokens=2800,
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


PLAN_SYSTEM = "당신은 반도체 학습 글의 구성을 설계하는 편집자입니다. 반드시 유효한 JSON 객체 하나만 출력합니다."

PLAN_SCHEMA = """{
  "kind": "process | device | phenomenon | metric | material | flow 중 하나",
  "use_formula": true 또는 false,
  "core_question": "이 글이 답하는 가장 핵심적인 질문 한 문장 (학습자가 실제로 궁금해할 만한 것)",
  "misconceptions": ["학습자가 자주 하는 실제 오해 1~2개 (없으면 빈 배열)"],
  "analogy": "정확히 들어맞는 비유가 있을 때만 한 문장. 없으면 빈 문자열",
  "parts": [
    {"name": "파트 이름(12자 이내)", "focus": ["다룰 내용 1", "다룰 내용 2", "다룰 내용 3"], "badges": ["핵심 개념", "정의"]},
    {"name": "...", "focus": ["..."], "badges": ["..."]},
    {"name": "...", "focus": ["..."], "badges": ["..."]}
  ]
}"""


def build_plan_prompt():
    return f"""'{target_keyword}' ({sel_cat} > {sel_sub}) 에 대한 학습 글의 구성을 설계하세요.

먼저 이 주제의 성격(kind)을 판단합니다.
- process: 공정/장비가 동작하는 방식  - device: 소자·구조  - phenomenon: 물리 현상·효과
- metric: 특성·지표·평가량 (예: 선택비, 단차 피복성, 수율)  - material: 재료  - flow: 공정 흐름·테스트 체계

글은 항상 3개 파트이며 역할은 고정입니다.
- 파트1(개념): 왜 이게 필요한지(문제 상황)에서 출발해 정의와 직관적 이해까지
- 파트2(세부): 시험·면접에서 깊게 묻는 핵심. 주제에 실제로 맞는 것만 고릅니다. (예: 측정·정의 방법, 값을 좌우하는 변수, 메커니즘, 비교, 정의식)
- 파트3(실무·요약): 현업에서 겪는 문제와 개선 방향, 마지막은 암기 포인트

설계 규칙
- 이 주제만의 글이 되도록, 이 주제에서 학습자가 가장 헷갈리거나 놓치기 쉬운 지점을 core_question과 misconceptions 에 담습니다.
- '동작 원리'는 process·device일 때만 씁니다. metric·phenomenon이면 '정의와 측정 방법', '값을 좌우하는 요인', '발생 원인' 등으로 바꿉니다.
- '장단점'은 장단점이 실제로 있는 기술·방식일 때만 씁니다. metric이면 '값이 좋을 때/나쁠 때의 영향', '개선 방법'으로 바꿉니다.
- '종류·분류'는 교과서에 정립된 분류가 있을 때만 씁니다. 확신이 없으면 쓰지 않습니다.
- use_formula는 널리 쓰이는 정의식·관계식이 실제로 있을 때만 true 입니다.
- 각 파트의 focus는 이 주제에 딱 맞는 구체적 항목 2~4개이고, 파트 간에 겹치면 안 됩니다.
- badges는 대괄호 없이, 그 파트 소제목에 쓸 짧은 이름 2~4개입니다. (예: 핵심 개념, 정의, 측정 방법, 변수 영향, 비교, 수식, 실무 이슈, 개선 방법)

아래 JSON 형식으로만 답하세요.
{PLAN_SCHEMA}"""


def validate_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("parts"), list) or len(plan["parts"]) != 3:
        raise ValueError("parts 가 3개가 아님")
    for pt in plan["parts"]:
        if not isinstance(pt.get("name"), str) or not pt["name"].strip():
            raise ValueError("파트 이름 없음")
        if not isinstance(pt.get("focus"), list) or not (1 <= len(pt["focus"]) <= 6) or not all(isinstance(x, str) and x.strip() for x in pt["focus"]):
            raise ValueError("focus 형식 오류")
        if not isinstance(pt.get("badges"), list) or not (1 <= len(pt["badges"]) <= 6) or not all(isinstance(x, str) and x.strip() for x in pt["badges"]):
            raise ValueError("badges 형식 오류")
    if not isinstance(plan.get("core_question"), str) or not plan["core_question"].strip():
        raise ValueError("core_question 없음")


def make_plan(retries=2):
    """주제 성격에 맞는 3파트 구성안을 받는다. 끝내 실패하면 None (→ 기본 틀 사용)."""
    for attempt in range(1, retries + 2):
        try:
            res = client.chat.completions.create(
                model=M["plan"],
                messages=[{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": build_plan_prompt()}],
                temperature=0.3,
                max_tokens=900,
                response_format={"type": "json_object"},
            )
            plan = json.loads(clean_json_string(res.choices[0].message.content or ""))
            validate_plan(plan)
            return plan
        except Exception as e:
            print(f"   ↻ 구성 설계 재시도 {attempt}/{retries + 1}: {e}")
    return None


def parts_from_plan(plan):
    use_formula = bool(plan.get("use_formula"))
    badge = lambda names: ", ".join(f"[{b.strip().strip('[]')}]" for b in names)
    formula_rule = (
        "- 핵심 수식 1~2개를 독립 수식($$...$$)으로 넣고, 쓰인 기호는 바로 아래에 한 줄씩 설명합니다."
        if use_formula else
        "- 수식은 억지로 만들지 않습니다. 정의식이 필요하면 말로 풀어 쓰세요."
    )
    def focus(i):
        return "\n".join(f"  · {x.strip()}" for x in plan["parts"][i]["focus"])
    core_q = plan["core_question"].strip()
    miscs = [m.strip() for m in (plan.get("misconceptions") or []) if isinstance(m, str) and m.strip()]
    misc_rule = ("- 아래 실제 오해 중 하나를 `> 💡 [흔한 오해]` 팁 박스로 바로잡아 주세요: " + " / ".join(miscs)) if miscs else ""
    analogy = plan.get("analogy") if isinstance(plan.get("analogy"), str) else ""
    analogy_rule = (f"- 비유를 쓴다면 이것만: {analogy.strip()} (어디까지 맞는지 한 줄로 한계도 밝히기)" if analogy.strip() else "- 비유는 억지로 만들지 않습니다.")
    return [
        {
            "no": 1, "name": plan["parts"][0]["name"].strip(), "badges": badge(plan["parts"][0]["badges"]), "tip": "[면접 팁]",
            "guide": f"""- 이 파트의 역할: 처음 보는 사람도 따라올 수 있는 '뼈대'입니다.
- 글 전체가 답하려는 핵심: "{core_q}" (방향 참고용입니다. 질문 문장으로 쓰지 말고 평서문으로 답하며 풀어 쓰세요)
- 첫 문단은 정의가 아니라 '이게 없으면/이게 어긋나면 어떤 문제가 생기는지' 같은 구체적인 상황으로 시작하세요. 질문으로 시작하지 않습니다.
- 이 파트에서 다룰 내용 (주제에 맞게 설계됨):
{focus(0)}
{analogy_rule}
- 소제목 2~3개, 전체 약 700~1,100자. 위 항목 외의 일반론은 쓰지 않습니다.
- 세부 변수·수식·표, 실무 이슈는 다음 파트에서 다루므로 여기서는 쓰지 않습니다.""",
            "min_headings": 2, "min_chars": 400, "last_badge": None,
        },
        {
            "no": 2, "name": plan["parts"][1]["name"].strip(), "badges": badge(plan["parts"][1]["badges"]), "tip": "[실무 코멘트]",
            "guide": f"""- 이 파트의 역할: 시험과 면접에서 구체적으로 묻는 '세부 내용'입니다. 사실과 인과가 정확해야 합니다.
- 이 파트에서 다룰 내용 (주제에 맞게 설계됨):
{focus(1)}
- 비교나 변수 → 결과 관계가 있으면 마크다운 표로 정리합니다. 억지로 만든 분류·종류 표는 금지입니다.
{formula_rule}
{misc_rule}
- 소제목 2~3개, 전체 약 900~1,400자.
- 정의와 배경은 반복하지 않고, 현업 이슈는 다음 파트에서 다룹니다.""",
            "min_headings": 2, "min_chars": 450, "last_badge": None,
        },
        {
            "no": 3, "name": plan["parts"][2]["name"].strip(), "badges": badge(plan["parts"][2]["badges"] + ["암기 포인트"]), "tip": "[면접 팁]",
            "guide": f"""- 이 파트의 역할: 현업 감각과 시험 직전 복습용 '마무리'입니다.
- 이 파트에서 다룰 내용 (주제에 맞게 설계됨):
{focus(2)}
- 마지막 소제목은 반드시 `### [암기 포인트] 시험·면접 직전 체크` 로 하고, 3~5개의 짧은 불릿으로 핵심을 요약합니다. (이 불릿은 개조식으로 짧게 써도 좋습니다)
- 소제목 3개, 전체 약 700~1,100자.
- 앞 파트 내용은 반복하지 말고 새로운 관점만 추가합니다.""",
            "min_headings": 3, "min_chars": 400, "last_badge": "[암기 포인트]",
        },
    ]


AUDIT_SYSTEM = """당신은 반도체 공정·소자 전문가이자 까다로운 학습서 편집자입니다. 받은 학습 글에서 '고쳐야 할 구절'만 찾아 JSON 으로 알려 줍니다. 글 전체를 다시 쓰지 않습니다.
고칠 대상은 다음뿐입니다.
1. 사실 오류, 지어낸 분류·수치·공식, 확신할 수 없는 구체 숫자
2. 구체적이지 않은 빈말 문장(예: '중요한 역할을 한다'), 같은 말을 되풀이하는 문장, 내용 없는 팁 박스
3. 질문형 소제목, 수사 의문문
4. 평서체(~한다/~이다/~된다)가 아닌 문장 끝(~해요, ~예요, ~합니다, ~입니다)
틀리지 않은 문장은 건드리지 않습니다. 고칠 곳이 없으면 빈 배열을 돌려줍니다.

출력 형식(JSON 객체 하나만):
{"fixes": [{"find": "원문에 글자 하나 다르지 않게 그대로 있는 구절(원문에서 한 번만 나오는 길이로)", "replace": "고친 구절(삭제하려면 빈 문자열, 평서체 ~한다/~이다로 씀)", "reason": "한 줄 이유"}]}
- find 는 한 줄 안에서만 고르고, '###' 소제목 표식이나 수식($...$) 기호는 find/replace 에 넣지 않습니다. (소제목 문구를 고칠 때는 ### [뱃지] 는 빼고 제목 글자만)
- 최대 8개."""


def audit_theory(text):
    """전체를 다시 쓰지 않고, 고칠 구절만 받아 파이썬이 직접 바꾼다. (토큰 절약 + 원문 훼손 방지)"""
    try:
        res = client.chat.completions.create(
            model=M["audit"],
            messages=[{"role": "system", "content": AUDIT_SYSTEM}, {"role": "user", "content": text}],
            temperature=0.1, max_tokens=1200, response_format={"type": "json_object"},
        )
        fixes = json.loads(clean_json_string(res.choices[0].message.content or "")).get("fixes") or []
        out, applied = text, 0
        for f in fixes[:8]:
            if not isinstance(f, dict):
                continue
            find, rep_ = str(f.get("find", "")), str(f.get("replace", ""))
            if len(find) < 4 or "\n" in find or "###" in find or "$" in find or "$" in rep_ or out.count(find) != 1:
                continue
            out = out.replace(find, rep_)
            applied += 1
        out = re.sub(r"[ \t]{2,}", " ", out); out = re.sub(r"\n{3,}", "\n\n", out)
        if len(out) < len(text) * 0.8 or len(HEADING_RE.findall(out)) != len(HEADING_RE.findall(text)):
            raise ValueError("교정 결과가 구조를 해쳐서 취소")
        print(f"   ✨ 편집 교정: 제안 {len(fixes)}개 중 {applied}개 적용")
        return out
    except Exception as e:
        print(f"   ⚠️ 편집 교정을 건너뜁니다(원문 유지): {e}")
        return text


def generate_theory():
    plan = make_plan()
    if plan:
        parts = parts_from_plan(plan)
        print(f"   🧭 구성 설계 완료 (성격: {plan.get('kind', '?')}) → " + " / ".join(pt["name"] for pt in parts))
        outline = "[전체 구성 계획 - 파트끼리 내용이 겹치지 않게 합니다]\n" + "\n".join(
            f"- {pt['no']}/3 「{pt['name']}」" for pt in parts) + "\n"
    else:
        parts, outline = DEFAULT_PARTS, ""
        print("   ⚠️ 구성 설계에 실패해 기본 틀로 진행합니다.")
    sections = []
    for part in parts:
        print(f"   📖 이론 {part['no']}/3 「{part['name']}」 생성 중...")
        previous = "\n\n".join(sections)
        sections.append(ask_markdown(build_part_prompt(part, previous, outline), part))
    seen = set()
    sections = [sanitize_diagrams(sec, seen) for sec in sections]   # 파트가 달라도 같은 그림은 한 번만
    return audit_theory("\n\n".join(sections))


# ====================================================================
# 📝 객관식 / 🗣️ 면접: 초안 작성 → 파이썬 규칙 검사 → AI 검수(사실·단서·해설) → 조립
#   - 보기 순서는 파이썬에서 섞고, 해설의 '몇 번' 표기도 섞은 뒤에 파이썬이 만든다.
# ====================================================================
def call_json(model, system, user, temperature, max_tokens=3000):
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature, max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    if res.choices[0].finish_reason == "length":
        raise ValueError("출력이 잘림")
    return json.loads(clean_json_string(res.choices[0].message.content or ""))


QUIZ_SYSTEM = """당신은 반도체 자격·면접 대비 문제를 출제하는 20년차 출제위원입니다. 학생이 '글만 읽고 감으로' 풀 수 없고, 풀고 나면 이론이 더 또렷해지는 문제를 만듭니다. 반드시 유효한 JSON 객체 하나만 출력합니다. 수식 기호(LaTeX, 백슬래시)는 쓰지 말고 Vth, ID 처럼 일반 문자로 씁니다."""

QUIZ_SCHEMA = """{
  "questions": [
    {
      "type": "concept | cause | scenario | compare 중 하나",
      "difficulty": "기초 | 중급 | 응용 중 하나",
      "question": "문제 지문",
      "correct": "정답 보기 문장",
      "distractors": [
        {"text": "오답 보기 문장", "why_wrong": "이 보기가 왜 틀렸는지, 어떤 오해에서 나온 보기인지 1문장"},
        {"text": "...", "why_wrong": "..."},
        {"text": "...", "why_wrong": "..."}
      ],
      "why_correct": "정답인 이유 2~3문장. 결론 → 이유 → 이론과의 연결 순서. 이 글을 처음 읽는 사람도 이해할 수 있게",
      "takeaway": "나중에 떠올릴 한 줄 기억 포인트"
    }
  ]
}"""


QUIZ_COMPOSITION = """1번: 개념 이해(concept) 또는 비교·구분(compare) — 기초~중급
2번: 원인→결과 추론(cause) — 중급
3번: 상황 적용(scenario) — 응용. 공정·소자에서 관측되는 상황을 2~3문장으로 제시하고 가장 타당한 원인·판단·조치를 묻기. 이론에서 도출 가능한 범위만."""


def build_quiz_prompt(theory, n=3, existing=None):
    comp = (QUIZ_COMPOSITION + ("\n나머지 문제: 위 유형과 겹치지 않는 다른 각도로" if n > 3 else "")) if n >= 3 else f"서로 다른 유형(concept/compare/cause/scenario)으로 {n}문제. 상황 적용(scenario)은 응용 난이도로, 공정·소자에서 관측되는 상황을 2~3문장으로 제시하고 가장 타당한 원인·판단·조치를 묻기."
    have = ("\n[이미 확보한 문제 - 이것과 겹치지 않는 다른 내용·다른 각도로 출제]\n" + "\n".join(f"- {str(e.get('question', ''))[:80]}" for e in existing) + "\n") if existing else ""
    return f"""아래 이론 글만을 근거로 객관식 {n}문제를 만드세요.

[문제 구성 - 서로 다른 유형으로]
{comp}
{have}
[보기 설계 규칙 - 글만 읽어도 풀리는 문제 금지]
- 보기 4개(정답 1 + 오답 3)는 길이, 문장 구조, 어조, 구체성 수준이 서로 비슷해야 합니다. 정답이 가장 길거나 가장 구체적이면 안 됩니다.
- 오답은 '학습자가 실제로 헷갈리는 오개념', '정답과 인접한 개념의 특성', '원인과 결과를 뒤집은 설명'처럼 그럴듯해야 합니다. 상식만으로 걸러지는 극단적·엉뚱한 보기("비용이 많이 든다", "전력 소모가 없다" 같은 것)는 금지입니다.
- '장점/특징을 고르는' 문제에서 오답을 단점들로만 채우지 마세요. 오답도 '장점처럼 들리지만 이 기술의 특징이 아닌 것' 등 같은 방향의 보기여야 합니다.
- 보기에 '항상, 절대, 전혀, 모든, 오직, 무조건' 같은 극단어를 쓰지 않습니다.
- 정답은 이론으로 명백히 하나여야 하고, 오답이 부분적으로 맞아 보여 논란이 생기면 안 됩니다.
- 문제 지문의 단어를 정답 보기에만 그대로 반복하지 않습니다.
- 부정형("아닌 것은?", "틀린 것은?") 질문은 금지입니다. 문제는 구체적인 질문 한 개입니다.

[문체 - 해요체 금지]
- 문제 지문·보기·해설 모두 평서체로 씁니다. 지문은 "~는 무엇인가?", "~의 원인으로 가장 타당한 것은?", 보기와 해설은 "~한다", "~이다", "~된다", 명사형 종결로 씁니다.
- "~인가요?", "~할까요?", "~해요", "~예요", "~합니다", "~입니다" 같은 어미는 쓰지 않습니다.

[해설]
- why_correct 는 '왜 맞는지'를 이론과 연결해 친절히, why_wrong 은 '어떤 오해라서 틀렸는지'를 각각 한 문장으로 씁니다.
- 이론에 없는 새 사실이나 구체 숫자를 지어내지 않습니다.

[이론 글]
<<<
{theory}
>>>

아래 JSON 형식으로만 답하세요.
{QUIZ_SCHEMA}"""


ABSOLUTE_RE = re.compile(r"항상|절대|전혀|모든 |오직|무조건")
NEGATIVE_RE = re.compile(r"아닌 것|않은 것|틀린 것|옳지 않")


def check_quiz_item(it):
    """규칙으로 잡을 수 있는 문제점을 문자열 목록으로 돌려준다. 비어 있으면 통과."""
    probs = []
    try:
        q, c = str(it["question"]).strip(), str(it["correct"]).strip()
        ds = it["distractors"]
        if not isinstance(ds, list) or len(ds) != 3:
            return ["오답 보기는 정확히 3개여야 함"]
        dt = [str(d["text"]).strip() for d in ds]
        dw = [str(d["why_wrong"]).strip() for d in ds]
    except Exception:
        return ["필수 필드 누락/형식 오류"]
    if len(q) < 12: probs.append("문제 지문이 너무 짧음")
    if NEGATIVE_RE.search(q): probs.append("부정형 질문")
    texts = [c] + dt
    norm = [re.sub(r"\s+", "", t) for t in texts]
    if any(not t for t in texts): probs.append("빈 보기")
    if len(set(norm)) != 4: probs.append("중복된 보기")
    if any(ABSOLUTE_RE.search(t) for t in texts): probs.append("극단어(항상/절대/전혀/모든/오직/무조건) 사용")
    avg = sum(len(t) for t in dt) / 3
    if len(c) > max(len(t) for t in dt) and len(c) > avg * 1.4: probs.append("정답이 오답보다 눈에 띄게 김")
    if len(str(it.get("why_correct", "")).strip()) < 20: probs.append("정답 해설이 너무 짧음")
    if any(len(w) < 8 for w in dw): probs.append("오답 해설이 너무 짧음")
    if not str(it.get("takeaway", "")).strip(): probs.append("기억 포인트 없음")
    if polite_hits(" ".join([q, *texts, *dw, str(it.get("why_correct", "")), str(it.get("takeaway", ""))])) >= 1:
        probs.append("해요체/합니다체 어미 사용 → 지문은 '~인가?', 보기·해설은 '~한다/~이다' 평서체로")
    return probs


QUIZ_REVIEW_SYSTEM = """당신은 문제를 깐깐하게 검수하는 반도체 전문가이자 출제 감수위원입니다. 반드시 유효한 JSON 객체 하나만 출력합니다. 수식 기호(백슬래시)는 쓰지 않습니다."""


def build_quiz_review_prompt(theory, items):
    listing = json.dumps([{"index": n, "item": it, "rule_problems": check_quiz_item(it)} for n, it in enumerate(items)], ensure_ascii=False)
    return f"""아래 객관식 문제 초안을 검수하세요. 각 문제를 다음 기준으로 평가합니다.

1. 사실: 정답이 실제 반도체 지식과 이론 글에서 맞는가? (이론 글 자체가 틀렸거나 문제가 성립하지 않으면 drop)
2. 정답 유일성: 다른 보기가 정답으로 해석될 여지는 없는가?
3. 단서 노출: 반도체 지식이 없어도 정답이 드러나는가? (보기 길이·구체성 차이, 극단적이거나 엉뚱한 오답, 지문 단어 반복, 장점을 묻는데 오답이 단점뿐인 경우 등)
4. 오답의 질: 각 오답이 실제로 헷갈릴 만한 오개념·인접 개념인가?
5. 해설: 왜 맞고 왜 틀린지 친절하고 정확한가? 이론에 없는 사실을 지어내지 않았는가?
6. 문체: 지문·보기·해설이 평서체(~인가?, ~한다, ~이다, ~된다)인가? '~인가요?', '~해요', '~합니다' 같은 어미는 평서체로 고칩니다. (fix 로 처리)
rule_problems 에 적힌 문제는 반드시 해결하세요.

각 문제에 대해 verdict 를 정합니다.
- ok: 그대로 사용 (final 에 원본 item 그대로)
- fix: 위 기준에 걸리는 부분을 고쳐서 final 에 같은 스키마로 완성본을 넣습니다. 문제의 핵심 의도는 유지하세요.
- drop: 고쳐도 살릴 수 없을 때 (final 은 null)

[이론 글]
<<<
{theory}
>>>

[문제 초안]
{listing}

아래 JSON 형식으로만 답하세요.
{{"reviews": [{{"index": 0, "verdict": "ok|fix|drop", "issues": ["발견한 문제 요약"], "final": {{...같은 item 스키마...}} 또는 null}}]}}"""


def compose_quiz(it, theory_id):
    """보기를 섞고, 섞인 번호에 맞춰 해설을 만든다."""
    pool = [(str(it["correct"]).strip(), None)] + [(str(d["text"]).strip(), str(d["why_wrong"]).strip()) for d in it["distractors"]]
    random.shuffle(pool)
    answer = next(n for n, (_, w) in enumerate(pool) if w is None)
    # 이미 완성된 해설 형식("정답 해설 ... 오답 체크 ...")이 why_correct 로 들어와도 두 번 감싸지 않는다
    why_correct = re.sub(r"^\s*정답 해설\s*\n", "", str(it["why_correct"]).strip())
    why_correct = re.split(r"\n\s*오답 체크\s*\n", why_correct)[0].split("\n💡 기억 포인트")[0].strip()
    wrong_lines = "\n".join(f"· {n + 1}번: {w}" for n, (_, w) in enumerate(pool) if w is not None)
    explanation = f"정답 해설\n{why_correct}\n\n오답 체크\n{wrong_lines}\n\n💡 기억 포인트: {str(it['takeaway']).strip()}"
    diff = it.get("difficulty") if it.get("difficulty") in ("기초", "중급", "응용") else "중급"
    return {
        "id": new_id("Q"), "category": sel_cat, "topic": target_keyword, "theory_id": theory_id,
        "difficulty": diff, "type": it.get("type", "concept"),
        "question": str(it["question"]).strip(), "options": [t for t, _ in pool], "answer": answer,
        "explanation": explanation,
    }


def review_drafts(label, drafts, review_system, build_review):
    """AI 검수. 한꺼번에 하다가 실패(출력 잘림 등)하면 한 개씩 나눠서 검수한다. 끝내 검수 못 한 것은 결과에 빠지고, 호출한 쪽이 규칙 검사만으로 판단한다."""
    try:
        reviews = call_json(M["review"], review_system, build_review(drafts), 0.2, 8000).get("reviews") or []
        return {r.get("index"): r for r in reviews if isinstance(r, dict)}
    except Exception as e:
        if len(drafts) < 2:
            raise
        print(f"   ⚠️ {label} 검수를 한꺼번에 하지 못해 한 개씩 검수합니다: {e}")
    out = {}
    for n, it in enumerate(drafts):
        try:
            for r in call_json(M["review"], review_system, build_review([it]), 0.2, 6000).get("reviews") or []:
                if isinstance(r, dict) and r.get("index") in (0, None):
                    out[n] = {**r, "index": n}
        except Exception as e:
            print(f"   ⚠️ {label} {n + 1} 검수 실패(규칙 검사만 적용): {e}")
    return out


def collect_items(label, want, make_drafts, review_system, build_review, check, max_rounds=5, existing=()):
    """초안 → AI 검수 → 규칙 검사를 거쳐 want 개를 '반드시' 채운다. 탈락해서 모자라면 부족한 만큼 다시 만든다(최대 max_rounds 번).
    끝내 못 채우면 예외를 던진다 → 호출한 쪽은 모자란 채로 저장하지 않는다.
    existing: 이미 있는 문항(겹치지 않게 만들기 위해 참고만 하고 개수에는 세지 않는다)."""
    final = []
    for rnd in range(max_rounds):
        need = want - len(final)
        if need <= 0:
            break
        ask = need + 1 if rnd == 0 else need   # 첫 라운드는 탈락분을 감안해 한 개 더 받는다
        if rnd:
            print(f"   ➕ 통과한 {label}이(가) {len(final)}개뿐이라 부족한 {need}개를 더 만듭니다. ({rnd + 1}/{max_rounds}번째 시도)")
        drafts = []
        try:
            drafts = make_drafts(ask, list(existing) + final)[:ask]
        except Exception as e:
            print(f"   ⚠️ {label} 초안 생성 실패: {e}")
            if need > 1:   # 여러 개를 한꺼번에 받다가 실패(출력 잘림 등)했으면 한 개씩 나눠서 받는다
                print(f"   ↪ {label}을(를) 한 개씩 나눠서 다시 만듭니다.")
                for _ in range(need):
                    try:
                        drafts += make_drafts(1, list(existing) + final + drafts)[:1]
                    except Exception as e2:
                        print(f"   ⚠️ {label} 초안 1개 생성 실패: {e2}")
        if not drafts:
            continue
        try:
            by_idx = review_drafts(label, drafts, review_system, build_review)
            for n, it in enumerate(drafts):
                if len(final) >= want:
                    break
                r = by_idx.get(n)
                if r is None:                      # 검수 누락 → 규칙만 통과하면 사용
                    cand = it
                elif r.get("verdict") == "drop":
                    print(f"   🗑️ {label} {n + 1} 제외: {'; '.join(map(str, r.get('issues', [])))[:120]}")
                    continue
                else:
                    cand = r.get("final") or it
                probs = check(cand)
                if probs:
                    print(f"   🗑️ {label} {n + 1} 제외(검수 후에도 규칙 위반): {probs}")
                    continue
                if r and r.get("verdict") == "fix":
                    print(f"   🔧 {label} {n + 1} 수정: {'; '.join(map(str, r.get('issues', [])))[:120]}")
                final.append(cand)
        except Exception as e:
            print(f"   ⚠️ {label} AI 검수 실패 → 규칙 검사만 통과한 초안 사용: {e}")
            final += [it for it in drafts if not check(it)]
    if len(final) < want:
        raise ValueError(f"검수를 통과한 {label}이(가) {len(final)}개뿐 (목표 {want}개, {max_rounds}번 시도)")
    return final[:want]


QUIZ_PER_THEORY = 3
INTERVIEW_PER_THEORY = 2


def generate_quiz(theory, theory_id, want=QUIZ_PER_THEORY, existing=()):
    final = collect_items(
        "문제", want,
        lambda need, have: call_json(M["qa"], QUIZ_SYSTEM, build_quiz_prompt(theory, need, have), 0.8, 8000).get("questions") or [],
        QUIZ_REVIEW_SYSTEM, lambda drafts: build_quiz_review_prompt(theory, drafts), check_quiz_item, existing=existing)
    return [compose_quiz(it, theory_id) for it in final]


INTERVIEW_SYSTEM = """당신은 반도체 대기업 공정·소자 직무 면접에서 실무 면접관을 맡는 10년차 엔지니어입니다. 지원자의 암기가 아니라 이해와 사고 과정을 보는 질문을 합니다. 반드시 유효한 JSON 객체 하나만 출력합니다. 수식 기호(백슬래시)는 쓰지 말고 일반 문자로 씁니다."""

INTERVIEW_SCHEMA = """{
  "interviews": [
    {
      "difficulty": "중급 | 고급 중 하나",
      "question": "면접관이 실제로 입으로 하는 질문 (한 가지만 묻기)",
      "follow_up": "지원자 답변을 듣고 면접관이 이어서 던질 꼬리 질문 1개",
      "follow_up_answer": "꼬리 질문에 대한 모범 답변 2~3문장",
      "key_points": ["면접관이 듣고 싶어 하는 핵심 키워드 3~4개"],
      "interview_answer": "지원자가 말로 하는 모범 답변"
    }
  ]
}"""


INTERVIEW_COMPOSITION = """1번 (개념 설명형): 핵심 개념을 지원자 자기 말로 풀게 하는 질문. 꼬리 질문으로 '왜 그런지'를 한 단계 더 파고듭니다.
2번 (상황·판단형): 공정·소자에서 마주칠 상황이나 trade-off를 제시하고 어떻게 판단·접근할지 묻는 질문. 꼬리 질문은 조건을 바꾸거나 한계를 묻습니다."""


def build_interview_prompt(theory, n=2, existing=None):
    comp = (INTERVIEW_COMPOSITION + ("\n나머지 질문: 위 둘과 겹치지 않는 다른 각도로" if n > 2 else "")) if n >= 2 else "개념 설명형 또는 상황·판단형 중 하나. 꼬리 질문으로 한 단계 더 파고듭니다."
    have = ("\n[이미 확보한 질문 - 이것과 겹치지 않는 다른 각도로 출제]\n" + "\n".join(f"- {str(e.get('question', ''))[:80]}" for e in existing) + "\n") if existing else ""
    return f"""아래 이론 글을 바탕으로, 실제 면접장에서 나올 법한 면접 질문 {n}개를 만드세요. 질문은 이론 범위에서 출제하되, 면접관의 말투와 맥락을 살립니다.

[질문 구성]
{comp}
{have}
[질문 규칙]
- 구어체 한두 문장. 예: "~에 대해 설명해 주시겠어요?", "~한 상황이라면 어떤 순서로 접근하시겠어요?" 교과서 문제처럼 항목을 줄줄이 요구하는 질문("정의, 원인, 대책을 모두 설명하라")은 금지입니다.
- 한 질문에는 한 가지만 묻습니다.
- 이론에 없는 내용을 알아야 답할 수 있는 질문은 금지입니다.

[모범 답변 규칙]
- 지원자가 말하는 정중한 구어체(합니다/해요 혼용 금지, ~입니다/~합니다 체).
- 구조: 결론 한 문장 → 이유·원리 2~3문장 → 한계·조건이나 실무 연결 1문장. 전체 5~8문장, 300~550자.
- 이론에 없는 구체 수치, 지어낸 사례, 해 본 적 없는 경험담("제가 현장에서 ~했을 때")은 금지입니다. 모르는 것을 아는 척하지 않고, 조건부로 신중하게 말합니다.
- 정확성이 최우선입니다. 단정하기 어려운 부분은 '일반적으로', '조건에 따라'로 범위를 밝힙니다.

[이론 글]
<<<
{theory}
>>>

아래 JSON 형식으로만 답하세요.
{INTERVIEW_SCHEMA}"""


def check_interview_item(it):
    probs = []
    try:
        q = str(it["question"]).strip(); fu = str(it["follow_up"]).strip()
        ans = str(it["interview_answer"]).strip(); fua = str(it["follow_up_answer"]).strip()
        kp = it["key_points"]
        if not isinstance(kp, list) or not (2 <= len(kp) <= 6) or not all(isinstance(k, str) and k.strip() for k in kp):
            return ["key_points 형식 오류"]
    except Exception:
        return ["필수 필드 누락/형식 오류"]
    if len(q) < 10 or len(q) > 160: probs.append("질문 길이가 부적절")
    if q.count("?") > 1: probs.append("한 질문에 여러 가지를 묻고 있음")
    if len(fu) < 8: probs.append("꼬리 질문이 너무 짧음")
    if not (200 <= len(ans) <= 800): probs.append(f"모범 답변 길이 부적절({len(ans)}자)")
    if len(fua) < 40: probs.append("꼬리 질문 답변이 너무 짧음")
    if cliche_hits(ans + fua) >= 3: probs.append("상투적 표현이 많음")
    if re.search(r"제가 (?:현장|실무|회사|인턴)에서", ans): probs.append("지어낸 경험담")
    return probs


INTERVIEW_REVIEW_SYSTEM = """당신은 면접 질문과 모범 답변을 검수하는 반도체 전문가이자 면접 코치입니다. 반드시 유효한 JSON 객체 하나만 출력합니다. 수식 기호(백슬래시)는 쓰지 않습니다."""


def build_interview_review_prompt(theory, items):
    listing = json.dumps([{"index": n, "item": it, "rule_problems": check_interview_item(it)} for n, it in enumerate(items)], ensure_ascii=False)
    return f"""아래 면접 문항 초안을 검수하세요. 기준은 다음과 같습니다.

1. 정확성(최우선): 모범 답변과 꼬리 질문 답변에 반도체 지식과 이론 글에 어긋나는 내용, 지어낸 수치·사례, 과도한 단정이 없는가?
2. 실제 면접 같은가: 면접관이 입으로 할 법한 자연스러운 질문인가? 한 번에 한 가지만 묻는가? 이론 밖 지식을 요구하지 않는가?
3. 답변 품질: 결론이 먼저 나오고, 이유가 인과로 이어지며, 한계·조건을 밝히는가? 말로 했을 때 자연스러운가? 상투적인 빈말이 없는가?
4. key_points: 면접관이 실제로 체크할 핵심 키워드인가?
rule_problems 는 반드시 해결하세요.

verdict: ok(final 에 원본) / fix(고친 완성본을 final 에, 같은 스키마) / drop(살릴 수 없음, final null)

[이론 글]
<<<
{theory}
>>>

[면접 초안]
{listing}

아래 JSON 형식으로만 답하세요.
{{"reviews": [{{"index": 0, "verdict": "ok|fix|drop", "issues": ["발견한 문제 요약"], "final": {{...같은 item 스키마...}} 또는 null}}]}}"""


def compose_interview(it, theory_id):
    return {
        "id": new_id("INT"), "category": sel_cat, "topic": target_keyword, "theory_id": theory_id,
        "difficulty": it.get("difficulty") if it.get("difficulty") in ("중급", "고급") else "고급",
        "question": str(it["question"]).strip(), "follow_up": str(it["follow_up"]).strip(),
        "follow_up_answer": str(it["follow_up_answer"]).strip(),
        "key_points": [k.strip() for k in it["key_points"]], "interview_answer": str(it["interview_answer"]).strip(),
    }


def generate_interview(theory, theory_id, want=INTERVIEW_PER_THEORY, existing=()):
    final = collect_items(
        "면접", want,
        lambda need, have: call_json(M["qa"], INTERVIEW_SYSTEM, build_interview_prompt(theory, need, have), 0.7, 8000).get("interviews") or [],
        INTERVIEW_REVIEW_SYSTEM, lambda drafts: build_interview_review_prompt(theory, drafts), check_interview_item, existing=existing)
    return [compose_interview(it, theory_id) for it in final]


def generate_unified_content():
    if target_keyword is None:
        print("✅ topics의 모든 키워드가 이미 등재/대기 중입니다. 새 키워드를 추가해 주세요. (API 호출 없이 종료)")
        return
    pending = len([d for d in load_json_list(draft_t_path) if not d.get("replaces")])  # 문체 변환 초안은 한도에 세지 않음
    if pending >= MAX_PENDING_DRAFTS:
        print(f"⏸️ 검수 대기 이론이 {pending}개 쌓여 있어 이번 실행은 건너뜁니다. (API 호출 없이 종료)")
        return

    print(f"[{target_keyword}] 기반 통합 콘텐츠 생성 시작...")

    # 이론 + 객관식 + 면접이 '모두' 만들어졌을 때만 한꺼번에 저장한다.
    # (하나라도 모자라면 아무것도 저장하지 않는다 → 검수소에 문항이 모자란 이론이 올라가지 않고, 이 키워드는 다음 실행에서 다시 시도된다)

    # 1. 📖 이론 백과사전 생성 (3단계 분할)
    try:
        theory_content = generate_theory()
        theory_content, auto_dg = ensure_diagrams(target_keyword, theory_content)   # AI 가 빼먹어도 제목에 맞는 그림은 넣는다
        if auto_dg:
            print(f"   🖼 눌러 보는 그림 자동 삽입: {', '.join(auto_dg)}")
    except Exception as e:
        print(f"⚠️ 이론 생성 실패 → 아무것도 저장하지 않고 종료합니다: {e}")
        return
    theory_id = new_id("TH")
    print("✅ 1/3 이론 생성 완료 (아직 저장 전)")

    # 2. 📝 객관식
    try:
        quiz_json = generate_quiz(theory_content, theory_id)
        print(f"✅ 2/3 이론 연계 객관식 {len(quiz_json)}개 준비 완료")
    except Exception as e:
        print(f"⚠️ 객관식을 목표만큼 만들지 못했습니다 → 아무것도 저장하지 않고 종료합니다 (다음 실행에서 다시 시도): {e}")
        return

    # 3. 🗣️ 면접
    try:
        interview_json = generate_interview(theory_content, theory_id)
        print(f"✅ 3/3 이론 연계 실무 면접 {len(interview_json)}개 준비 완료")
    except Exception as e:
        print(f"⚠️ 면접을 목표만큼 만들지 못했습니다 → 아무것도 저장하지 않고 종료합니다 (다음 실행에서 다시 시도): {e}")
        return

    # 4. 💾 한꺼번에 저장 (문항 → 이론 순서: 도중에 끊겨도 '문항만 있고 이론이 없는' 쪽으로 남아 고아 문항은 fill/정리로 처리 가능)
    save_draft(draft_q_path, quiz_json)
    save_draft(draft_i_path, interview_json)
    save_draft(draft_t_path, [{
        "id": theory_id,
        "category": sel_cat,
        "subject": sel_sub,
        "title": target_keyword,
        "tags": [target_keyword.replace(" ", ""), "핵심이론"],
        "content": theory_content,
    }])
    print(f"💾 저장 완료: 이론 1 + 객관식 {len(quiz_json)} + 면접 {len(interview_json)}")


if __name__ == "__main__":
    generate_unified_content()
