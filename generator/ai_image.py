"""Gemini로 세로(9:16) 배경 이미지를 생성한다.

사용법: python generator/ai_image.py "프롬프트" out.png
"""
import base64
import json
import os
import sys
import time
import urllib.request

MODEL = "gemini-3.1-flash-image"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

STYLE = (
    "Photorealistic, cinematic editorial photograph, natural light, rich detail, "
    "vertical 9:16 composition with calm empty space in the top third for a headline. "
    "No text, no letters, no logos, no watermark."
)


def api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key and os.name == "nt":  # setx 후 앱을 재시작하지 않은 경우
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key = winreg.QueryValueEx(k, "GEMINI_API_KEY")[0]
    if not key:
        sys.exit("GEMINI_API_KEY 가 없습니다")
    return key


def generate(prompt, out_path, retries=3):
    body = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n{STYLE}"}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}},
    }
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            for part in data["candidates"][0]["content"]["parts"]:
                if "inlineData" in part:
                    with open(out_path, "wb") as f:
                        f.write(base64.b64decode(part["inlineData"]["data"]))
                    return out_path
            raise RuntimeError(f"이미지 없음: {json.dumps(data)[:300]}")
        except Exception as e:
            if attempt == retries - 1:
                raise
            print("retry:", e)
            time.sleep(5 * (attempt + 1))


if __name__ == "__main__":
    print(generate(sys.argv[1], sys.argv[2]))
