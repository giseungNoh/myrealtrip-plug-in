"""
review_ratio.py — 장소별 현지어권 검색 결과 비율 계산

방법 (검색 결과 "건수" 비교 — 텍스트 언어 분석이 아니다):
  1. 현지어 리뷰 키워드로 DDG 검색 → 히트 건수 A
  2. 한국어(비교 대상 국가면 영어) 리뷰 키워드로 DDG 검색 → 히트 건수 B
  3. local_review_ratio = A / (A + B) * 100
     → 한국어로 쳤을 때 이 장소 언급이 거의 없고 현지어로만 많이 나오면
       외국인에게 덜 알려진 로컬 스팟이라는 뜻. 반대로 한국어로도 이미
       많이 나오면 이미 관광객(한국인)에게 알려진 곳이라는 뜻.
  4. 장바구니 JSON 업데이트 (--no-write 시 출력만)

주의: DDG API는 "총 몇 건" 같은 전체 히트수를 주지 않고 요청한 max_results개
까지만 반환한다. 그래서 이 비율은 상한(max_results) 안에서의 상대적 비교이며,
두 언어 모두 상한에 도달하는 초유명 관광지는 이 방식으로 잘 구분되지 않는다
(애초에 그런 곳은 "숨은 스팟" 판별 대상이 아니므로 실사용상 큰 문제는 아니다).

사용법:
    python3 src/tools/review_ratio.py --cart travel-cart/rome-trastevere-2026.json
    python3 src/tools/review_ratio.py --cart travel-cart/sapporo-2026.json --item 1
    python3 src/tools/review_ratio.py --cart travel-cart/rome-trastevere-2026.json --no-write

API 키 불필요. 외부 의존: ddgs
"""

import json
import os
import re
import subprocess
import sys
import time
import argparse
from pathlib import Path
from typing import Optional

# DDG 검색 백엔드(primp/reqwest)가 시스템 프록시 설정을 조회하다 SIGABRT로
# 죽는 경우가 있다 (macOS, 특히 샌드박스된 상위 프로세스 하에서 재현됨 —
# 메인 스레드에서도 발생해 스레드 격리만으로는 완전히 막지 못한다).
# env 프록시를 명시해 시스템 조회 자체를 최대한 우회한다.
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# ---------------------------------------------------------------------------
# 나라별 현지어 설정: (언어 코드, 현지어 리뷰 키워드)
# ---------------------------------------------------------------------------
COUNTRY_LANG: dict[str, tuple[str, str]] = {
    "Japan":    ("ja", "口コミ レビュー 評判"),
    "Italy":    ("it", "recensione opinioni dove mangiare"),
    "France":   ("fr", "avis critique restaurant quartier"),
    "Thailand": ("th", "รีวิว ร้านอาหาร ที่เที่ยว"),
    "Vietnam":  ("vi", "đánh giá quán ăn địa điểm"),
    "Taiwan":   ("zh", "評論 心得 推薦"),
    "Korea":    ("ko", "리뷰 후기 맛집"),
    "USA":      ("en", "review local spot"),
    "Spain":    ("es", "reseña opinión restaurante"),
    "Germany":  ("de", "Bewertung Erfahrung Restaurant"),
}

# 비교 대상(=한국인 관광객 인지도) 언어. 목적지 국가가 한국이면 한국어끼리
# 비교할 수 없으니 영어를 비교 언어로 쓴다.
_DEFAULT_TOURIST = ("ko", "리뷰")
_TOURIST_FOR_KOREA = ("en", "review")

# 한국어 비교 쿼리는 "Rome, Italy"가 아니라 "로마, 이탈리아"처럼 한국어로
# 검색해야 실제 한국 블로그·카페 글 히트가 제대로 잡힌다.
_KOREAN_COUNTRY_NAMES: dict[str, str] = {
    "Japan": "일본", "Italy": "이탈리아", "France": "프랑스", "Thailand": "태국",
    "Vietnam": "베트남", "Taiwan": "대만", "Korea": "한국", "USA": "미국",
    "Spain": "스페인", "Germany": "독일",
}
_KOREAN_CITY_NAMES: dict[str, str] = {
    "rome": "로마", "roma": "로마", "milan": "밀라노", "florence": "피렌체", "venice": "베네치아",
    "tokyo": "도쿄", "osaka": "오사카", "kyoto": "교토", "sapporo": "삿포로", "fukuoka": "후쿠오카",
    "paris": "파리", "lyon": "리옹",
    "bangkok": "방콕", "chiang mai": "치앙마이", "phuket": "푸켓",
    "hanoi": "하노이", "ho chi minh": "호치민", "da nang": "다낭", "hoi an": "호이안",
    "taipei": "타이베이",
    "seoul": "서울", "busan": "부산",
    "new york": "뉴욕", "nyc": "뉴욕", "los angeles": "로스앤젤레스",
    "chicago": "시카고", "san francisco": "샌프란시스코",
    "madrid": "마드리드", "barcelona": "바르셀로나",
    "berlin": "베를린", "munich": "뮌헨",
}


