import os
import json
import random
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ✨ 1단계와 2단계의 '절대 틀'을 현재 이론 백과사전과 완벽히 동일하게 고정
topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리"},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자"},
    {"category": "반도체 기초 이론", "subject": "메모리 반도체"},
    {"category": "반도체 8대 공정", "subject": "1. 웨이퍼 제조 공정"},
    {"category": "반도체 8대 공정", "subject": "2. 산화 공정 (Oxidation)"},
    {"category": "반도체 8대 공정", "subject": "3. 포토 공정 (Photo)"},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)"},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)"},
    {"category": "반도체 8대 공정", "subject": "6. 금속 배선 공정 (Metallization)"},
    {"category": "반도체 8대 공정", "subject": "7. EDS 공정 (Testing)"},
    {"category": "반도체 8대 공정", "subject": "8. 패키징 공정 (Packaging)"},
    {"category": "차세대 첨단 기술", "subject": "차세대 소자 기술"},
    {"category": "차세대 첨단 기술", "subject": "어드밴스드 패키징"}
]
selected = random.choice(topics)
sel_category = selected["category"]
sel_subject = selected["subject"]

PROMPT_QUIZ = f"""
당신은 반도체 기업의 직무 면접관입니다. 대분류 '{sel_category}', 세부 주제 '{sel_subject}'와 관련된 정석적이고 범용적인 객관식 문제를 5개 생성해 주세요.
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

# ✨ (심화) 괄호 제거 & path의 앞 2단계를 강제로 고정시켜 3단계부터 뻗어나가도록 지시
PROMPT_THEORY = f"""
당신은 반도체 공정기술 수석 엔지니어입니다. 
대분류 '{sel_category}', 중분류 '{sel_subject}'에 속하는 기술 중 하나를 골라, 하위 개념으로 파고드는 구체적인 심화 주제(예: 실무 트러블슈팅, 설비 원리 등)를 선정해 '핵심 요약 노트'를 작성해 주세요.

반드시 아래 형식을 가진 JSON 배열(Array)로만 응답하세요. (마크다운 생략)
[
  {{
    "id": "AUTO-T-{random.randint(100000,999999)}",
    "path": ["{sel_category}", "{sel_subject}", "새로운 3단계 세부 가지(예: 건식 식각)", "필요시 4단계 심화 가지"],
    "title": "선정한 구체적인 기술 제목",
    "content": "구구절절한 서술형을 피하고, '-' 기호를 사용해 1) 핵심 개념, 2) 장단점, 3) 실무 적용 등을 3~4줄의 개조식(Bullet point)으로 짧고 직관적이게 요약할 것. 줄바꿈은 \\n 처리.",
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
