"""todayzip 릴스 생성기 (AI 배경 이미지 + 질문형 표지 + 정보 장면).

사용법: python generator/make_reel.py posts/2026-10-07/content.json [--skip-images]
content.json 옆에 img_*.png(AI 배경), frame_*.png(미리보기), cover.jpg, reel.mp4 를 만든다.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from ai_image import generate  # noqa: E402
from make_cards import wrap  # noqa: E402
from stock_image import download as download_stock, fetch as fetch_stock  # noqa: E402

W, H = 1080, 1920
PAD = 80
FPS = 30
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
FONT_REG = "C:/Windows/Fonts/malgun.ttf"
BRAND = "@todayzip.info"
ACCENTS = {"life": "#4FA3FF", "money": "#3DDC84", "health": "#FFB547", "trend": "#C084FC",
           "weekend": "#FF6B6B", "mind": "#2DD4BF", "law": "#FACC15",
           # 살림 분야 (STYLE.md 요일표)
           "kitchen": "#FF9F43", "bath": "#38BDF8", "laundry": "#A5B4FC", "storage": "#FACC15",
           "season": "#FF6B6B", "picks": "#F472B6"}
DUR_COVER, DUR_SCENE, DUR_OUTRO, XFADE = 3.5, 4.5, 4.0, 0.5


def font(path, size):
    return ImageFont.truetype(path, size)


def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # winget 설치 직후 PATH 가 갱신되지 않은 경우
    hits = list(Path.home().glob("AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/**/bin/ffmpeg.exe"))
    if not hits:
        sys.exit("ffmpeg 를 찾을 수 없습니다")
    return str(hits[0])


def cover_fit(img):
    """이미지를 W x H 로 꽉 채워 자른다."""
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H)).convert("RGB")


def gradient(top_alpha, top_h, bottom_alpha=0, bottom_h=0):
    g = Image.new("L", (1, H), 0)
    for y in range(H):
        a = 0
        if y < top_h:
            a = top_alpha * (1 - y / top_h) ** 1.2
        if bottom_h and y > H - bottom_h:
            a = max(a, bottom_alpha * ((y - (H - bottom_h)) / bottom_h) ** 1.2)
        g.putpixel((0, y), int(a))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    layer.putalpha(g.resize((W, H)))
    return layer


def shadow_text(layer, xy, text, fnt, fill, blur=6):
    """가독성을 위해 흐린 그림자 위에 글자를 쓴다."""
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 3, xy[1] + 4), text, font=fnt, fill=(0, 0, 0, 200))
    layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(layer).text(xy, text, font=fnt, fill=fill)


def brand(layer):
    shadow_text(layer, (PAD, 70), "TODAYZIP", font(FONT_BOLD, 34), "white", 4)


def overlay_cover(c, accent):
    layer = gradient(215, 1000, 160, 500)
    d = ImageDraw.Draw(layer)
    brand(layer)
    y = 260
    if c.get("kicker"):
        kf = font(FONT_BOLD, 44)
        tw = d.textlength(c["kicker"], font=kf)
        d.rounded_rectangle((PAD, y, PAD + tw + 56, y + 76), radius=38, fill=accent)
        d.text((PAD + 28, y + 10), c["kicker"], font=kf, fill="#111111")
        y += 120
    tf = font(FONT_BOLD, 128)
    for line in wrap(d, c["title"], tf, W - 2 * PAD):
        shadow_text(layer, (PAD, y), line, tf, "white", 10)
        y += 128 + 26
    return layer


def overlay_scene(s, num, total, accent):
    layer = gradient(220, 820, 200, 760)
    d = ImageDraw.Draw(layer)
    brand(layer)
    # 상단: 번호 + 제목
    nf = font(FONT_BOLD, 56)
    d.ellipse((PAD, 200, PAD + 104, 304), fill=accent)
    n = str(num)
    d.text((PAD + 52 - d.textlength(n, font=nf) / 2, 212), n, font=nf, fill="#111111")
    hf = font(FONT_BOLD, 96)
    y = 340
    for line in wrap(d, s["heading"], hf, W - 2 * PAD):
        shadow_text(layer, (PAD, y), line, hf, "white", 8)
        y += 96 + 20
    # 하단 정보 박스 (릴스 UI 를 피하려고 아래 380px 은 비운다)
    bf = font(FONT_REG, 42)
    lines = wrap(d, s["body"], bf, W - 2 * PAD - 80)
    box_h = len(lines) * (42 + 20) + 80
    top = H - 400 - box_h
    box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((PAD - 10, top, W - PAD + 10, top + box_h), radius=34,
                                          fill=(15, 15, 15, 185))
    layer.alpha_composite(box)
    d = ImageDraw.Draw(layer)
    d.rectangle((PAD - 10, top + 30, PAD - 2, top + box_h - 30), fill=accent)
    yy = top + 40
    for line in lines:
        d.text((PAD + 40, yy), line, font=bf, fill="white")
        yy += 42 + 20
    # 진행 표시
    seg = (W - 2 * PAD - (total - 1) * 10) / total
    for i in range(total):
        x0 = PAD + i * (seg + 10)
        d.rounded_rectangle((x0, 150, x0 + seg, 158), radius=4,
                            fill=accent if i < num else (255, 255, 255, 90))
    return layer


def overlay_outro(o, accent):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 170))
    d = ImageDraw.Draw(layer)
    brand(layer)
    tf = font(FONT_BOLD, 96)
    y = 330
    for line in wrap(d, o["title"], tf, W - 2 * PAD):
        shadow_text(layer, (PAD, y), line, tf, "white", 8)
        y += 96 + 22
    y += 50
    pf = font(FONT_REG, 50)
    for p in o.get("points", []):
        d.ellipse((PAD + 4, y + 22, PAD + 30, y + 48), fill=accent)
        for line in wrap(d, p, pf, W - 2 * PAD - 60):
            d.text((PAD + 56, y), line, font=pf, fill="white")
            y += 50 + 14
        y += 22
    cf = font(FONT_BOLD, 50)
    top = H - 640
    d.rounded_rectangle((PAD, top, W - PAD, top + 200), radius=36, fill=accent)
    d.text((PAD + 50, top + 34), "저장하고 필요할 때 꺼내보세요", font=cf, fill="#111111")
    d.text((PAD + 50, top + 108), f"매일 12시 {BRAND}", font=cf, fill="#111111")
    return layer


MUSIC_DIR = Path(__file__).parent / "music"
THEME_MUSIC = {"life": "bright", "money": "upbeat", "health": "calm", "trend": "upbeat",
               "weekend": "bright", "mind": "calm", "law": "warm",
               "kitchen": "warm", "bath": "bright", "laundry": "calm", "storage": "bright",
               "season": "upbeat", "picks": "upbeat"}


def pick_music(data):
    """content.json 의 "music"(파일 이름) > 카테고리 기본 곡 > 폴더의 첫 곡."""
    tracks = sorted(MUSIC_DIR.glob("*.mp3"))
    if not tracks:
        sys.exit("generator/music 에 배경음이 없습니다 (python generator/make_music.py)")
    for name in (data.get("music"), THEME_MUSIC.get(data["theme"])):
        for t in tracks:
            if name and t.stem == name:
                return t
    return tracks[0]


def render_clip(ff, bg_path, ov_path, dur, out, zoom_in=True):
    """배경은 천천히 확대/축소, 그 위에 글자 레이어를 얹는다."""
    frames = int(dur * FPS)
    z = f"1+0.08*on/{frames}" if zoom_in else f"1.08-0.08*on/{frames}"
    vf = (f"[0:v]scale={W * 2}:{H * 2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps={FPS}[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]")
    subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", str(bg_path), "-loop", "1",
                    "-i", str(ov_path), "-filter_complex", vf, "-map", "[v]", "-t", str(dur),
                    "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(out)],
                   check=True)


def main(path, skip_images=False):
    path = Path(path)
    out = path.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    accent = ACCENTS[data["theme"]]
    ff = ffmpeg()
    tmp = out / "_build"
    tmp.mkdir(exist_ok=True)

    shots = [("cover", data["cover"])] + [(f"scene{i}", s) for i, s in enumerate(data["scenes"], 1)]
    credits = {}
    for name, s in shots:
        img = out / f"img_{name}.png"
        if skip_images and img.exists():
            continue
        if s.get("image_id"):  # 후보 시트에서 고른 무료 사진
            print("downloading", name, s["image_id"])
            credits[name] = download_stock(s["image_id"], img)
        elif s.get("image_queries"):  # 무료 사진, 첫 검색 결과
            print("searching", name, s["image_queries"])
            credits[name] = fetch_stock(s["image_queries"], img)
        else:  # AI 생성 (유료)
            print("generating", name)
            generate(s["image_prompt"], img)
    if credits:
        (out / "image_credits.json").write_text(json.dumps(credits, indent=2), encoding="utf-8")

    total = len(data["scenes"])
    clips = []
    for idx, (name, s) in enumerate(shots + [("outro", data["outro"])]):
        src = "cover" if name == "outro" else name  # 마지막은 표지 이미지를 다시 쓴다
        bg = cover_fit(Image.open(out / f"img_{src}.png"))
        if name == "outro":
            bg = bg.filter(ImageFilter.GaussianBlur(12))
        bg_path = tmp / f"bg_{name}.png"
        bg.save(bg_path)
        if name == "cover":
            ov, dur = overlay_cover(s, accent), DUR_COVER
        elif name == "outro":
            ov, dur = overlay_outro(s, accent), DUR_OUTRO
        else:
            ov, dur = overlay_scene(s, idx, total, accent), DUR_SCENE
        ov_path = tmp / f"ov_{name}.png"
        ov.save(ov_path)
        Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB").save(out / f"frame_{idx:02d}.jpg", quality=90)
        clip = tmp / f"clip_{idx:02d}.mp4"
        render_clip(ff, bg_path, ov_path, dur, clip, zoom_in=idx % 2 == 0)
        clips.append((clip, dur))

    # 장면 사이 크로스페이드 + 무음 오디오 트랙
    inputs, filt, last, offset = [], [], "[0:v]", 0.0
    for c, _ in clips:
        inputs += ["-i", str(c)]
    for i in range(1, len(clips)):
        offset += clips[i - 1][1] - XFADE
        tag = f"[x{i}]"
        filt.append(f"{last}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.2f}{tag}")
        last = tag
    total_dur = sum(d for _, d in clips) - XFADE * (len(clips) - 1)
    music = pick_music(data)
    print("music:", music.name)
    filt.append(f"[{len(clips)}:a]volume=0.55,afade=t=in:d=0.5,"
                f"afade=t=out:st={total_dur - 1.8:.2f}:d=1.8[a]")
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-stream_loop", "-1", "-i", str(music),
                    "-filter_complex", ";".join(filt),
                    "-map", last, "-map", "[a]", "-t", f"{total_dur:.2f}", "-c:v", "libx264",
                    "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
    shutil.copy(out / "frame_00.jpg", out / "cover.jpg")
    shutil.rmtree(tmp)
    print(f"reel.mp4 ({total_dur:.1f}s) -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], "--skip-images" in sys.argv)
