import os
import json
import random
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

topics = [
    {"category": "반도체 기초 이론", "subject": "반도체 물리", "keywords": ["에너지 밴드", "페르미 준위", "캐리어 농도", "PN 접합"]},
    {"category": "반도체 기초 이론", "subject": "트랜지스터 소자", "keywords": ["MOSFET 동작 원리", "채널 길이 변조", "단채널 효과 (SCE)", "누설 전류"]},
    {"category": "반도체 기초 이론", "subject": "메모리 반도체", "keywords": ["DRAM 커패시터", "NAND 플래시 부유게이트", "CTF 구조", "읽기/쓰기 메커니즘"]},
    {"category": "반도체 8대 공정", "subject": "2. 산화 공정 (Oxidation)", "keywords": ["건식 vs 습식 산화", "딜그로브(Deal-Grove) 모델", "산화막의 역할"]},
    {"category": "반도체 8대 공정", "subject": "3. 포토 공정 (Photo)", "keywords": ["EUV 리소그래피", "포토레지스트(PR)", "해상도(Resolution)와 초점심도(DOF)", "OPC"]},
    {"category": "반도체 8대 공정", "subject": "4. 식각 공정 (Etching)", "keywords": ["건식 식각 (Dry Etch)", "플라즈마 식각 원리", "식각 선택비(Selectivity)", "비등방성(Anisotropy)", "Bowing / Notching 불량"]},
    {"category": "반도체 8대 공정", "subject": "5. 박막 증착 공정 (Deposition)", "keywords": ["CVD (화학 기상 증착)", "ALD (원자층 증착)", "PVD (물리 기상 증착)", "단차 피복성 (Step Coverage)"]},
    {"category": "차세대 첨단 기술", "subject": "어드밴스드 패키징", "keywords": ["HBM", "TSV (실리콘 관통 전극)", "하이브리드 본딩 (Hybrid Bonding)", "칩렛 (Chiplet)"]}
]

draft_t_path = "data/draft_theories.json"

selected = random.choice(topics)
sel_category = selected["category"]
sel_subject = selected["subject"]
target_keyword = random.choice(selected["keywords"])

# 💡 양파CBT급 퀄리티를 위한 1타 강사 프롬프트 (마크다운 강제)
PROMPT_THEORY = f"""
당신은 반도체 취업 및 전공 시험 대비 1타 강사입니다. 
대분류 '{sel_category}', 세부 주제 '{sel_subject}'의 핵심 키워드인 **[{target_keyword}]**에 대해 수험생이 5분 만에 완벽히 이해하고 암기할 수 있는 고퀄리티 요약 노트를 작성해 주세요.

[작성 규칙 및 마크다운(Markdown) 포맷 강제]:
반드시 아래의 5가지 섹션 구조를 마크다운 기호(#, -, |, ** 등)를 적극 활용하여 시각적으로 아름답게 작성하세요. 일반 줄글 형태는 절대 금지합니다.

### 1. 💡 한 줄 요약
(이 기술/공정이 왜 존재하는지 직관적이고 명쾌한 1~2문장 요약)

### 2. ⚙️ 핵심 작동 원리 (메커니즘)
(작동 원리나 공정 순서를 1, 2, 3 단계별 글머리 기호로 정리. 핵심 용어는 **굵은 글씨** 처리)

### 3. 📊 비교 분석 테이블
(헷갈리기 쉬운 유사 개념이나 공정(예: 건식vs습식, CVDvsPVD 등)의 장단점 및 특징을 Markdown Table(| | |) 형식으로 정리)

### 4. 🚨 실무 및 면접 빈출 포인트
(실제 팹(Fab)에서 발생하는 주요 불량 이슈나 면접관이 자주 묻는 함정 포인트 2가지 요약)

### 5. 🧠 1타 강사의 암기 팁
(초보자도 쉽게 외울 수 있는 기발한 비유나 앞글자 암기법 등)

반드시 아래 JSON 배열 형식으로만 응답하세요. (백틱 ```json 등 제외)
[
  {{
    "id": "TH-{random.randint(10000,99999)}",
    "category": "{sel_category}",
    "subject": "{sel_subject}",
    "title": "{target_keyword} 완벽 마스터",
    "tags": ["{target_keyword.replace(' ', '')}", "전공핵심", "면접대비"],
    "content": "위에서 요구한 5가지 섹션이 완벽하게 적용된 마크다운 형식의 텍스트"
  }}
]
"""

def generate_theory():
    print(f"[{sel_subject} - {target_keyword}] 이론 데이터 생성 중...")
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You strictly output a valid JSON array."}, {"role": "user", "content": PROMPT_THEORY}],
        temperature=0.7
    )
    
    new_theory = json.loads(res.choices[0].message.content.replace("```json", "").replace("```", "").strip())

    existing_draft_t = []
    if os.path.exists(draft_t_path):
        with open(draft_t_path, "r", encoding="utf-8") as f:
            try: existing_draft_t = json.load(f)
            except: pass
            
    with open(draft_t_path, "w", encoding="utf-8") as f:
        json.dump(new_theory + existing_draft_t, f, ensure_ascii=False, indent=2)

    print(f"✅ 고퀄리티 이론 1건이 {draft_t_path}에 저장되었습니다!")

if __name__ == "__main__":
    generate_theory()
