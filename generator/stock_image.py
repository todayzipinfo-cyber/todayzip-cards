"""Pixabay 무료 사진 검색/다운로드.

1) 후보 보기:  python generator/stock_image.py candidates posts/<날짜>/content.json
   장면마다 후보 8장을 번호를 붙인 한 장짜리 시트(posts/<날짜>/_cand_<장면>.jpg)로 만들고
   candidates.json 에 번호 -> Pixabay id 를 기록한다. 시트를 보고 가장 잘 맞는 사진의 id 를
   content.json 의 해당 장면 "image_id" 에 적는다.
2) make_reel.py 가 image_id 로 원본을 내려받는다 (image_id 가 없으면 첫 검색 결과를 쓴다).
이미 쓴 사진은 used_images.txt 에 기록해 다시 고르지 않는다.
"""
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

USED = Path(__file__).parent / "used_images.txt"
UA = {"User-Agent": "todayzip-cards/1.0"}


def api_key():
    key = os.environ.get("PIXABAY_API_KEY")
    if not key and os.name == "nt":  # setx 후 앱을 재시작하지 않은 경우
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key = winreg.QueryValueEx(k, "PIXABAY_API_KEY")[0]
    if not key:
        sys.exit("PIXABAY_API_KEY 가 없습니다")
    return key


def api(**params):
    params = urllib.parse.urlencode({"key": api_key(), "image_type": "photo", "safesearch": "true", **params})
    req = urllib.request.Request(f"https://pixabay.com/api/?{params}", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["hits"]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def used_ids():
    return set(USED.read_text().split()) if USED.exists() else set()


def search(queries, n=8):
    """검색어 목록을 차례로 검색해 아직 안 쓴 사진 n장을 모은다 (세로 사진 우선)."""
    used, seen, out = used_ids(), set(), []
    for q in queries:
        for orientation in ("vertical", "all"):
            for hit in api(q=q[:100], orientation=orientation, per_page=30, order="popular", min_height=1200):
                hid = str(hit["id"])
                if hid in used or hid in seen:
                    continue
                seen.add(hid)
                out.append(hit)
                if len(out) >= n:
                    return out
    return out


def contact_sheet(hits, path):
    tw, th = 300, 460
    sheet = Image.new("RGB", (4 * tw, 2 * th), "white")
    f = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 40)
    for i, hit in enumerate(hits[:8]):
        im = Image.open(io.BytesIO(get(hit["webformatURL"]))).convert("RGB")
        im.thumbnail((tw - 8, th - 8))
        x, y = (i % 4) * tw, (i // 4) * th
        sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        d = ImageDraw.Draw(sheet)
        d.rectangle((x + 4, y + 4, x + 60, y + 56), fill="black")
        d.text((x + 18, y + 4), str(i + 1), font=f, fill="yellow")
    sheet.save(path, quality=85)


def candidates_for(shots, outdir):
    """shots: [(이름, image_queries 를 가진 dict)] -> outdir 에 _cand_<이름>.jpg 와 candidates.json"""
    outdir = Path(outdir)
    result = {}
    for name, s in shots:
        if not s.get("image_queries"):
            continue
        hits = search(s["image_queries"])
        sheet = outdir / f"_cand_{name}.jpg"
        contact_sheet(hits, sheet)
        result[name] = {str(i + 1): h["id"] for i, h in enumerate(hits[:8])}
        print(name, sheet, len(hits), "후보")
    (outdir / "candidates.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def candidates(content_path):
    content_path = Path(content_path)
    data = json.loads(content_path.read_text(encoding="utf-8"))
    shots = [("cover", data["cover"])] + [(f"scene{i}", s) for i, s in enumerate(data["scenes"], 1)]
    candidates_for(shots, content_path.parent)


def download(image_id, out_path):
    hit = api(id=image_id)[0]
    Path(out_path).write_bytes(get(hit["largeImageURL"]))
    with USED.open("a") as f:
        f.write(f"{hit['id']}\n")
    return {"id": hit["id"], "page": hit["pageURL"]}


def fetch(queries, out_path):
    """후보를 고르지 않았을 때: 첫 번째 새 사진을 쓴다."""
    hits = search(queries, n=1)
    if not hits:
        raise RuntimeError(f"사진을 찾지 못했습니다: {queries}")
    return download(hits[0]["id"], out_path)


if __name__ == "__main__":
    if sys.argv[1] == "candidates":
        candidates(sys.argv[2])
    else:
        print(fetch([sys.argv[1]], sys.argv[2]))
