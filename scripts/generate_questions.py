import os
import json
import random
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "guide": "N형/P형, 에너지 밴드, 캐리어 등 기초 물리 위주"},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자", "guide": "MOSFET, 채널, 누설 전류 등 소자 원리 위주"},
    {"category": "반도체 기초 이론", "subject": "메모리 반도체", "guide": "DRAM, NAND 플래시의 구조 및 동작 원리"},
    {"category": "반도체 8대 공정", "subject": "1. 웨이퍼 제조 공정", "guide": "초크랄스키법, 잉곳, 슬라이싱, 폴리싱 등 웨이퍼 자체 제조"},
    {"category": "반도체 8대 공정", "subject": "2. 산화 공정 (Oxidation)", "guide": "건식/습식 산화, 산화막의 절연 역할"},
    {"category": "반도체 8대 공정", "subject": "3. 포토 공정 (Photo)", "guide": "EUV, PR, 노광 원리, 해상도 등 포토 공정 전용"},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "guide": "건식/습식 식각, 플라즈마, 비등방성/선택비 등 식각 공정 전용"},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)", "guide": "CVD, ALD, PVD 등 증착 원리와 단차 피복성"},
    {"category": "반도체 8대 공정", "subject": "6. 금속 배선 공정 (Metallization)", "guide": "구리 다마신 공정, 장벽 금속, 배선 저항(RC 지연) 등 배선 전용"},
    {"category": "반도체 8대 공정", "subject": "7. EDS 공정 (Testing)", "guide": "웨이퍼 테스트, 수율, 프로브 카드 등 테스트 전용"},
    {"category": "반도체 8대 공정", "subject": "8. 패키징 공정 (Packaging)", "guide": "플립칩, 와이어본딩, 다이싱 등"},
    {"category": "차세대 첨단 기술", "subject": "차세대 소자 기술", "guide": "FinFET, GAA(MBCFET), 2D 소자 등"},
    {"category": "차세대 첨단 기술", "subject": "어드밴스드 패키징", "guide": "HBM, TSV, 하이브리드 본딩, 칩렛 등 차세대 패키징"}
]

draft_q_path = "data/draft_questions.json"
draft_i_path = "data/draft_interviews.json"

selected = random.choice(topics)
sel_category = selected["category"]
sel_subject = selected["subject"]
sel_guide = selected["guide"]

# ✨ 면접 난이도 3개 중 랜덤 2개 추출
chosen_diffs = random.sample(["초급", "중급", "고급"], 2)

# 1. 객관식 시험 생성
PROMPT_QUIZ = f"""
당신은 반도체 공정 전공 교수입니다. 대분류 '{sel_category}', 세부 주제 '{sel_subject}'에 대한 필수 전공 이론 암기를 검증할 객관식 문제 3개를 생성해 주세요.
[출제 규칙]:
1. "다음 중 틀린 것은?" 같은 부정형 질문 절대 금지. 핵심 개념의 정의와 원리를 묻는 긍정형 질문으로 작성.
2. 난이도는 "초급", "중급", "고급"으로 1개씩. 보기 중 오답도 헷갈리는 전공 용어로 구성.

반드시 아래 JSON 배열 형식으로만 응답하세요.
[
  {{
    "id": "Q-{random.randint(10000,99999)}",
    "category": "{sel_category}",
    "topic": "{sel_subject}",
    "difficulty": "초급",
    "question": "전공 이론 및 개념을 묻는 긍정형 지문",
    "options": ["보기1", "보기2", "보기3", "보기4"],
    "answer": 0,
    "explanation": "이론적 메커니즘과 오답 해설"
  }}
]
"""

