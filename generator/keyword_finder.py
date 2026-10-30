"""블로그 롱테일 키워드 찾기 (네이버 검색광고 키워드 도구 API + 네이버 블로그 검색 API).

  python generator/keyword_finder.py 결로 제습기 김치통
  python generator/keyword_finder.py 결로 --min 500 --max 20000 --top 40

1) 검색광고 API로 씨앗 키워드의 연관 키워드와 월간 검색수(PC+모바일)를 받는다.
2) 검색수가 --min ~ --max 사이인 것만 남긴다 (기본 1,000 ~ 10,000).
3) 블로그 검색 API 키가 있으면 키워드마다 블로그 문서 수를 세어
   "문서 수 ÷ 검색수"(경쟁도, 낮을수록 들어갈 틈이 큼) 순으로 정렬한다. 키가 없으면 검색수 순.
4) 결과를 화면에 표로 보여 주고 blog/keywords/<오늘>.csv 에 저장한다.

환경 변수 (사용자 환경 변수에 저장):
  NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID
      searchad.naver.com > 도구 > API 사용 관리 에서 발급 (무료)
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET   (선택: 문서 수)
      developers.naver.com > Application 등록 > 사용 API "검색" (무료, 하루 25,000회)
"""
import argparse
import base64
import csv
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
AD_HOST = "https://api.searchad.naver.com"


def env(name):
    v = os.environ.get(name, "").strip()
    if not v and sys.platform == "win32":  # 앱을 켠 뒤에 등록한 사용자 환경 변수도 읽는다
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = str(winreg.QueryValueEx(k, name)[0]).strip()
        except OSError:
            v = ""
    return v


def get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"API 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def related_keywords(seeds):
    """검색광고 키워드 도구: 씨앗(한 번에 5개까지, 공백 없이) -> 연관 키워드 목록."""
    key, secret, customer = env("NAVER_AD_API_KEY"), env("NAVER_AD_SECRET_KEY"), env("NAVER_AD_CUSTOMER_ID")
    if not (key and secret and customer):
        raise SystemExit("검색광고 API 키가 없어요. NAVER_AD_API_KEY / NAVER_AD_SECRET_KEY / NAVER_AD_CUSTOMER_ID 를 "
                         "사용자 환경 변수로 등록해 주세요 (searchad.naver.com > 도구 > API 사용 관리).")
    out = {}
    for i in range(0, len(seeds), 5):
        uri = "/keywordstool"
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(secret.encode(), f"{ts}.GET.{uri}".encode(), hashlib.sha256).digest()).decode()
        q = urllib.parse.urlencode({"hintKeywords": ",".join(s.replace(" ", "") for s in seeds[i:i + 5]), "showDetail": 1})
        data = get_json(f"{AD_HOST}{uri}?{q}", {
            "X-Timestamp": ts, "X-API-KEY": key, "X-Customer": customer, "X-Signature": sig})
        for k in data.get("keywordList", []):
            out[k["relKeyword"]] = k
        time.sleep(0.3)
    return list(out.values())


def count(v):
    """'< 10' 같은 값은 5로 본다."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return 5


def blog_docs(keyword):
    """블로그 검색 API의 total = 그 키워드의 블로그 문서 수. 키가 없으면 None."""
    cid, csec = env("NAVER_CLIENT_ID"), env("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        return None
    url = "https://openapi.naver.com/v1/search/blog.json?" + urllib.parse.urlencode({"query": keyword, "display": 1})
    return int(get_json(url, {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}).get("total", 0))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="블로그 롱테일 키워드 찾기")
    ap.add_argument("seeds", nargs="+", help="씨앗 키워드 (예: 결로 제습기)")
    ap.add_argument("--min", type=int, default=1000, help="월간 검색수 최소 (기본 1000)")
    ap.add_argument("--max", type=int, default=10000, help="월간 검색수 최대 (기본 10000)")
    ap.add_argument("--top", type=int, default=30, help="보여 줄 개수 (기본 30)")
    a = ap.parse_args()

    rows = []
    for k in related_keywords(a.seeds):
        pc, mo = count(k.get("monthlyPcQcCnt")), count(k.get("monthlyMobileQcCnt"))
        if a.min <= pc + mo <= a.max:
            rows.append({"keyword": k["relKeyword"], "search": pc + mo, "mobile": mo,
                         "ad_comp": k.get("compIdx", ""), "docs": None, "ratio": None})
    rows.sort(key=lambda r: -r["search"])
    rows = rows[:max(a.top * 3, a.top)]  # 문서 수는 상위 후보만 센다 (호출 수 절약)

    has_docs = bool(env("NAVER_CLIENT_ID") and env("NAVER_CLIENT_SECRET"))
    if has_docs:
        for r in rows:
            r["docs"] = blog_docs(r["keyword"])
            r["ratio"] = round(r["docs"] / r["search"], 1)
            time.sleep(0.1)
        rows.sort(key=lambda r: r["ratio"])
    rows = rows[:a.top]

    # 블로그 검색 API 는 2026년 신규 신청이 막혀서, 키가 없으면 문서 수 칸을 아예 뺀다
    print(f"씨앗: {', '.join(a.seeds)} · 월간 검색수 {a.min:,}~{a.max:,} · {len(rows)}개")
    print(f"{'키워드':<24}{'검색수':>8}{'모바일%':>8}" + (f"{'문서수':>10}{'경쟁도':>8}" if has_docs else "") + "  광고경쟁")
    for r in rows:
        mob = f"{r['mobile'] * 100 // max(r['search'], 1)}%"
        docs = f"{r['docs']:>10,}{r['ratio']:>8}" if has_docs else ""
        print(f"{r['keyword']:<24}{r['search']:>8,}{mob:>8}{docs}  {r['ad_comp']}")
    if has_docs:
        print("경쟁도 = 블로그 문서 수 ÷ 월간 검색수. 낮을수록 새 블로그가 들어갈 틈이 커요 (대략 10 이하면 좋음).")

    out = ROOT / "blog" / "keywords" / f"{datetime.date.today():%Y-%m-%d}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:  # 엑셀에서 한글이 안 깨지게 BOM
        w = csv.writer(f)
        w.writerow(["키워드", "월간검색수", "모바일검색수", "블로그문서수", "경쟁도(문서/검색)", "광고경쟁", "씨앗"])
        for r in rows:
            w.writerow([r["keyword"], r["search"], r["mobile"], r["docs"] if r["docs"] is not None else "",
                        r["ratio"] if r["ratio"] is not None else "", r["ad_comp"], " ".join(a.seeds)])
    print(f"저장: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
