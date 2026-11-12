"""이론 글에 넣을 수 있는 '눌러 보는 그림'의 목록과, 어떤 이론에 어떤 그림을 붙일지의 규칙.

그림 자체(SVG)는 index.html 의 DIAGRAMS 에 있다. 새 그림을 만들면 여기 DIAGRAMS 와 RULES 에도 같은 id 를 적는다.
 - generate_all.py : 새 이론이 만들어질 때 AI 에게 그림 목록을 보여 주고, AI 가 빼먹어도 RULES 에 맞으면 자동으로 넣는다.
 - add_diagrams.py : 이미 있는 이론에 같은 규칙으로 그림을 넣는다.
"""
import re

DIAGRAMS = {
    "dram-cell": "DRAM 1T1C 셀 회로도. 대기·쓰기 1·쓰기 0·읽기(1 저장)·읽기(0 저장) 상태별 워드라인/비트라인 전압, 트랜지스터 ON/OFF, 전하 이동. DRAM 셀의 읽기·쓰기·센스 앰프 설명에 사용",
    "mosfet": "NMOS 단면. 차단·선형·포화·채널 길이 변조 상태별 채널 모양과 전류. MOSFET 동작, 문턱 전압, 채널 길이 변조 설명에 사용",
    "pn-junction": "PN 접합. 평형·순방향·역방향 바이어스에서 공핍층 폭, 내부 전계, 캐리어, 전류. PN 접합·다이오드 설명에 사용",
    "band-doping": "에너지 밴드 다이어그램. 금속·반도체·절연체 비교, 진성·n형·p형의 페르미 준위와 캐리어. 에너지 밴드, 페르미 준위, 캐리어 농도, 도핑 설명에 사용",
    "photo-process": "포토 공정 단면. 감광막 도포→노광→현상→식각→감광막 제거. 노광·포토레지스트·패턴 전사 설명에 사용",
    "etch-profile": "식각 단면. 등방성·이방성·보잉·낮은 선택비. 건식/습식 식각, 플라즈마 식각, 식각 선택비, 보잉 설명에 사용",
    "step-coverage": "홈(트렌치) 안 박막 두께. PVD·CVD·ALD의 단차 피복성 비교. 박막 증착, 단차 피복성, CVD·ALD·PVD 설명에 사용",
    "damascene": "구리 다마신 단면. 홈 식각→배리어·시드→구리 도금→CMP. 구리 배선, 다마신, 배리어 메탈 설명에 사용",
    "finfet-gaa": "게이트가 채널을 감싸는 방식. 평면(1면)→FinFET(3면)→GAA 나노시트(4면). FinFET, GAA, 단채널 효과 설명에 사용",
    "hbm-tsv": "HBM 스택과 2.5D 패키지 단면. DRAM 적층, TSV, 마이크로 범프, 인터포저, 데이터 경로. HBM, TSV, 인터포저 설명에 사용",
    "czochralski": "초크랄스키 단결정 성장. 시드 접촉→넥→크라운→바디. 초크랄스키 공정, 실리콘 잉곳 설명에 사용",
}

# (그림 id, 이론 제목에 맞는 정규식, 캡션)
RULES = [
    ("dram-cell", re.compile(r"^DRAM\b|메모리 반도체 개요"), "DRAM 셀에서 워드라인과 비트라인 전압이 바뀌며 값을 쓰고 읽는 과정"),
    ("mosfet", re.compile(r"MOSFET|문턱 전압|채널 길이 변조|트랜지스터 소자 개요"), "NMOS의 차단·선형·포화 동작과 채널 길이 변조"),
    ("pn-junction", re.compile(r"PN 접합"), "바이어스에 따라 달라지는 공핍층과 전류"),
    ("band-doping", re.compile(r"에너지 밴드|페르미 준위|캐리어 농도|반도체 물리 개요"), "물질별 밴드 구조와 도핑에 따른 페르미 준위의 위치"),
    ("photo-process", re.compile(r"노광|포토레지스트|포토 공정 개요"), "감광막 도포부터 제거까지 패턴이 웨이퍼 막에 옮겨지는 과정"),
    ("etch-profile", re.compile(r"식각|Bowing"), "식각 방식에 따라 달라지는 단면 모양"),
    ("step-coverage", re.compile(r"단차 피복성|CVD|ALD|PVD|박막 증착 공정 개요"), "증착 방식별로 홈 안쪽에 쌓이는 막의 두께 비교"),
    ("damascene", re.compile(r"다마신|금속 배선 공정 개요"), "구리 다마신 공정의 단계별 단면"),
    ("finfet-gaa", re.compile(r"FinFET|GAA|단채널|차세대 소자 기술 개요"), "게이트가 채널을 감싸는 면의 수 비교"),
    ("hbm-tsv", re.compile(r"HBM|TSV|인터포저|어드밴스드 패키징"), "HBM 스택과 프로세서를 인터포저 위에서 연결한 단면"),
    ("czochralski", re.compile(r"초크랄스키|실리콘 잉곳|웨이퍼 제조 공정 개요"), "단결정 잉곳이 자라는 단계"),
]

# 그림 줄을 넣을 소제목 후보(앞쪽일수록 우선). 해당 소제목 파트의 끝(팁 박스 바로 앞)에 넣는다.
WHERE = [r"원리|동작|작동", r"메커니즘|구조|세부|상세", r"정의|개념"]


def insert_diagram(content, did, caption):
    """content 에 {{diagram:did|caption}} 한 줄을 넣는다. (새 내용, 넣었는지) 를 돌려준다. 이미 있으면 그대로."""
    if "{{diagram:%s" % did in content:
        return content, False
    token = "{{diagram:%s|%s}}" % (did, caption)
    lines = content.split("\n")
    heads = [i for i, ln in enumerate(lines) if re.match(r"^###\s*\[", ln)]
    if not heads:
        return content, False
    start = None
    for pat in WHERE:
        start = next((i for i in heads if re.match(r"^###\s*\[[^\]]*(?:%s)" % pat, lines[i])), None)
        if start is not None:
            break
    if start is None:
        start = heads[0]
    end = next((i for i in heads if i > start), len(lines))
    tip = next((i for i in range(start + 1, end) if lines[i].lstrip().startswith(">")), None)
    at = tip if tip is not None else end
    while at > start + 1 and lines[at - 1].strip() == "":
        at -= 1
    lines[at:at] = ["", token, ""]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)), True


def ensure_diagrams(title, content, limit=2):
    """제목이 규칙에 맞는 그림을 content 에 넣는다. (새 내용, 넣은 그림 id 목록)"""
    added = []
    for did, pat, cap in RULES:
        if len(added) >= limit:
            break
        if pat.search(str(title)):
            content, ok = insert_diagram(content, did, cap)
            if ok:
                added.append(did)
    return content, added
