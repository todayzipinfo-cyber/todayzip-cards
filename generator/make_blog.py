"""todayzip 네이버 블로그 원고 생성기 (살림템 구매 가이드).

1) 사진 후보:  python generator/make_blog.py candidates blog/<날짜>/blog.json
2) 원고 만들기: python generator/make_blog.py build blog/<날짜>/blog.json [--skip-images]
   -> blog/<날짜>/draft/index.html (복사 버튼이 있는 원고), 01_thumbnail.jpg, 02.jpg ... (올릴 사진)
"""
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from make_cards import wrap  # noqa: E402
from make_reel import FONT_BOLD, font, shadow_text  # noqa: E402
from stock_image import candidates_for, download  # noqa: E402

THUMB = 1080
ACCENT = "#FF9F43"
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
ROOT = Path(__file__).parent.parent


def affiliate_enabled():
    """블로그 제휴 링크 스위치 (BLOG.md). 인스타용 STYLE.md 스위치와 별개."""
    return "**AFFILIATE_BLOG_ENABLED: true**" in (ROOT / "BLOG.md").read_text(encoding="utf-8")


def coupang_search(q):
    return "https://www.coupang.com/np/search?q=" + urllib.parse.quote(q)


def shots(data):
    out = [("thumbnail", data["thumbnail"])]
    out += [(f"sec{i}", s) for i, s in enumerate(data["sections"], 1) if s.get("image_queries")]
    return out


def square(img, size):
    s = min(img.size)
    x, y = (img.width - s) // 2, (img.height - s) // 2
    return img.crop((x, y, x + s, y + s)).resize((size, size), Image.LANCZOS).convert("RGB")


def thumbnail(src, t, out):
    """정사각 썸네일: 사진 + 아래쪽 어둡게 + kicker + 큰 제목 + 브랜드."""
    img = square(Image.open(src), THUMB).convert("RGBA")
    shade = Image.new("L", (1, THUMB))
    for y in range(THUMB):
        shade.putpixel((0, y), int(230 * max(0, (y - THUMB * 0.3) / (THUMB * 0.7)) ** 1.1))
    dark = Image.new("RGBA", (THUMB, THUMB), (0, 0, 0, 255))
    dark.putalpha(shade.resize((THUMB, THUMB)))
    img.alpha_composite(dark)
    d = ImageDraw.Draw(img)
    tf = font(FONT_BOLD, 110)
    lines = wrap(d, t["title"], tf, THUMB - 140)
    y = THUMB - 110 - len(lines) * 132
    if t.get("kicker"):
        kf = font(FONT_BOLD, 44)
        tw = d.textlength(t["kicker"], font=kf)
        d.rounded_rectangle((70, y - 100, 70 + tw + 56, y - 26), radius=37, fill=ACCENT)
        d.text((98, y - 92), t["kicker"], font=kf, fill="#111111")
    for line in lines:
        shadow_text(img, (70, y), line, tf, "white", 10)
        y += 132
    shadow_text(img, (70, 60), "TODAYZIP 살림 가이드", font(FONT_BOLD, 38), "white", 4)
    img.convert("RGB").save(out, quality=92)


def photo(src, out, width=1200):
    img = Image.open(src).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(out, quality=88)


def esc(s):
    return html.escape(s).replace("\n", "<br>")


