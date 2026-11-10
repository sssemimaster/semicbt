import os
import json
import random
import re
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "keywords": ["에너지 밴드", "페르미 준위", "캐리어 농도", "PN 접합", "유효 질량"]},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자", "keywords": ["MOSFET", "채널 길이 변조", "단채널 효과 (SCE)", "누설 전류", "문턱 전압"]},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "keywords": ["건식 식각", "플라즈마 식각", "식각 선택비", "Bowing 현상"]},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)", "keywords": ["CVD 공정", "ALD 공정", "PVD 공정", "단차 피복성"]}
]

draft_t_path = "data/draft_theories.json"
draft_q_path = "data/draft_questions.json"
draft_i_path = "data/draft_interviews.json"

selected = random.choice(topics)
sel_cat = selected["category"]
sel_sub = selected["subject"]
target_keyword = random.choice(selected["keywords"])

def clean_json_string(raw_str):
    cleaned = raw_str.replace("```json", "").replace("```", "").strip()
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    return cleaned

def generate_unified_content():
    print(f"[{target_keyword}] 기반 통합 콘텐츠 생성 시작...")
    
    # ----------------------------------------------------
    # 1. 📖 이론 백과사전 생성
    # ----------------------------------------------------
    msg_theory = [
        {"role": "system", "content": "당신은 반도체 공정 1타 강사입니다. 수식은 반드시 LaTeX 문법을 사용하며, 인라인 수식은 $...$, 블록 수식은 $$...$$로 감싸주세요."},
        {"role": "user", "content": f"""
'{target_keyword}'에 대한 깊이 있는 이론 해설서를 작성하세요.
- 전체 글은 이론 중심 서사로 이어져야 합니다.
- 중간에 `> 💡 [실무 코멘트] ...` 같은 인라인 팁을 1~2개 섞어주세요.
- 소제목은 `### [원리] ...` 형태로 작성하세요.
- JSON 배열로 응답하고, 내부 큰따옴표는 반드시 이스케이프(\\")하세요.

[
  {{
    "id": "TH-{random.randint(10000,99999)}",
    "category": "{sel_cat}",
    "subject": "{sel_sub}",
    "title": "{target_keyword}",
    "tags": ["{target_keyword.replace(' ', '')}", "핵심이론"],
    "content": "이론 중심 서사 마크다운 전문"
  }}
]
"""}
    ]
    res_t = client.chat.completions.create(model="gpt-4o-mini", messages=msg_theory, temperature=0.7)
    theory_json = json.loads(clean_json_string(res_t.choices[0].message.content))
    theory_content = theory_json[0]['content'] # 방금 쓴 이론 내용을 추출

    # ----------------------------------------------------
    # 2. 📝 이론 기반 객관식 생성
    # ----------------------------------------------------
    msg_quiz = [
        {"role": "system", "content": "You strictly output a valid JSON array. 수식은 $ 또는 $$ 로 감싸세요."},
        {"role": "user", "content": f"""
다음은 방금 생성된 '{target_keyword}'에 대한 이론입니다:
{theory_content}

이 이론 내용만을 바탕으로, 이론을 제대로 읽었는지 검증하는 긍정형 객관식 기출문제 3개를 만들어주세요. 부정형("아닌 것은?") 질문은 금지합니다.
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
    for q in quiz_json: # 정답 셔플링
        correct_text = q["options"][q["answer"]]
        random.shuffle(q["options"])
        q["answer"] = q["options"].index(correct_text)

    # ----------------------------------------------------
    # 3. 🗣️ 이론 기반 면접 생성
    # ----------------------------------------------------
    msg_int = [
        {"role": "system", "content": "You strictly output a valid JSON array."},
        {"role": "user", "content": f"""
다음 이론을 바탕으로:
{theory_content}

지원자가 이 이론을 실무에 어떻게 적용하는지 묻는 날카로운 면접 질문 2개를 만드세요.
(질문에 구체적인 물질/상황을 포함할 것)
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

    # ----------------------------------------------------
    # 4. 파일 저장
    # ----------------------------------------------------
    def save_draft(path, new_data):
        existing = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                try: existing = json.load(f)
                except: pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_data + existing, f, ensure_ascii=False, indent=2)

    save_draft(draft_t_path, theory_json)
    save_draft(draft_q_path, quiz_json)
    save_draft(draft_i_path, interview_json)
    print(f"✅ 통합 생성 완료! (이론 1, 퀴즈 3, 면접 2)")

if __name__ == "__main__":
    generate_unified_content()
