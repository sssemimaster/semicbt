"""이론마다 고유 주소를 가진 페이지를 만든다. (검색 노출·링크 공유용, AI 호출 없음)

각 페이지는 별도 디자인이 아니라 '이 사이트(index.html) 그대로'다. index.html 에 그 이론의 글을 미리 넣어 두기만 하므로
같은 헤더·메뉴·다크모드·문제 풀이 버튼이 그대로 동작하고, 검색엔진은 미리 들어 있는 글을 읽는다.
브라우저에서는 앱이 켜지면서 같은 이론 화면을 이어받는다.

만드는 것
  theory/<id>/index.html   이론 한 편 = 한 페이지
  theory/index.html        이론 전체 목록 (검색 로봇이 모든 이론 링크를 따라가는 입구)
  data/theory_pages.json   이론 id -> 주소 조각 (앱이 이론을 읽는 동안 주소창을 그 이론의 주소로 바꿈)
  sitemap.xml, robots.txt  사이트 주소를 알 수 있을 때만 (SITE_URL, CNAME, 또는 GitHub Actions 의 저장소 이름으로 계산)
  theory/.manifest.json    내용이 바뀐 이론만 sitemap 의 수정일이 바뀌게 하는 기록

index.html 의 구조가 바뀌어 미리 넣을 자리를 못 찾으면, 엉뚱한 페이지를 만들지 않고 오류로 멈춘다.

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


def slugify(i, used):
    s = re.sub(r"[^a-z0-9-]+", "-", str(i).lower()).strip("-") or "t"
    base, n = s, 2
    while s in used:
        s = f"{base}-{n}"; n += 1
    used.add(s)
    return s


# ---------------------------------------------------------------- 앱(index.html)에 글 미리 넣기
def must_replace(text, old, new, what):
    if text.count(old) != 1:
        sys.exit(f"index.html 에서 '{what}' 자리를 찾지 못했습니다. (index.html 구조가 바뀌었다면 scripts/build_pages.py 도 맞춰 고쳐야 합니다)")
    return text.replace(old, new, 1)


def make_shell(tpl, *, title, desc, canonical, ld, root, depth, boot_js, container_html, og_type="article"):
    h = tpl
    if not re.search(r"<title>.*?</title>", h, re.S) or not re.search(r'<meta name="description" content="[^"]*">', h):
        sys.exit("index.html 의 <title> 또는 description 자리를 찾지 못했습니다.")
    h = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(title)}</title>", h, count=1, flags=re.S)
    og = (f'<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{SITE_NAME}"><meta property="og:locale" content="ko_KR">'
          f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta name="twitter:card" content="summary">'
          + (f'<meta property="og:url" content="{esc(canonical)}">' if canonical else ""))
    can = f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ""
    h = re.sub(r'<meta name="description" content="[^"]*">', lambda m: f'<meta name="description" content="{esc(desc)}">{can}{og}', h, count=1)
    h = must_replace(h, "</head>", "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld) + "</head>", "</head>")
    h = must_replace(h, '<script src="https://cdn.tailwindcss.com', f"<script>if(!/(\\/|\\.html)$/.test(location.pathname)){{location.replace(location.pathname+'/'+location.search+location.hash)}}window.DEPTH={depth};{boot_js}</script>\n  <script src=\"https://cdn.tailwindcss.com", "Tailwind 스크립트")
    # 처음부터 홈이 아니라 이론 화면이 보이게 (검색엔진은 숨겨진 글을 낮게 본다)
    h = must_replace(h, '<div id="view-lobby" class="w-full flex flex-col gap-6 lg:gap-7">', '<div id="view-lobby" class="hidden w-full flex flex-col gap-6 lg:gap-7">', "홈 화면(view-lobby)")
    h = must_replace(h, '<div id="view-learning" class="hidden w-full flex flex-col">', '<div id="view-learning" class="w-full flex flex-col">', "이론 화면(view-learning)")
    h = must_replace(h, '<div id="learningContainer" class="grid grid-cols-1 gap-4"></div>', f'<div id="learningContainer" class="flex flex-col space-y-4">{container_html}</div>', "이론 영역(learningContainer)")
    h = must_replace(h, 'id="theoryHubLink" href="theory/"', f'id="theoryHubLink" href="{root}theory/"', "푸터의 이론 목록 링크")
    return h


LINK_CARD = 'class="block rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#0f1729] px-4 py-3 hover:border-indigo-300 dark:hover:border-cyan-400/40 transition"'


def detail_html(it, body, minutes, rel):
    t = it["t"]
    tags = "".join(f'<span class="bg-indigo-50 dark:bg-white/5 text-indigo-700 dark:text-cyan-300 text-[11px] px-2.5 py-1 rounded-full font-bold">#{esc(str(x))}</span>' for x in (t.get("tags") or []))
    rel_html = ""
    if rel:
        rel_html = ('<nav aria-label="같이 보면 좋은 이론" class="mt-2"><p class="text-xs font-bold text-slate-400 dark:text-slate-500 mb-3">같이 보면 좋은 이론</p><ul class="grid gap-2 sm:grid-cols-2">'
                    + "".join(f'<li><a href="../{r["slug"]}/" {LINK_CARD}><span class="font-bold text-sm text-slate-900 dark:text-white">{esc(r["t"]["title"])}</span><span class="block text-xs text-slate-500 dark:text-slate-400 mt-0.5">{esc(r["cat"])} · {esc(r["sub"])}</span></a></li>' for r in rel)
                    + "</ul></nav>")
    return ('<div class="bg-white dark:bg-[#0f1729] rounded-2xl shadow-sm border border-slate-200 dark:border-white/10 overflow-hidden"><div class="p-6 md:p-8">'
            f'<p class="eyebrow mb-2">{esc(it["cat"])} <span class="opacity-50">/</span> {esc(it["sub"])} <span class="opacity-50">·</span> 약 {minutes}분 읽기</p>'
            f'<h1 class="page-title text-slate-900 dark:text-white mb-3">{esc(t["title"])}</h1>'
            f'<div class="flex flex-wrap gap-1.5 mb-6 pb-6 border-b border-slate-100 dark:border-white/10">{tags}</div>'
            f'<div class="custom-table-container theory-body prose prose-slate dark:prose-invert max-w-none">{body}</div></div></div>{rel_html}')


def hub_html(items, cats):
    out = ['<div class="space-y-8">']
    for c in cats:
        out.append(f'<section><h2 class="text-lg font-bold text-slate-900 dark:text-white mb-3">{esc(c)}</h2><ul class="grid gap-2 sm:grid-cols-2">')
        for i in items:
            if i["cat"] == c:
                out.append(f'<li><a href="{i["slug"]}/" {LINK_CARD}><span class="font-bold text-sm text-slate-900 dark:text-white">{esc(i["t"]["title"])}</span><span class="block text-xs text-slate-500 dark:text-slate-400 mt-0.5">{esc(i["sub"])} · {esc(i["desc"][:60])}</span></a></li>')
        out.append("</ul></section>")
    out.append("</div>")
    return "".join(out)


# ---------------------------------------------------------------- 본 작업
def main():
    try:
        theories = json.load(open("data/theories.json", encoding="utf-8"))
        tpl = open("index.html", encoding="utf-8").read()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.exit(f"data/theories.json 또는 index.html 을 읽을 수 없습니다: {e}")
    theories = [t for t in theories if isinstance(t, dict) and t.get("title") and "채워질 예정" not in str(t.get("content", ""))]
    base = site_url()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        manifest = json.load(open(MANIFEST, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}

    used, items = set(), []
    for t in theories:
        tid = t.get("id") or t["title"]
        items.append(dict(t=t, id=tid, slug=slugify(tid, used), cat=t.get("category") or "기타", sub=t.get("subject") or "일반", desc=plain_description(str(t.get("content", "")))))

    os.makedirs(OUT_DIR, exist_ok=True)
    new_manifest = {}
    for it in items:
        t = it["t"]; slug = it["slug"]
        h = hashlib.sha1(json.dumps([t.get("title"), t.get("category"), t.get("subject"), t.get("content"), t.get("tags")], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
        old = manifest.get(slug, {})
        it["lastmod"] = old["lastmod"] if old.get("hash") == h else today
        new_manifest[slug] = {"hash": h, "lastmod": it["lastmod"]}
        url = f"{base}/{OUT_DIR}/{slug}/" if base else ""
        minutes = max(1, round(len(str(t.get("content", ""))) / 650))
        rel = [r for r in items if r is not it and r["sub"] == it["sub"]][:4] or [r for r in items if r is not it and r["cat"] == it["cat"]][:4]
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": t["title"], "description": it["desc"], "inLanguage": "ko", "articleSection": it["cat"],
               "dateModified": it["lastmod"], "publisher": {"@type": "Organization", "name": SITE_NAME}},
              {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                  {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": base + "/" if base else "../../"},
                  {"@type": "ListItem", "position": 2, "name": "이론 백과사전", "item": f"{base}/{OUT_DIR}/" if base else "../"},
                  {"@type": "ListItem", "position": 3, "name": t["title"]}]}]
        if url:
            ld[0]["mainEntityOfPage"] = url
        page = make_shell(tpl, title=f'{t["title"]} 정리 — {it["sub"] if it["sub"] != "일반" else it["cat"]} | {SITE_NAME}', desc=it["desc"], canonical=url, ld=ld, root="../../", depth=2,
                          boot_js=f"window.BOOT_THEORY={json.dumps(str(it['id']), ensure_ascii=False)};",
                          container_html=detail_html(it, render_markdown(str(t.get("content", ""))), minutes, rel))
        d = os.path.join(OUT_DIR, slug); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)

    cats = sorted({i["cat"] for i in items}, key=lambda c: (CAT_ORDER.index(c) if c in CAT_ORDER else 99, c))
    hub_url = f"{base}/{OUT_DIR}/" if base else ""
    hub_ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": f"이론 백과사전 | {SITE_NAME}", "inLanguage": "ko",
               "hasPart": [{"@type": "Article", "headline": i["t"]["title"], **({"url": f"{base}/{OUT_DIR}/{i['slug']}/"} if base else {})} for i in items]}]
    hub = make_shell(tpl, title=f"반도체 이론 백과사전 — 기초·소자·8대 공정·첨단 기술 | {SITE_NAME}",
                     desc=f"반도체 기초 이론부터 소자, 8대 공정, 차세대 첨단 기술까지 {len(items)}편. 하루 5분, 쉬운 말로 정리한 반도체 학습 노트.",
                     canonical=hub_url, ld=hub_ld, root="../", depth=1, boot_js="window.BOOT_HUB=true;", container_html=hub_html(items, cats), og_type="website")
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(hub)

    # 사라진 이론의 옛 페이지 정리 (이전에 이 스크립트가 만든 것만)
    for slug in set(manifest) - set(new_manifest):
        shutil.rmtree(os.path.join(OUT_DIR, slug), ignore_errors=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
    with open("data/theory_pages.json", "w", encoding="utf-8") as f:
        json.dump({str(i["id"]): i["slug"] for i in items}, f, ensure_ascii=False, indent=1, sort_keys=True)

    if base:
        newest = max((i["lastmod"] for i in items), default=today)
        urls = [(f"{base}/", newest), (f"{base}/{OUT_DIR}/", newest)] + [(f"{base}/{OUT_DIR}/{i['slug']}/", i["lastmod"]) for i in items]
        with open("sitemap.xml", "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{m}</lastmod></url>\n" for u, m in urls) + "</urlset>\n")
        with open("robots.txt", "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")
        print(f"✅ 이론 {len(items)}편 + 목록 페이지 + sitemap.xml 생성 (사이트 주소: {base})")
    else:
        print(f"✅ 이론 {len(items)}편 + 목록 페이지 생성. ⚠️ 사이트 주소를 알 수 없어 sitemap.xml/robots.txt 는 만들지 않았습니다. (SITE_URL 환경변수로 지정)")


if __name__ == "__main__":
    main()
