import os
import json
import random
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "keywords": ["에너지 밴드", "페르미 준위", "캐리어 농도", "PN 접합"]},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자", "keywords": ["MOSFET", "채널 길이 변조", "단채널 효과", "누설 전류"]},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "keywords": ["건식 식각", "플라즈마 식각", "식각 선택비", "Bowing 현상"]},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정", "keywords": ["CVD 공정", "ALD 공정", "PVD 공정", "단차 피복성"]}
]

draft_t_path = "data/draft_theories.json"

selected = random.choice(topics)
sel_category = selected["category"]
sel_subject = selected["subject"]
target_keyword = random.choice(selected["keywords"])

def generate_deep_theory():
    print(f"[{target_keyword}] 3단계 이론 중심(인라인 코멘트) 데이터 생성 시작...")
    
    # [STEP 1] 처음부터 끝까지 끊기지 않는 '이론 중심' 서사 구축
    msg1 = [
        {"role": "system", "content": "당신은 반도체 공정 전공 1타 강사입니다."},
        {"role": "user", "content": f"'{target_keyword}'에 대해 서론-본론-결론이 있는 완벽한 '이론 위주'의 전공 지식 해설서를 작성하세요. 단편적인 요약이 아니라, 처음부터 끝까지 이론적 흐름과 메커니즘이 끊기지 않고 자연스럽게 이어지도록 깊이 있게 서술하세요."}
    ]
    res1 = client.chat.completions.create(model="gpt-4o-mini", messages=msg1, temperature=0.7).choices[0].message.content

    # [STEP 2] 이론 흐름 중간중간에 코멘트(실무/면접 팁) 자연스럽게 삽입
    msg2 = msg1 + [
        {"role": "assistant", "content": res1},
        {"role": "user", "content": "훌륭합니다. 이제 이 전체적인 이론적 흐름을 그대로 유지하면서, 관련된 핵심 이론 설명이 끝나는 부분 바로 밑에 코멘트 형식으로 '실무 트러블슈팅'이나 '면접 꿀팁'을 삽입해 주세요.\n\n코멘트는 글 마지막에 따로 모아두지 말고, 반드시 본문 중간중간 적절한 위치에 `> 💡 [면접 코멘트] ...` 또는 `> 💡 [실무 코멘트] ...` 형식을 사용해 배치하세요. 필요한 경우 헷갈리는 개념 비교 표(Table)도 본문 중간에 추가하세요."}
    ]
    res2 = client.chat.completions.create(model="gpt-4o-mini", messages=msg2, temperature=0.7).choices[0].message.content

    # [STEP 3] 최종 UI 포맷팅 및 제목 길이 강제 제한
    msg3 = msg2 + [
        {"role": "assistant", "content": res2},
        {"role": "user", "content": f"""
지금까지의 내용을 모두 종합하여, 최종 요약 노트를 아래의 엄격한 규칙과 JSON 구조로 반환해 주세요.

[작성 규칙]:
1. 전체 글은 처음부터 끝까지 '이론'이 중심이 되어 자연스럽게 읽혀야 합니다.
2. 중간중간 들어간 코멘트 박스는 반드시 `> 💡 [실무 코멘트] ...` 형태를 그대로 유지하세요.
3. 소제목은 `### [원리] CVD의 메커니즘` 처럼 대괄호 뱃지 형태를 포함하세요.

반드시 아래 JSON 배열 형식으로만 응답하세요. 제목(title)은 수식어나 문장 없이 '{target_keyword}' 처럼 짧은 핵심 명사형으로만 작성하세요. (예: CVD 공정, 단채널 효과)
[
  {{
    "id": "TH-{random.randint(10000,99999)}",
    "category": "{sel_category}",
    "subject": "{sel_subject}",
    "title": "{target_keyword}",
    "tags": ["{target_keyword.replace(' ', '')}", "전공이론"],
    "content": "이론 중심의 흐름과 중간 인라인 코멘트가 완벽히 결합된 마크다운 텍스트 전문"
  }}
]
"""}
    ]
    res3 = client.chat.completions.create(model="gpt-4o-mini", messages=msg3, temperature=0.7)
    
    new_theory = json.loads(res3.choices[0].message.content.replace("```json", "").replace("```", "").strip())

    existing_draft_t = []
    if os.path.exists(draft_t_path):
        with open(draft_t_path, "r", encoding="utf-8") as f:
            try: existing_draft_t = json.load(f)
            except: pass
            
    with open(draft_t_path, "w", encoding="utf-8") as f:
        json.dump(new_theory + existing_draft_t, f, ensure_ascii=False, indent=2)

    print(f"✅ 이론 서사 + 인라인 코멘트 데이터 생성 완료!")

if __name__ == "__main__":
    generate_deep_theory()
