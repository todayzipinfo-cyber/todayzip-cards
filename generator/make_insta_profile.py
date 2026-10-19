"""인스타그램 프로필 사진 (원형으로 잘려도 안전하게, 작게 보여도 알아보게).

사용법: python generator/make_insta_profile.py  -> branding/profile_instagram.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from make_branding import ORANGE, OUT, house  # noqa: E402
from make_reel import FONT_BOLD, font  # noqa: E402


def sparkle(d, cx, cy, r, fill):
    """반짝이 (깨끗해진 느낌)."""
    k = r * 0.22
    d.polygon([(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
               (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)], fill=fill)


def main():
    n = 1080
    img = Image.new("RGB", (n, n), ORANGE)
    d = ImageDraw.Draw(img)
    house(d, n / 2, n / 2 - 40, 300, "white")
    sparkle(d, n / 2 + 300, n / 2 - 250, 70, "white")
    sparkle(d, n / 2 + 375, n / 2 - 120, 36, "white")
    f = font(FONT_BOLD, 96)
    t = "살림 해결소"
    d.text(((n - d.textlength(t, font=f)) / 2, n / 2 + 290), t, font=f, fill="white")
    img.save(OUT / "profile_instagram.png")


if __name__ == "__main__":
    main()