def _korean_city_label(city: str, country: str) -> str:
    """'Rome, Italy' → '로마, 이탈리아'. 매핑에 없는 도시명은 원문 그대로 둔다."""
    city_part = city.split(",")[0].strip()
    city_kr = _KOREAN_CITY_NAMES.get(city_part.lower(), city_part)
    country_kr = _KOREAN_COUNTRY_NAMES.get(country, country)
    return f"{city_kr}, {country_kr}"

# ---------------------------------------------------------------------------
# 국가 감지 (destination 문자열에서)
# ---------------------------------------------------------------------------

_COUNTRY_ALIASES: dict[str, str] = {
    "italy": "Italy", "italia": "Italy", "rome": "Italy", "roma": "Italy",
    "milan": "Italy", "florence": "Italy", "venice": "Italy",
    "japan": "Japan", "일본": "Japan", "tokyo": "Japan", "osaka": "Japan",
    "kyoto": "Japan", "sapporo": "Japan", "fukuoka": "Japan",
    "france": "France", "paris": "France", "lyon": "France",
    "thailand": "Thailand", "태국": "Thailand", "bangkok": "Thailand",
    "chiang mai": "Thailand", "phuket": "Thailand",
    "vietnam": "Vietnam", "베트남": "Vietnam", "hanoi": "Vietnam",
    "ho chi minh": "Vietnam", "da nang": "Vietnam", "hoi an": "Vietnam",
    "taiwan": "Taiwan", "대만": "Taiwan", "taipei": "Taiwan",
    "korea": "Korea", "한국": "Korea", "seoul": "Korea", "busan": "Korea",
    "usa": "USA", "미국": "USA", "new york": "USA", "nyc": "USA",
    "los angeles": "USA", "chicago": "USA", "san francisco": "USA",
    "spain": "Spain", "스페인": "Spain", "madrid": "Spain", "barcelona": "Spain",
    "germany": "Germany", "독일": "Germany", "berlin": "Germany", "munich": "Germany",
}


def _detect_country(destination: str) -> Optional[str]:
    dest_lower = destination.lower()
    for alias, country in _COUNTRY_ALIASES.items():
        if alias in dest_lower:
            return country
    return None


# ---------------------------------------------------------------------------
# DDG 검색 (서브프로세스 격리)
# ---------------------------------------------------------------------------
#
# DDGS().text()는 이 스크립트 자신을 `--_ddg-worker`로 재실행해 별도 프로세스에서
# 돌린다. primp가 SIGABRT로 죽어도 워커 프로세스만 죽고, 이 스크립트는 non-zero
# exit code를 받아 "검색 결과 없음"으로 처리하고 계속 진행한다 — 카트 전체 계산이
# 항목 하나의 크래시 때문에 통째로 중단되는 것을 막는다.

def _ddgs_search_subprocess(query: str, max_results: int) -> list[dict]:
    try:
        proc = subprocess.run(
            [sys.executable, __file__, "--_ddg-worker", query, str(max_results)],
            capture_output=True, text=True, timeout=20,
        )
    except subprocess.TimeoutExpired:
        print(f"  [DDG 타임아웃] {query[:50]}", file=sys.stderr)
        return []
    if proc.returncode != 0:
        print(f"  [DDG 워커 비정상 종료 exit={proc.returncode}] {query[:50]}", file=sys.stderr)
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# 핵심 계산 로직
# ---------------------------------------------------------------------------

def calculate_ratio(
    name: str,
    address: str,
    city: str,
    country: str,
    verbose: bool = True,
    max_results: int = 20,
) -> Optional[int]:
    """
    장소 하나에 대한 현지어권 검색 결과 비율 계산 (0~100).

    현지어 쿼리와 비교 언어(한국어, 또는 Korea 목적지면 영어) 쿼리를 각각 따로
    실행해 히트 건수를 비교한다. 한국어 쿼리 히트가 적고 현지어 쿼리 히트만
    많으면 한국인 관광객에게 덜 알려진 로컬 스팟이라는 뜻이다.

    반환값: int (0~100) 또는 None (계산 불가)
    """
    if country not in COUNTRY_LANG:
        print(f"  ⚠️  지원하지 않는 국가: {country}", file=sys.stderr)
        return None

    lang_code, local_kw = COUNTRY_LANG[country]
    tourist_lang, tourist_kw = _TOURIST_FOR_KOREA if country == "Korea" else _DEFAULT_TOURIST

    local_query = f'"{name}" {address} {local_kw}' if address else f'"{name}" {city} {local_kw}'
    tourist_city = _korean_city_label(city, country) if tourist_lang == "ko" else city
    tourist_query = f'"{name}" {tourist_city} {tourist_kw}'

    if verbose:
        print(f"  🔍 [현지어:{lang_code}] {local_query[:65]}", file=sys.stderr)
    local_results = _ddgs_search_subprocess(local_query, max_results)
    time.sleep(1.2)

    if verbose:
        print(f"  🔍 [비교언어:{tourist_lang}] {tourist_query[:65]}", file=sys.stderr)
    tourist_results = _ddgs_search_subprocess(tourist_query, max_results)
    time.sleep(1.2)

    local_count = len(local_results)
    tourist_count = len(tourist_results)
    total = local_count + tourist_count

    if verbose:
        print(f"  📊 검색 결과 건수: 현지어={local_count}, 비교언어={tourist_count} (상한 {max_results}건)", file=sys.stderr)
        if local_count >= max_results and tourist_count >= max_results:
            print(f"  ⚠️  양쪽 다 상한 도달 — 초유명 장소라 이 방식으론 구분이 잘 안 될 수 있음", file=sys.stderr)

    if total == 0:
        print(f"  ❌ 검색 결과 없음 — 비율 계산 불가", file=sys.stderr)
        return None

    ratio = round(local_count / total * 100)
    return max(0, min(100, ratio))


