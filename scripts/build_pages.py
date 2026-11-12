"""이론마다 고유 주소를 가진 정적 HTML 페이지를 만든다. (검색 노출·링크 공유용, AI 호출 없음)

만드는 것
  theory/<id>/index.html   이론 한 편 = 한 페이지 (글이 HTML 로 미리 들어 있어 검색엔진이 읽을 수 있음)
  theory/index.html        이론 전체 목록 (검색 로봇이 모든 이론 링크를 따라가는 입구)
  sitemap.xml, robots.txt  사이트 주소를 알 수 있을 때만 (SITE_URL, CNAME, 또는 GitHub Actions 의 저장소 이름으로 계산)
  theory/.manifest.json    내용이 바뀐 이론만 sitemap 의 수정일이 바뀌게 하는 기록

사용법 (저장소 루트에서):  pip install markdown  →  python scripts/build_pages.py
  SITE_URL=https://example.com/semicbt python scripts/build_pages.py   (주소를 직접 지정할 때)
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

try:
    import markdown
except ImportError:
    sys.exit("markdown 패키지가 필요합니다:  pip install markdown")

SITE_NAME = "반도체 새김"
CAT_ORDER = ["반도체 기초 이론", "반도체 소자", "반도체 8대 공정", "차세대 첨단 기술", "기타"]
OUT_DIR = "theory"
MANIFEST = os.path.join(OUT_DIR, ".manifest.json")
esc = html.escape


# ---------------------------------------------------------------- 사이트 주소
def site_url():
    u = (os.environ.get("SITE_URL") or "").strip().rstrip("/")
    if u:
        return u
    if os.path.exists("CNAME"):
        c = open("CNAME", encoding="utf-8").read().strip()
        if c:
            return "https://" + c.splitlines()[0].strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io" if name.lower() == f"{owner}.github.io".lower() else f"https://{owner}.github.io/{name}"
    return ""


# ---------------------------------------------------------------- 마크다운 → HTML (index.html 의 렌더링과 같은 규칙)
BADGES = [(r"정의|개념|정체", "📘"), (r"배경|필요|왜", "🌱"), (r"원리|동작|작동", "⚙️"), (r"메커니즘|세부|상세|구조", "🔬"), (r"분류|종류|유형", "🗂️"),
          (r"변수|영향|요인", "🎚️"), (r"장단점|한계", "⚖️"), (r"실무|이슈|응용|활용", "🛠️"), (r"암기|체크|정리|요약", "🧠")]


def badge_emoji(t):
    for pat, e in BADGES:
        if re.search(pat, t):
            return e
    return "✏️"


def inline_md(text):
    out = markdown.markdown(text.strip(), extensions=["sane_lists"])
    return re.sub(r"^<p>|</p>$", "", out.strip())


def render_markdown(src):
    stash = []

    def hold(m):
        stash.append(m.group(0))
        return f"@@MATH{len(stash) - 1}@@"

    t = re.sub(r"\$\$[\s\S]+?\$\$", hold, src)
    t = re.sub(r"\$[^$\n]+?\$", hold, t)
    t = re.sub(r"\*\*([^*\n]+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r">\s*💡\s*(.*?)(?=\n\n|\n###|$)", lambda m: f'\n\n<div class="custom-highlight-box">{inline_md(m.group(1))}</div>\n\n', t, flags=re.S)
    t = re.sub(r"###\s*\[(.*?)\]\s*(.*)", lambda m: f'\n\n<div class="custom-badge-heading"><span class="custom-badge">{badge_emoji(m.group(1))} {esc(m.group(1))}</span>{m.group(2)}</div>\n\n', t)
    out = markdown.markdown(t, extensions=["tables", "sane_lists"])
    out = out.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    return re.sub(r"@@MATH(\d+)@@", lambda m: esc(stash[int(m.group(1))], quote=False), out)


def plain_description(content, limit=118):
    keep = []
    for ln in content.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", ">", "|", "-", "*", "$", "!")) or re.match(r"^\d+\.", s):
            continue
        keep.append(s)
        if sum(len(x) for x in keep) > limit * 2:
            break
    text = re.sub(r"\*\*|`|\$[^$]*\$|\[[^\]]*\]\([^)]*\)", "", " ".join(keep))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    m = max(cut.rfind(". "), cut.rfind("다. "))
    return (cut[:m + 1] if m > 50 else cut.rstrip() + "…")


# ---------------------------------------------------------------- 공통 HTML 조각
CSS = """
:root{color-scheme:light;--bg:#f8fafc;--card:#fff;--text:#334155;--muted:#64748b;--line:#e2e8f0;--heading:#0f172a;--accent:#4f46e5;--accent-soft:#eef2ff;
--hl-bg:#fffbeb;--hl-border:#fde68a;--hl-accent:#f59e0b;--hl-text:#4b3a0a;--badge-bg:#e0e7ff;--badge-fg:#4338ca;--tbl-head-bg:#eef2ff;--tbl-head-fg:#4338ca}
html.dark{color-scheme:dark;--bg:#0a1020;--card:#0f1729;--text:#cbd5e1;--muted:#94a3b8;--line:#22314d;--heading:#f8fafc;--accent:#67e8f9;--accent-soft:#112844;
--hl-bg:#2a2410;--hl-border:#5a4a1a;--hl-accent:#fbbf24;--hl-text:#fde9b0;--badge-bg:#14304f;--badge-fg:#67e8f9;--tbl-head-bg:#112844;--tbl-head-fg:#67e8f9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:'IBM Plex Sans KR',system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}.wrap{max-width:820px;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--line);background:var(--card)}header.top .wrap{display:flex;align-items:center;justify-content:space-between;height:60px}
.logo{font-weight:800;font-size:1.1rem;color:var(--heading);text-decoration:none}.logo b{color:var(--accent)}
.top-r{display:flex;gap:8px;align-items:center}.pill{display:inline-flex;align-items:center;height:38px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--heading);font-size:.875rem;font-weight:600;text-decoration:none;cursor:pointer;font-family:inherit}
.crumb{font-size:.8rem;color:var(--muted);margin:22px 0 10px}.crumb a{color:var(--muted);text-decoration:none}.crumb a:hover{text-decoration:underline}
article.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px 24px;margin-bottom:20px}
.eyebrow{font-size:.75rem;letter-spacing:.08em;font-weight:700;color:var(--accent);margin:0 0 8px}h1{font-size:1.9rem;line-height:1.3;letter-spacing:-.03em;color:var(--heading);margin:0 0 14px;word-break:keep-all}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid var(--line)}.tags span{background:var(--accent-soft);color:var(--accent);font-size:.7rem;font-weight:700;padding:4px 10px;border-radius:999px}
.theory-body{font-size:1.05rem;line-height:1.9;word-break:keep-all}.theory-body p{margin:.9rem 0}.theory-body strong{font-weight:700;color:var(--heading);background:linear-gradient(transparent 62%,rgba(250,204,21,.38) 0)}
html.dark .theory-body strong{background:linear-gradient(transparent 62%,rgba(103,232,249,.22) 0)}.theory-body ul,.theory-body ol{margin:.8rem 0;padding-left:1.4rem}.theory-body li{margin:.45rem 0}
.theory-body h1,.theory-body h2,.theory-body h3,.theory-body h4{color:var(--heading)}.theory-body code{background:var(--accent-soft);padding:1px 6px;border-radius:6px;font-size:.9em}
.custom-highlight-box{display:flex;gap:12px;background:var(--hl-bg);border:1px solid var(--hl-border);border-left:5px solid var(--hl-accent);border-radius:16px;padding:1.1rem 1.3rem;margin:1.6rem 0;color:var(--hl-text);font-size:.98rem;line-height:1.75}
.custom-highlight-box::before{content:'💡';font-size:1.3rem;line-height:1;flex:none}
.custom-badge-heading{display:flex;align-items:center;gap:10px;margin:3rem 0 1rem;font-size:1.3rem;font-weight:800;letter-spacing:-.03em;color:var(--heading);flex-wrap:wrap}
.custom-badge{background:var(--badge-bg);color:var(--badge-fg);font-size:.78rem;padding:5px 12px;border-radius:999px;white-space:nowrap}
.table-wrap{overflow-x:auto;margin:1.2rem 0;border:1px solid var(--line);border-radius:14px}.theory-body table{border-collapse:collapse;width:100%;font-size:.95rem}
.theory-body th{background:var(--tbl-head-bg);color:var(--tbl-head-fg);text-align:left;padding:.65rem .9rem}.theory-body td{padding:.6rem .9rem;border-top:1px solid var(--line)}
.katex-display{overflow-x:auto;overflow-y:hidden;padding:.35rem 0;margin:1rem 0!important}.katex-display>.katex{font-size:1.4em}
.cta{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px 24px;margin-bottom:20px}.cta h2{font-size:1rem;margin:0 0 4px;color:var(--heading)}.cta p{margin:0 0 14px;font-size:.88rem;color:var(--muted)}
.btns{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.btn{display:flex;align-items:center;justify-content:center;gap:8px;padding:14px 16px;border-radius:12px;font-weight:700;font-size:.95rem;text-decoration:none;border:2px solid var(--accent);color:var(--accent);background:transparent}
.btn.primary{background:var(--accent);color:#fff}html.dark .btn.primary{color:#04121f}
.rel{margin-bottom:28px}.rel h2{font-size:1rem;color:var(--heading);margin:0 0 10px}.rel ul{list-style:none;margin:0;padding:0;display:grid;gap:8px}.rel a{display:block;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:12px;text-decoration:none;color:var(--heading);font-weight:600;font-size:.92rem}
.rel a small{display:block;color:var(--muted);font-weight:400;margin-top:2px}
footer.bot{border-top:1px solid var(--line);padding:22px 0 40px;font-size:.8rem;color:var(--muted)}
.hub h2{font-size:1.15rem;color:var(--heading);margin:30px 0 4px}.hub h3{font-size:.9rem;color:var(--accent);margin:16px 0 8px}
@media(max-width:560px){h1{font-size:1.55rem}article.card{padding:22px 16px}.top-r .pill:first-child{display:none}}
"""
THEME_JS = """<script>try{var d=localStorage.theme==='dark'||(!('theme' in localStorage)&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d)}catch(e){}</script>"""
FONT = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700;800&display=swap">'
KATEX = ('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">'
         '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>'
         '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js" onload="renderMathInElement(document.querySelector(\'.theory-body\'),{delimiters:[{left:\'$$\',right:\'$$\',display:true},{left:\'$\',right:\'$\',display:false}],throwOnError:false})"></script>')
TOGGLE_JS = """<script>function tt(){var h=document.documentElement,d=!h.classList.contains('dark');h.classList.toggle('dark',d);try{localStorage.theme=d?'dark':'light'}catch(e){}}</script>"""
FAVICON = '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 32 32\'%3E%3Ccircle cx=\'16\' cy=\'16\' r=\'14\' fill=\'%230f1729\' stroke=\'%2367e8f9\' stroke-width=\'2\'/%3E%3Cpath d=\'M9 18h5v-5h4v8h5\' fill=\'none\' stroke=\'%23a78bfa\' stroke-width=\'2\' stroke-linecap=\'round\'/%3E%3C/svg%3E">'


def head(title, desc, root, canonical, extra=""):
    can = f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ""
    og = (f'<meta property="og:type" content="article"><meta property="og:site_name" content="{SITE_NAME}"><meta property="og:locale" content="ko_KR">'
          f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">'
          + (f'<meta property="og:url" content="{esc(canonical)}">' if canonical else "") + '<meta name="twitter:card" content="summary">')
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{can}{og}{FAVICON}{THEME_JS}{FONT}<style>{CSS}</style>{extra}</head><body>')


def top_bar(root):
    return (f'<header class="top"><div class="wrap"><a class="logo" href="{root}index.html">반도체 <b>새김</b></a>'
            f'<div class="top-r"><a class="pill" href="{root}theory/">이론 목록</a><a class="pill" href="{root}index.html">학습하러 가기</a>'
            f'<button class="pill" onclick="tt()" aria-label="화면 색 전환">🌓</button></div></div></header>{TOGGLE_JS}')


def bottom(root):
    return (f'<footer class="bot"><div class="wrap">AI가 생성한 이론과 문제는 검수 후 게시돼요. 오류를 발견하면 <a href="{root}index.html">앱</a>의 제보 기능으로 알려 주세요.<br>'
            f'{SITE_NAME} · 하루 5분, 오늘의 학습을 웨이퍼에 새겨보세요</div></footer></body></html>')


def slugify(i, used):
    s = re.sub(r"[^a-z0-9-]+", "-", str(i).lower()).strip("-") or "t"
    base, n = s, 2
    while s in used:
        s = f"{base}-{n}"; n += 1
    used.add(s)
    return s


# ---------------------------------------------------------------- 본 작업
def main():
    try:
        theories = json.load(open("data/theories.json", encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.exit(f"data/theories.json 을 읽을 수 없습니다: {e}")
    theories = [t for t in theories if isinstance(t, dict) and t.get("title") and "채워질 예정" not in str(t.get("content", ""))]
    base = site_url()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        manifest = json.load(open(MANIFEST, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}

    used, items = set(), []
    for t in theories:
        cat, sub = t.get("category") or "기타", t.get("subject") or "일반"
        items.append(dict(t=t, id=t.get("id") or t["title"], slug=slugify(t.get("id") or t["title"], used), cat=cat, sub=sub, desc=plain_description(str(t.get("content", "")))))

    os.makedirs(OUT_DIR, exist_ok=True)
    new_manifest = {}
    for it in items:
        t = it["t"]; slug = it["slug"]
        h = hashlib.sha1(json.dumps([t.get("title"), t.get("category"), t.get("subject"), t.get("content"), t.get("tags")], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
        old = manifest.get(slug, {})
        it["lastmod"] = old["lastmod"] if old.get("hash") == h else today
        new_manifest[slug] = {"hash": h, "lastmod": it["lastmod"]}
        url = f"{base}/{OUT_DIR}/{slug}/" if base else ""
        root = "../../"
        minutes = max(1, round(len(str(t.get("content", ""))) / 650))
        body = render_markdown(str(t.get("content", "")))
        tags = "".join(f"<span>#{esc(str(x))}</span>" for x in (t.get("tags") or []))
        rel = [r for r in items if r is not it and r["sub"] == it["sub"]][:4] or [r for r in items if r is not it and r["cat"] == it["cat"]][:4]
        rel_html = ("<section class=\"rel\"><h2>같이 보면 좋은 이론</h2><ul>" + "".join(f'<li><a href="../{r["slug"]}/">{esc(r["t"]["title"])}<small>{esc(r["cat"])} · {esc(r["sub"])}</small></a></li>' for r in rel) + "</ul></section>") if rel else ""
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": t["title"], "description": it["desc"], "inLanguage": "ko", "articleSection": it["cat"],
               "dateModified": it["lastmod"], "publisher": {"@type": "Organization", "name": SITE_NAME}},
              {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                  {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": base + "/" if base else root},
                  {"@type": "ListItem", "position": 2, "name": "이론 백과사전", "item": f"{base}/{OUT_DIR}/" if base else "../"},
                  {"@type": "ListItem", "position": 3, "name": t["title"]}]}]
        if url:
            ld[0]["mainEntityOfPage"] = url
        ldjs = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)
        q = esc(str(it["id"]), quote=True)
        page = (head(f'{t["title"]} 정리 — {it["sub"] if it["sub"] != "일반" else it["cat"]} | {SITE_NAME}', it["desc"], root, url, KATEX + ldjs) + top_bar(root)
                + f'<main class="wrap"><nav class="crumb" aria-label="경로"><a href="{root}index.html">{SITE_NAME}</a> › <a href="../">이론 백과사전</a> › {esc(it["cat"])}</nav>'
                + f'<article class="card"><p class="eyebrow">{esc(it["cat"])} / {esc(it["sub"])} · 약 {minutes}분 읽기</p><h1>{esc(t["title"])}</h1><div class="tags">{tags}</div><div class="theory-body">{body}</div></article>'
                + f'<section class="cta"><h2>읽은 내용을 바로 확인해 보세요</h2><p>문제와 면접 연습은 가입 없이 무료예요. 푼 기록은 이 브라우저에 저장돼요.</p><div class="btns">'
                + f'<a class="btn primary" href="{root}index.html?theory={q}&go=quiz">🧩 실전 문제 풀기</a><a class="btn" href="{root}index.html?theory={q}&go=interview">🗣️ 면접 연습</a><a class="btn" href="{root}index.html?theory={q}">📖 앱에서 이어 읽기</a></div></section>'
                + rel_html + '</main>' + bottom(root))
        d = os.path.join(OUT_DIR, slug); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)

    # 목록 페이지
    secs = []
    cats = sorted({i["cat"] for i in items}, key=lambda c: (CAT_ORDER.index(c) if c in CAT_ORDER else 99, c))
    for c in cats:
        secs.append(f"<h2>{esc(c)}</h2>")
        for s_ in dict.fromkeys(i["sub"] for i in items if i["cat"] == c):
            secs.append(f"<h3>{esc(s_)}</h3><div class=\"rel\"><ul>" + "".join(f'<li><a href="{i["slug"]}/">{esc(i["t"]["title"])}<small>{esc(i["desc"][:70])}</small></a></li>' for i in items if i["cat"] == c and i["sub"] == s_) + "</ul></div>")
    hub_url = f"{base}/{OUT_DIR}/" if base else ""
    hub_ld = json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": f"이론 백과사전 | {SITE_NAME}", "inLanguage": "ko",
                         "hasPart": [{"@type": "Article", "headline": i["t"]["title"], **({"url": f"{base}/{OUT_DIR}/{i['slug']}/"} if base else {})} for i in items]}, ensure_ascii=False)
    hub = (head(f"반도체 이론 백과사전 — 기초·소자·8대 공정·첨단 기술 | {SITE_NAME}", f"반도체 기초 이론부터 소자, 8대 공정, 차세대 첨단 기술까지 {len(items)}편. 하루 5분, 쉬운 말로 정리한 반도체 학습 노트.", "../", hub_url, f'<script type="application/ld+json">{hub_ld}</script>')
           + top_bar("../") + f'<main class="wrap hub"><nav class="crumb"><a href="../index.html">{SITE_NAME}</a> › 이론 백과사전</nav><h1>반도체 이론 백과사전</h1>'
           + f'<p>기초 이론, 소자, 8대 공정, 차세대 첨단 기술을 쉬운 말로 정리했어요. 총 {len(items)}편이에요.</p>' + "".join(secs) + "</main>" + bottom("../"))
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(hub)

    # 사라진 이론의 옛 페이지 정리 (이전에 이 스크립트가 만든 것만)
    for slug in set(manifest) - set(new_manifest):
        shutil.rmtree(os.path.join(OUT_DIR, slug), ignore_errors=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=1, sort_keys=True)

    # sitemap / robots
    if base:
        urls = [(f"{base}/", max((i["lastmod"] for i in items), default=today)), (f"{base}/{OUT_DIR}/", max((i["lastmod"] for i in items), default=today))] + [(f"{base}/{OUT_DIR}/{i['slug']}/", i["lastmod"]) for i in items]
        with open("sitemap.xml", "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{m}</lastmod></url>\n" for u, m in urls) + "</urlset>\n")
        with open("robots.txt", "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")
        print(f"✅ 이론 {len(items)}편 + 목록 페이지 + sitemap.xml 생성 (사이트 주소: {base})")
    else:
        print(f"✅ 이론 {len(items)}편 + 목록 페이지 생성. ⚠️ 사이트 주소를 알 수 없어 sitemap.xml/robots.txt 는 만들지 않았습니다. (SITE_URL 환경변수로 지정)")


if __name__ == "__main__":
    main()
