"""todayzip 카드뉴스 생성기.

사용법: python generator/make_cards.py posts/2026-10-07/content.json
content.json 옆에 01.png, 02.png ... 를 만든다 (1080x1350, 인스타 4:5).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
PAD = 96
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
FONT_REG = "C:/Windows/Fonts/malgun.ttf"
BRAND = "@todayzip.info"

# 카테고리별 테마: (메인색, 진한색, 연한 배경색)
THEMES = {
    "life":    ("#2F80ED", "#1B4F99", "#EEF4FD"),
    "money":   ("#16A34A", "#0F6B32", "#ECF8F0"),
    "health":  ("#F2994A", "#A85A16", "#FEF4EB"),
    "trend":   ("#9B51E0", "#5E2A94", "#F5EEFC"),
    "weekend": ("#EB5757", "#9E2A2A", "#FDEFEF"),
    "mind":    ("#14B8A6", "#0B7368", "#E9F8F6"),
    "law":     ("#334155", "#0F172A", "#F1F5F9"),
}
INK = "#111827"
SUB = "#4B5563"


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    """공백 우선, 넘치면 글자 단위로 줄바꿈. 명시적 \\n 유지."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = word if not cur else cur + " " + word
            if draw.textlength(cand, font=fnt) <= max_w:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if draw.textlength(cur + ch, font=fnt) <= max_w:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
        lines.append(cur)
    return lines


def draw_lines(draw, xy, lines, fnt, fill, spacing):
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + spacing
    return y


def footer(draw, idx, total, color):
    f = font(FONT_BOLD, 30)
    draw.text((PAD, H - 90), BRAND, font=f, fill=color)
    page = f"{idx} / {total}"
    draw.text((W - PAD - draw.textlength(page, font=f), H - 90), page, font=f, fill=color)


def cover(data, theme, total):
    main, dark, _ = theme
    img = Image.new("RGB", (W, H), main)
    d = ImageDraw.Draw(img)
    # 장식 원
    d.ellipse((W - 420, -220, W + 220, 420), fill=dark)
    d.ellipse((W - 220, H - 560, W + 140, H - 200), fill=dark)

    c = data["cover"]
    tag = font(FONT_BOLD, 36)
    label = f"  {data['category']}  "
    tw = d.textlength(label, font=tag)
    d.rounded_rectangle((PAD, 260, PAD + tw, 260 + 64), radius=32, fill="white")
    d.text((PAD, 268), label, font=tag, fill=main)

    y = 380
    if c.get("kicker"):
        y = draw_lines(d, (PAD, y), wrap(d, c["kicker"], font(FONT_REG, 46), W - 2 * PAD),
                       font(FONT_REG, 46), "white", 14) + 24
    tf = font(FONT_BOLD, 96)
    y = draw_lines(d, (PAD, y), wrap(d, c["title"], tf, W - 2 * PAD), tf, "white", 22) + 36
    if c.get("subtitle"):
        sf = font(FONT_REG, 42)
        draw_lines(d, (PAD, y), wrap(d, c["subtitle"], sf, W - 2 * PAD), sf, "#FFFFFFDD", 16)

    hint = font(FONT_BOLD, 34)
    d.text((PAD, H - 200), "옆으로 넘겨보세요  →", font=hint, fill="white")
    footer(d, 1, total, "white")
    return img


def body_slide(slide, num, theme, idx, total):
    main, dark, light = theme
    img = Image.new("RGB", (W, H), light)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 18), fill=main)

    nf = font(FONT_BOLD, 56)
    d.ellipse((PAD, 150, PAD + 110, 260), fill=main)
    n = f"{num}"
    d.text((PAD + 55 - d.textlength(n, font=nf) / 2, 166), n, font=nf, fill="white")

    hf = font(FONT_BOLD, 72)
    y = draw_lines(d, (PAD, 310), wrap(d, slide["heading"], hf, W - 2 * PAD), hf, INK, 18) + 30
    d.rectangle((PAD, y, PAD + 80, y + 8), fill=main)
    y += 56

    bf = font(FONT_REG, 44)
    y = draw_lines(d, (PAD, y), wrap(d, slide["body"], bf, W - 2 * PAD), bf, SUB, 22)

    if slide.get("tip"):
        tf = font(FONT_BOLD, 38)
        tip_lines = wrap(d, "TIP  " + slide["tip"], tf, W - 2 * PAD - 80)
        box_h = len(tip_lines) * (38 + 16) + 70
        top = max(y + 50, H - 170 - box_h)
        d.rounded_rectangle((PAD, top, W - PAD, top + box_h), radius=28, fill="white",
                            outline=main, width=4)
        draw_lines(d, (PAD + 40, top + 35), tip_lines, tf, dark, 16)

    footer(d, idx, total, main)
    return img


def outro(data, theme, total):
    main, dark, _ = theme
    img = Image.new("RGB", (W, H), dark)
    d = ImageDraw.Draw(img)
    o = data["outro"]

    tf = font(FONT_BOLD, 76)
    y = draw_lines(d, (PAD, 200), wrap(d, o["title"], tf, W - 2 * PAD), tf, "white", 20) + 50

    pf = font(FONT_REG, 44)
    for p in o.get("points", []):
        d.ellipse((PAD + 6, y + 18, PAD + 34, y + 46), fill=main)
        y = draw_lines(d, (PAD + 64, y), wrap(d, p, pf, W - 2 * PAD - 64), pf, "white", 14) + 26

    cf = font(FONT_BOLD, 40)
    box_top = H - 400
    d.rounded_rectangle((PAD, box_top, W - PAD, box_top + 210), radius=32, fill=main)
    draw_lines(d, (PAD + 48, box_top + 40),
               ["저장해두고 필요할 때 꺼내보세요", f"매일 12시, {BRAND}"], cf, "white", 28)
    footer(d, total, total, "white")
    return img


def main(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    theme = THEMES[data["theme"]]
    total = len(data["slides"]) + 2
    out = path.parent

    images = [cover(data, theme, total)]
    for i, s in enumerate(data["slides"], start=1):
        images.append(body_slide(s, i, theme, i + 1, total))
    images.append(outro(data, theme, total))

    for i, img in enumerate(images, start=1):
        img.save(out / f"{i:02d}.png", optimize=True)
    print(f"{total} cards -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
