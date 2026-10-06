"""네이버 블로그 꾸미기용 이미지: 프로필(정사각)과 타이틀 배너.

사용법: python generator/make_branding.py <배경 사진>  -> branding/profile.png, branding/title_966x300.jpg
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from make_reel import FONT_BOLD, FONT_REG, font, shadow_text  # noqa: E402

OUT = Path(__file__).parent.parent / "branding"
ORANGE = "#FF9F43"
INK = "#1F1F1F"


def house(d, cx, cy, s, fill):
    """간단한 집 아이콘 (지붕 삼각형 + 몸체 + 문)."""
    d.polygon([(cx - s, cy - s * 0.1), (cx, cy - s), (cx + s, cy - s * 0.1)], fill=fill)
    d.rounded_rectangle((cx - s * 0.72, cy - s * 0.2, cx + s * 0.72, cy + s * 0.8), radius=s * 0.08, fill=fill)
    d.rounded_rectangle((cx - s * 0.18, cy + s * 0.25, cx + s * 0.18, cy + s * 0.8), radius=s * 0.06, fill=ORANGE)


def profile():
    n = 800
    img = Image.new("RGB", (n, n), ORANGE)
    d = ImageDraw.Draw(img)
    house(d, n / 2, n / 2 - 70, 210, "white")
    f = font(FONT_BOLD, 92)
    t = "todayzip"
    d.text(((n - d.textlength(t, font=f)) / 2, n - 250), t, font=f, fill="white")
    img.save(OUT / "profile.png")


def title(bg_path):
    w, h = 966, 300
    bg = Image.open(bg_path).convert("RGB")
    scale = max(w / bg.width, h / bg.height)
    bg = bg.resize((round(bg.width * scale), round(bg.height * scale)), Image.LANCZOS)
    x, y = (bg.width - w) // 2, (bg.height - h) // 2
    bg = bg.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(2)).convert("RGBA")
    bg.alpha_composite(Image.new("RGBA", (w, h), (0, 0, 0, 120)))
    d = ImageDraw.Draw(bg)
    house(d, 92, 150, 46, ORANGE)
    shadow_text(bg, (160, 70), "오늘의 집 살림 가이드", font(FONT_BOLD, 58), "white", 6)
    d = ImageDraw.Draw(bg)
    d.text((162, 155), "살림템 고르는 법 · 청소 세탁 주방 꿀팁", font=font(FONT_REG, 28), fill="white")
    d.rounded_rectangle((160, 210, 160 + 330, 256), radius=23, fill=ORANGE)
    d.text((180, 214), "매주 월 · 수 · 금 업데이트", font=font(FONT_BOLD, 26), fill=INK)
    d.text((w - 250, 258), "@todayzip.info", font=font(FONT_BOLD, 24), fill="white")
    bg.convert("RGB").save(OUT / "title_966x300.jpg", quality=92)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    profile()
    title(sys.argv[1])
    print("->", OUT)
