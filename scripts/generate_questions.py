import os
import json
import random
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ✨ AI가 다른 공정의 내용을 침범하지 못하도록 'guide' 지침 추가
topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "guide": "N형/P형, 에너지 밴드, 캐리어 등 기초 물리 위주"},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자", "guide": "MOSFET, 채널, 누설 전류 등 소자 원리 위주"},
    {"category": "반도체 기초 이론", "subject": "메모리 반도체", "guide": "DRAM, NAND 플래시의 구조 및 동작 원리"},
    {"category": "반도체 8대 공정", "subject": "1. 웨이퍼 제조 공정", "guide": "초크랄스키법, 잉곳, 슬라이싱, 폴리싱 등 웨이퍼 자체 제조"},
    {"category": "반도체 8대 공정", "subject": "2. 산화 공정 (Oxidation)", "guide": "건식/습식 산화, 산화막의 절연 역할"},
    {"category": "반도체 8대 공정", "subject": "3. 포토 공정 (Photo)", "guide": "EUV, PR, 노광 원리, 해상도 등 포토 공정 전용"},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "guide": "건식/습식 식각, 플라즈마, 비등방성/선택비 등 식각 공정 전용"},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)", "guide": "CVD, ALD, PVD 등 증착 원리와 단차 피복성 (※ 반드시 CVD와 ALD는 이 폴더에만 작성할 것)"},
    {"category": "반도체 8대 공정", "subject": "6. 금속 배선 공정 (Metallization)", "guide": "구리 다마신 공정, 장벽 금속, 배선 저항(RC 지연) 등 배선 전용 (※ 일반 증착/CVD 원리에 대한 설명은 절대 작성 금지)"},
    {"category": "반도체 8대 공정", "subject": "7. EDS 공정 (Testing)", "guide": "웨이퍼 테스트, 수율, 프로브 카드 등 테스트 전용"},
    {"category": "반도체 8대 공정", "subject": "8. 패키징 공정 (Packaging)", "guide": "플립칩, 와이어본딩, 다이싱 등 (※ 차세대 HBM 등은 제외)"},
    {"category": "차세대 첨단 기술", "subject": "차세대 소자 기술", "guide": "FinFET, GAA(MBCFET), 2D 소자 등"},
    {"category": "차세대 첨단 기술", "subject": "어드밴스드 패키징", "guide": "HBM, TSV, 하이브리드 본딩, 칩렛 등 차세대 패키징"}
]

selected = random.choice(topics)
sel_category = selected["category"]
sel_subject = selected["subject"]
sel_guide = selected["guide"]

PROMPT_QUIZ = f"""
당신은 반도체 기업의 직무 면접관입니다. 대분류 '{sel_category}', 세부 주제 '{sel_subject}'에 대한 객관식 문제를 5개 생성해 주세요.
[출제 지침]: {sel_guide} (이 지침에 해당하는 영역만 출제하고 다른 공정의 내용은 침범하지 마세요.)

반드시 아래 형식을 가진 JSON 배열(Array)로만 응답하세요. (마크다운 생략)
[
  {{
    "id": "AUTO-{random.randint(10000,99999)}",
    "category": "{sel_category}",
    "topic": "{sel_subject} 내부 세부 토픽",
    "difficulty": "중급",
    "question": "문제 지문",
    "options": ["보기1", "보기2", "보기3", "보기4"],
    "answer": 0,
    "explanation": "상세 해설",
    "flashcard_keywords": ["키워드1", "키워드2"],
    "interview_answer": "두괄식 형태의 면접 답변 스크립트"
  }}
]
"""

PROMPT_THEORY = f"""
당신은 반도체 공정기술 수석 엔지니어입니다. 
대분류 '{sel_category}', 중분류 '{sel_subject}'에 속하는 구체적인 심화 기술을 하나 선정하여 새로운 백과사전 글을 작성해 주세요.
[작성 지침]: {sel_guide} (반드시 이 지침에 해당하는 영역만 다루고 다른 공정의 내용을 침범하지 마세요.)

반드시 아래 형식을 가진 JSON 배열(Array)로만 응답하세요. (마크다운 생략)
[
  {{
    "id": "AUTO-T-{random.randint(100000,999999)}",
    "category": "{sel_category}",
    "subject": "{sel_subject}",
    "title": "선정한 구체적인 심화 기술 제목",
    "content": "선정한 기술에 대해 3~4문단으로 깊이 있고 풍부하게 설명할 것. 문단 바꿈은 \\n\\n 으로 명확히 구분할 것.",
    "tags": ["키워드1", "키워드2", "키워드3"]
  }}
]
"""

def generate_contents():
    res_q = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You strictly output a valid JSON array."},
            {"role": "user", "content": PROMPT_QUIZ}
        ],
        temperature=0.7
    )
    new_questions = json.loads(res_q.choices[0].message.content.replace("```json", "").replace("```", "").strip())
    
    res_t = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You strictly output a valid JSON array."},
            {"role": "user", "content": PROMPT_THEORY}
        ],
        temperature=0.8 
    )
    new_theories = json.loads(res_t.choices[0].message.content.replace("```json", "").replace("```", "").strip())

    q_path = "data/questions.json"
    with open(q_path, "r", encoding="utf-8") as f:
        existing_q = json.load(f)
    with open(q_path, "w", encoding="utf-8") as f:
        json.dump(new_questions + existing_q, f, ensure_ascii=False, indent=2)
        
    t_path = "data/theories.json"
    with open(t_path, "r", encoding="utf-8") as f:
        existing_t = json.load(f)
    with open(t_path, "w", encoding="utf-8") as f:
        json.dump(new_theories + existing_t, f, ensure_ascii=False, indent=2)

    print(f"새로운 문제 {len(new_questions)}개, 심화 이론 {len(new_theories)}개 생성 완료!")

if __name__ == "__main__":
    generate_contents()
