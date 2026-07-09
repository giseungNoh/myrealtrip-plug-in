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
import argparse
from concurrent.futures import ThreadPoolExecutor
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

# ddgs의 "duckduckgo" 백엔드만 httpx 기반 클라이언트를 쓰는데, 이 클라이언트는
# 요청마다 TLS 설정을 무작위로 바꾼다(봇 탐지 회피 목적) — 그중 "TLS 1.3 이상 강제"
# 옵션이 걸리면 이 환경의 구버전 LibreSSL(2.8.3, TLS 1.3 미지원)에서 즉시
# "Unsupported protocol version 0x304"로 실패한다. 실측 결과 이 문제로 개별
# 검색 호출의 60~70%가 조용히 빈 결과로 처리되고 있었다. 나머지 백엔드는 전부
# primp(자체 TLS 스택)를 써서 이 문제가 없으므로 duckduckgo만 제외한다.
#
# "mullvad_brave"·"mullvad_google"도 함께 제외한다 — 이 둘이 의존하는 Mullvad의
# 검색 프록시 서비스 Leta가 2025-11-27부로 영구 종료돼(leta.mullvad.net DNS
# 조회 자체가 실패) ddgs 9.8.0에도 죽은 백엔드로 남아있다. 즉 ddgs로 구글
# 결과를 받는 유일한 경로였던 mullvad_google도 이미 죽어있었다 — 구글 결과가
# 필요하면 공식 Google Custom Search JSON API(무료 키 발급 필요)를 별도로
# 붙여야 한다.
_DDGS_BACKENDS = "bing,brave,mojeek,wikipedia,yahoo,yandex"

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
# DDG 검색 (서브프로세스 격리, 병렬 실행)
# ---------------------------------------------------------------------------
#
# DDGS().text()는 이 스크립트 자신을 `--_ddg-worker`로 재실행해 별도 프로세스에서
# 돌린다. primp가 SIGABRT로 죽어도 워커 프로세스만 죽고, 이 스크립트는 non-zero
# exit code를 받아 "검색 결과 없음"으로 처리하고 계속 진행한다 — 카트 전체 계산이
# 항목 하나의 크래시 때문에 통째로 중단되는 것을 막는다.
#
# 여러 쿼리를 스레드 풀로 동시에 쏘아도 안전하다: 실제 DDGS() 호출은 항상
# `--_ddg-worker` 서브프로세스(자신만의 메인 스레드를 가진 별도 프로세스) 안에서만
# 일어나고, 부모 프로세스의 스레드는 그 서브프로세스가 끝나기를 기다리기만 할 뿐
# primp/SystemConfiguration을 직접 건드리지 않기 때문이다.

def _ddgs_search_subprocess(query: str, max_results: int) -> list[dict]:
    # ddgs가 콤마로 묶인 여러 백엔드를 조회할 때 동시 조회 엔진 수를
    # min(엔진수, ceil(max_results/10)+1)로 제한한다. 우리가 쓰는 6개 백엔드를
    # 전부 실제로 조회시키려면 최소 max_results=60 이상을 요청해야 한다
    # (그렇지 않으면 뒤쪽 엔진 — 특히 가장 결과가 좋은 yahoo — 이 아예 호출조차
    # 안 되는 채로 조용히 빠진다). 실제로 쓸 결과 개수(max_results)는 그 다음에
    # 잘라낸다.
    fetch_count = max(max_results, 60)
    try:
        proc = subprocess.run(
            [sys.executable, __file__, "--_ddg-worker", query, str(fetch_count)],
            capture_output=True, text=True, timeout=25,
        )
    except subprocess.TimeoutExpired:
        print(f"  [DDG 타임아웃] {query[:50]}", file=sys.stderr)
        return []
    if proc.returncode != 0:
        print(f"  [DDG 워커 비정상 종료 exit={proc.returncode}] {query[:50]}", file=sys.stderr)
        return []
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return results[:max_results]


def _run_queries_parallel(
    tasks: list[tuple[str, str]], max_results: int, max_workers: int
) -> dict[str, list[dict]]:
    """
    (key, query) 튜플 목록을 스레드 풀로 동시에 검색한다.
    반환: key -> 검색 결과 리스트.
    """
    results: dict[str, list[dict]] = {}
    if not tasks:
        return results
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(_ddgs_search_subprocess, query, max_results): key
            for key, query in tasks
        }
        for future in future_to_key:
            key = future_to_key[future]
            results[key] = future.result()
    return results


# ---------------------------------------------------------------------------
# 쿼리 구성 + 비율 계산
# ---------------------------------------------------------------------------

def _build_queries(name: str, address: str, city: str, country: str) -> Optional[dict]:
    """
    장소 하나의 현지어 쿼리·비교언어 쿼리를 구성한다.
    반환: {"lang_code", "local_query", "tourist_lang", "tourist_query"} 또는
    지원하지 않는 국가면 None.
    """
    if country not in COUNTRY_LANG:
        print(f"  ⚠️  지원하지 않는 국가: {country}", file=sys.stderr)
        return None

    lang_code, local_kw = COUNTRY_LANG[country]
    tourist_lang, tourist_kw = _TOURIST_FOR_KOREA if country == "Korea" else _DEFAULT_TOURIST

    local_query = f'"{name}" {address} {local_kw}' if address else f'"{name}" {city} {local_kw}'
    tourist_city = _korean_city_label(city, country) if tourist_lang == "ko" else city
    tourist_query = f'"{name}" {tourist_city} {tourist_kw}'

    return {
        "lang_code": lang_code,
        "local_query": local_query,
        "tourist_lang": tourist_lang,
        "tourist_query": tourist_query,
    }