# ---------------------------------------------------------------------------
# 장바구니 처리
# ---------------------------------------------------------------------------

def process_cart(cart_path: Path, item_id: Optional[str], no_write: bool, verbose: bool) -> None:
    with open(cart_path, encoding="utf-8") as f:
        cart = json.load(f)

    destination = cart.get("destination", "")
    items = cart.get("items", [])

    country = _detect_country(destination)
    if not country:
        print(f"⚠️  국가 감지 실패: '{destination}'", file=sys.stderr)
        print(f"   지원 국가: {', '.join(COUNTRY_LANG.keys())}", file=sys.stderr)
        sys.exit(1)

    # 도시 추출 (괄호 제거)
    city = re.sub(r'\s*\(.*?\)', '', destination).strip()
    # 두 번째 쉼표 이후는 제거 (예: "Rome, Italy" 유지)
    city_parts = city.split(",")
    city = ", ".join(city_parts[:2]).strip() if len(city_parts) >= 2 else city

    print(f"\n장바구니: {cart_path.name}  |  여행지: {destination}  |  감지 국가: {country}\n", file=sys.stderr)

    updated = 0
    for item in items:
        if item_id and item.get("id") != item_id:
            continue

        label = item.get("name_local") or item.get("name") or "(이름없음)"
        existing = item.get("local_review_ratio")

        if existing is not None and item_id is None:
            print(f"⏭  {label}: 이미 {existing}% — 재계산하려면 --item {item['id']}", file=sys.stderr)
            continue

        print(f"\n▶ {label}", file=sys.stderr)
        name = item.get("name_local") or item.get("name") or ""
        address = item.get("address") or ""

        ratio = calculate_ratio(
            name=name,
            address=address,
            city=city,
            country=country,
            verbose=verbose,
        )

        if ratio is not None:
            print(f"  ✅ 현지어 리뷰 비율: {ratio}%", file=sys.stderr)
            item["local_review_ratio"] = ratio
            updated += 1
        else:
            print(f"  ❌ 비율 계산 실패 — null 유지", file=sys.stderr)

    if updated > 0 and not no_write:
        with open(cart_path, "w", encoding="utf-8") as f:
            json.dump(cart, f, ensure_ascii=False, indent=2)
        print(f"\n💾 저장 완료: {cart_path}  ({updated}건 업데이트)", file=sys.stderr)
    elif no_write:
        print(f"\n[--no-write] 파일 수정 없음 (계산만 수행)", file=sys.stderr)
    else:
        print(f"\n변경 없음 (업데이트 0건)", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 서브프로세스 워커 모드 — _ddgs_search_subprocess()가 이 스크립트 자신을
    # 재실행할 때 쓴다. argparse를 거치지 않고 바로 처리하고 종료한다.
    if len(sys.argv) >= 4 and sys.argv[1] == "--_ddg-worker":
        _worker_query, _worker_max = sys.argv[2], int(sys.argv[3])
        try:
            _worker_ddgs = DDGS()
            _worker_results = list(_worker_ddgs.text(_worker_query, max_results=_worker_max))
        except Exception:
            _worker_results = []
        print(json.dumps(_worker_results, ensure_ascii=False))
        sys.exit(0)

    parser = argparse.ArgumentParser(description="현지어 리뷰 비율 계산 → 장바구니 JSON 업데이트")
    parser.add_argument("--cart", "-c", required=True, help="장바구니 JSON 파일 경로")
    parser.add_argument("--item", "-i", default=None, help="특정 항목 ID만 처리 (예: --item 1)")
    parser.add_argument("--no-write", action="store_true", help="파일 수정 없이 결과만 출력")
    parser.add_argument("--quiet", "-q", action="store_true", help="중간 로그 최소화")
    args = parser.parse_args()

    path = Path(args.cart)
    if not path.exists():
        print(f"오류: {path} 없음", file=sys.stderr)
        sys.exit(1)

    process_cart(
        cart_path=path,
        item_id=args.item,
        no_write=args.no_write,
        verbose=not args.quiet,
    )