# 2. 실무 면접 (구체적 상황, 특정 물질, 이론 기반 트러블슈팅)
PROMPT_INTERVIEW = f"""
당신은 반도체 대기업의 깐깐한 실무진 면접관입니다. 대분류 '{sel_category}', 세부 주제 '{sel_subject}'와 관련하여, 지원자의 **전공 이론 기반 실무 트러블슈팅 능력**을 검증할 아주 구체적인 면접 질문 2개를 생성해 주세요.

[출제 규칙 - 매우 중요]:
1. "수율이 떨어지면 어떻게 할 것인가?" 같은 포괄적이고 뻔한 질문은 절대 금지합니다.
2. 질문 지문에는 반드시 **[특정 공정 단계], [사용 중인 구체적 물질이나 가스], [발생한 구체적인 물리적/화학적 결함 상황]**이 명확하게 제시되어야 합니다.
   (예시: "고종횡비(High Aspect Ratio) 식각 공정에서 C4F8 가스를 사용할 때 패턴 하단부에 Bowing 현상이 발생했습니다. 이를 해결하기 위해 플라즈마 파라미터를 어떻게 조정해야 하며, 그 물리적 근거는 무엇인가요?")
3. 지원자가 단순 경험이 아니라, '전공 이론과 메커니즘'을 바탕으로 논리적인 엔지니어링 조치를 답변할 수밖에 없도록 질문을 뾰족하게 깎으세요.
4. 해설(interview_answer)은 실제 면접에서 답변할 수 있는 '모범 두괄식 스크립트'로 작성하되, 파라미터 조절의 이론적 근거가 탄탄하게 포함되어야 합니다.

반드시 아래 JSON 배열 형식으로만 응답하세요. (마크다운 생략)
[
  {{
    "id": "INT-{random.randint(10000,99999)}",
    "category": "{sel_category}",
    "topic": "{sel_subject}",
    "difficulty": "고급",
    "question": "구체적인 물질/상황/이론이 포함된 핀포인트 실무 면접 질문",
    "key_points": ["반드시 포함해야 할 전공 핵심 키워드1", "키워드2"],
    "interview_answer": "전공 이론과 원리에 근거한 두괄식 모범 답변 스크립트"
  }}
]
"""
[
  {{
    "id": "INT-{random.randint(10000,99999)}",
    "category": "{sel_category}",
    "topic": "{sel_subject}",
    "difficulty": "고급",
    "question": "구체적인 물질/상황/이론이 포함된 핀포인트 실무 면접 질문",
    "key_points": ["반드시 포함해야 할 전공 핵심 키워드1", "키워드2"],
    "interview_answer": "전공 이론과 원리에 근거한 두괄식 모범 답변 스크립트"
  }}
]
"""

def generate_contents():
    # 객관식 생성
    res_q = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You strictly output a valid JSON array."}, {"role": "user", "content": PROMPT_QUIZ}],
        temperature=0.8
    )
    new_questions = json.loads(res_q.choices[0].message.content.replace("```json", "").replace("```", "").strip())
    
    # 면접 생성
    res_i = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You strictly output a valid JSON array."}, {"role": "user", "content": PROMPT_INTERVIEW}],
        temperature=0.8
    )
    new_interviews = json.loads(res_i.choices[0].message.content.replace("```json", "").replace("```", "").strip())

    existing_draft_q = []
    if os.path.exists(draft_q_path):
        with open(draft_q_path, "r", encoding="utf-8") as f:
            try: existing_draft_q = json.load(f)
            except: pass
    with open(draft_q_path, "w", encoding="utf-8") as f:
        json.dump(new_questions + existing_draft_q, f, ensure_ascii=False, indent=2)

    existing_draft_i = []
    if os.path.exists(draft_i_path):
        with open(draft_i_path, "r", encoding="utf-8") as f:
            try: existing_draft_i = json.load(f)
            except: pass
    with open(draft_i_path, "w", encoding="utf-8") as f:
        json.dump(new_interviews + existing_draft_i, f, ensure_ascii=False, indent=2)

    print(f"시험 {len(new_questions)}개, 면접 {len(new_interviews)}개 대기소 저장 완료! (면접 난이도: {chosen_diffs[0]}, {chosen_diffs[1]})")

if __name__ == "__main__":
    generate_contents()