def _filter_relevant(results: list[dict], name: str) -> list[dict]:
    """
    검색 결과 중 실제로 장소 이름이 언급된 것만 남긴다.

    검색 백엔드가 진짜 매칭을 못 찾으면 완전 무관한 필러 콘텐츠(예: 엉뚱한
    소프트웨어 소개 페이지)를 대신 반환하는 경우가 있다. 그런 결과는 제목·본문
    어디에도 장소 이름이 안 나오므로, 이 필터로 걸러 비율 계산에서 제외한다.
    """
    name_lower = (name or "").strip().lower()
    if not name_lower:
        return results
    return [
        r for r in results
        if name_lower in (r.get("title", "") + " " + r.get("body", "")).lower()
    ]


def _ratio_from_counts(local_count: int, tourist_count: int, max_results: int, verbose: bool) -> Optional[int]:
    """
    현지어/비교언어 검색 히트 건수로 비율(0~100)을 계산한다.
    한국어(비교언어) 쿼리 히트가 적고 현지어 쿼리 히트만 많으면 한국인 관광객에게
    덜 알려진 로컬 스팟이라는 뜻이다. 반환값: int 또는 None(계산 불가).
    """
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

def process_cart(
    cart_path: Path,
    item_id: Optional[str],
    no_write: bool,
    verbose: bool,
    max_workers: int = 4,
) -> None:
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

    # 1단계: 처리 대상 항목을 추리고 (현지어/비교언어) 쿼리를 구성한다.
    max_results = 20
    to_process: list[dict] = []
    for item in items:
        if item_id and item.get("id") != item_id:
            continue

        label = item.get("name_local") or item.get("name") or "(이름없음)"
        existing = item.get("local_review_ratio")

        if existing is not None and item_id is None:
            print(f"⏭  {label}: 이미 {existing}% — 재계산하려면 --item {item['id']}", file=sys.stderr)
            continue

        name = item.get("name_local") or item.get("name") or ""
        address = item.get("address") or ""
        queries = _build_queries(name=name, address=address, city=city, country=country)
        if queries is None:
            continue

        to_process.append({"item": item, "label": label, "name": name, **queries})

    if not to_process:
        print("\n처리할 항목이 없습니다.", file=sys.stderr)
        return

    # 2단계: 모든 항목의 현지어·비교언어 쿼리를 한 번에 병렬로 검색한다.
    tasks: list[tuple[str, str]] = []
    for entry in to_process:
        item_key = entry["item"]["id"]
        tasks.append((f"{item_key}:local", entry["local_query"]))
        tasks.append((f"{item_key}:tourist", entry["tourist_query"]))

    print(
        f"🔍 {len(to_process)}개 장소 × 쿼리 2개 = {len(tasks)}건 병렬 검색 시작 "
        f"(동시 {max_workers}건)\n",
        file=sys.stderr,
    )
    if verbose:
        for entry in to_process:
            print(f"  ▶ {entry['label']}", file=sys.stderr)
            print(f"    [현지어:{entry['lang_code']}] {entry['local_query'][:65]}", file=sys.stderr)
            print(f"    [비교언어:{entry['tourist_lang']}] {entry['tourist_query'][:65]}", file=sys.stderr)

    search_results = _run_queries_parallel(tasks, max_results=max_results, max_workers=max_workers)

    # 3단계: 항목별로 결과를 모아 비율을 계산하고 반영한다.
    updated = 0
    print("", file=sys.stderr)
    for entry in to_process:
        item = entry["item"]
        item_key = item["id"]
        label = entry["label"]
        local_raw = search_results.get(f"{item_key}:local", [])
        tourist_raw = search_results.get(f"{item_key}:tourist", [])
        local_relevant = _filter_relevant(local_raw, entry["name"])
        tourist_relevant = _filter_relevant(tourist_raw, entry["name"])
        local_count = len(local_relevant)
        tourist_count = len(tourist_relevant)

        print(f"▶ {label}", file=sys.stderr)
        if verbose and (len(local_raw) != local_count or len(tourist_raw) != tourist_count):
            print(
                f"  🧹 무관한 결과 제외: 현지어 {len(local_raw)}→{local_count}건, "
                f"비교언어 {len(tourist_raw)}→{tourist_count}건",
                file=sys.stderr,
            )
        ratio = _ratio_from_counts(local_count, tourist_count, max_results, verbose)

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
            _worker_results = list(
                _worker_ddgs.text(_worker_query, max_results=_worker_max, backend=_DDGS_BACKENDS)
            )
        except Exception:
            _worker_results = []
        print(json.dumps(_worker_results, ensure_ascii=False))
        sys.exit(0)

    parser = argparse.ArgumentParser(description="현지어 리뷰 비율 계산 → 장바구니 JSON 업데이트")
    parser.add_argument("--cart", "-c", required=True, help="장바구니 JSON 파일 경로")
    parser.add_argument("--item", "-i", default=None, help="특정 항목 ID만 처리 (예: --item 1)")
    parser.add_argument("--no-write", action="store_true", help="파일 수정 없이 결과만 출력")
    parser.add_argument("--quiet", "-q", action="store_true", help="중간 로그 최소화")
    parser.add_argument(
        "--workers", "-w", type=int, default=4,
        help="동시 검색 개수 (기본 4). DDG 차단이 잦으면 낮춘다",
    )
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
        max_workers=args.workers,
    )