def body_html(data, photo_no):
    aff = affiliate_enabled()
    parts = []
    if aff and data.get("products"):
        parts.append(f'<p class="disc">{DISCLOSURE}</p>')
    parts.append(f'<p class="ph">[사진 {photo_no["thumbnail"]}: 썸네일]</p>')
    parts += [f"<p>{esc(p)}</p>" for p in data["intro"]]
    for i, s in enumerate(data["sections"], 1):
        parts.append(f"<h3>{esc(s['heading'])}</h3>")
        if f"sec{i}" in photo_no:
            parts.append(f'<p class="ph">[사진 {photo_no[f"sec{i}"]}]</p>')
        parts += [f"<p>{esc(p)}</p>" for p in s.get("paragraphs", [])]
        if s.get("list"):
            parts.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in s["list"]) + "</ul>")
        if s.get("table"):
            tb = s["table"]
            parts.append("<table><tr>" + "".join(f"<th>{esc(h)}</th>" for h in tb["head"]) + "</tr>"
                         + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in tb["rows"])
                         + "</table>")
    if data.get("products"):
        parts.append("<h3>이런 제품을 고르세요</h3><ul>")
        for i, p in enumerate(data["products"], 1):
            link = ""
            if aff and p.get("link"):  # 이미 만든 파트너스 링크
                link = f' <a href="{html.escape(p["link"])}">👉 쿠팡에서 보기</a>'
            elif aff:
                link = f' <span class="ph">[쿠팡 링크 {i}]</span>'
            parts.append(f"<li><b>{esc(p['name'])}</b>: {esc(p['point'])}{link}</li>")
        parts.append("</ul>")
    if data.get("caution"):
        parts.append("<h3>꼭 알아두세요</h3><ul>" + "".join(f"<li>{esc(c)}</li>" for c in data["caution"]) + "</ul>")
    if data.get("faq"):
        parts.append("<h3>자주 묻는 질문</h3>")
        for f in data["faq"]:
            parts.append(f"<p><b>Q. {esc(f['q'])}</b><br>A. {esc(f['a'])}</p>")
    parts += [f"<p>{esc(p)}</p>" for p in data["outro"]]
    parts.append("<p>인스타그램 @todayzip.info 에서 살림 꿀팁을 30초 영상으로도 볼 수 있어요.</p>")
    if aff and data.get("products"):
        parts.append(f'<p class="disc">{DISCLOSURE}</p>')
    return "\n".join(parts)


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>블로그 원고 · {date}</title>
<style>
:root{{--bg:#f6f6f4;--card:#fff;--ink:#1d1d1f;--sub:#6b6b6b;--line:#e5e5e5;--acc:#03c75a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--card:#1b1b1b;--ink:#eee;--sub:#aaa;--line:#333}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Malgun Gothic",sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:24px 16px 80px}}
.step{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}}
.step h2{{font-size:15px;margin:0 0 10px;color:var(--sub)}}
button{{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:9px 16px;font:inherit;font-weight:700;cursor:pointer}}
button.done{{background:#555}}
.title{{font-size:22px;font-weight:700;margin:8px 0}}
.meta{{font-size:13px;color:var(--sub)}}
.photos{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-top:10px}}
.photos figure{{margin:0;font-size:12px;color:var(--sub);text-align:center}}
.photos img{{width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px}}
#body{{line-height:1.8;font-size:16px}}
#body h3{{font-size:19px;margin:28px 0 8px;border-left:4px solid var(--acc);padding-left:10px}}
#body .ph{{color:#d33;font-weight:700}}
#body .disc{{font-size:13px;color:var(--sub)}}
#body table{{border-collapse:collapse;width:100%;font-size:14px}}
#body th,#body td{{border:1px solid var(--line);padding:6px 8px;text-align:left}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}}
.chip{{background:var(--bg);color:var(--ink);border:1px solid var(--line);font-weight:400;padding:6px 12px;border-radius:999px}}
.chip.done{{background:var(--acc);color:#fff}}
</style></head><body><div class="wrap">
<p class="meta">📝 {date} · 핵심 키워드 <b>{keyword}</b> · 본문 약 {chars:,}자</p>

<div class="step"><h2>1. 제목 복사</h2><div class="title" id="title">{title}</div>
<button onclick="copyText('title',this)">제목 복사</button></div>

<div class="step"><h2>2. 본문 복사 → 네이버 에디터에 붙여넣기</h2>
<p class="meta">빨간 <b>[사진 N]</b> 자리에 아래 3번의 사진을 올리고, 그 표시 줄은 지워주세요.</p>
<button onclick="copyHtml('body',this)">본문 복사</button></div>
{coupang}

<div class="step"><h2>3. 사진 ({n_photos}장, 이 폴더에 있어요)</h2>
<p class="meta">{folder}</p><div class="photos">{photos}</div></div>

<div class="step"><h2>4. 태그 넣기</h2>
<p class="meta">한 번에: <b>태그 전체 복사</b> 후 태그 칸에 붙여넣기 (쉼표로 나뉘어요). 잘 안 나뉘면 아래 태그를 하나씩 눌러 복사 → 붙여넣기 → Enter.</p>
<div class="tags" id="tags" style="display:none">{tags}</div>
<button onclick="copyText('tags',this)">태그 전체 복사</button>
<div class="chips">{chips}</div></div>

<div class="step"><h2>본문 미리보기</h2><div id="body">{body}</div></div>
</div>
<script>
function flash(b){{b.classList.add('done');if(!b.classList.contains('chip'))b.textContent='복사됨 ✓';}}
function copyTag(b){{navigator.clipboard.writeText(b.dataset.tag).then(()=>flash(b),()=>{{const t=document.createElement('textarea');t.value=b.dataset.tag;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();flash(b);}});}}
function copyText(id,b){{navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>flash(b),()=>copyHtml(id,b));}}
function copyHtml(id,b){{const r=document.createRange();r.selectNodeContents(document.getElementById(id));
 const s=getSelection();s.removeAllRanges();s.addRange(r);document.execCommand('copy');s.removeAllRanges();flash(b);}}
</script></body></html>"""


def build(path, skip_images=False):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    out = path.parent / "draft"
    out.mkdir(exist_ok=True)
    photo_no, cards, n = {}, [], 0
    for name, s in shots(data):
        raw = path.parent / f"img_{name}.jpg"
        if not (skip_images and raw.exists()):
            if not s.get("image_id"):
                sys.exit(f"{name}: image_id 가 없습니다 (candidates 로 고른 뒤 적어주세요)")
            download(s["image_id"], raw)
        n += 1
        fname = f"{n:02d}_{name}.jpg"
        if name == "thumbnail":
            thumbnail(raw, data["thumbnail"], out / fname)
        else:
            photo(raw, out / fname)
        photo_no[name] = n
        cards.append(f'<figure><img src="{fname}" alt=""><figcaption>사진 {n}</figcaption></figure>')
    body = body_html(data, photo_no)
    chars = len(re.sub(r"<[^>]+>|\[사진[^\]]*\]", "", body))
    coupang = ""
    if affiliate_enabled() and data.get("products") and not all(p.get("link") for p in data["products"]):
        rows = "".join(
            f'<li><b>[쿠팡 링크 {i}] {html.escape(p["name"])}</b> · '
            f'<a href="{coupang_search(p.get("search") or p["name"])}" target="_blank" rel="noopener">쿠팡에서 찾기 ↗</a></li>'
            for i, p in enumerate(data["products"], 1))
        coupang = ('<div class="step"><h2>2-1. 쿠팡 링크 만들기</h2>'
                   '<p class="meta">① 쿠팡에서 찾기로 알맞은 상품을 고르고 주소를 복사 → ② 쿠팡 파트너스 '
                   '<a href="https://partners.coupang.com" target="_blank" rel="noopener">간편 링크 만들기</a>에 붙여넣어 '
                   '링크 생성 → ③ 본문의 빨간 [쿠팡 링크 N] 자리를 그 링크로 바꾸기</p>'
                   f'<ul>{rows}</ul></div>')
    page = PAGE.format(date=data["date"], coupang=coupang, keyword=html.escape(data["keyword"]), title=html.escape(data["title"]),
                       chars=chars, body=body, photos="".join(cards), n_photos=n, folder=html.escape(str(out)),
                       tags=html.escape(",".join(data["tags"])),
                       chips="".join(f'<button class="chip" data-tag="{html.escape(t)}" onclick="copyTag(this)">'
                                     f'{html.escape(t)}</button>' for t in data["tags"]))
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"draft -> {out / 'index.html'} ({chars}자, 사진 {n}장)")


if __name__ == "__main__":
    cmd, p = sys.argv[1], Path(sys.argv[2])
    if cmd == "candidates":
        candidates_for(shots(json.loads(p.read_text(encoding="utf-8"))), p.parent)
    else:
        build(p, "--skip-images" in sys.argv)
