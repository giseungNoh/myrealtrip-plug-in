"""
geocoder.py — 장바구니 JSON의 lat/lng 자동 채우기

사용법:
    python3 src/tools/geocoder.py --cart travel-cart/rome-trastevere-2026.json
    python3 src/tools/geocoder.py --cart travel-cart/rome-trastevere-2026.json --dry-run

전략 순서:
  1~5. Nominatim(OpenStreetMap) — 이름+주소 조합
  6.   DDGS 웹 검색 → 주소 추출 → Nominatim 재시도

API: Nominatim — 무료, API 키 불필요, 초당 1건 제한 자동 준수
"""

import json
import os
import re
import subprocess
import time
import argparse
import sys
from pathlib import Path
from typing import Optional

import requests

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

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "myrealtrip-curator/1.0 (geocoder; contact=juks8666@gmail.com)"
RATE_LIMIT_SEC = 1.1  # Nominatim 정책: max 1 req/sec

_last_nominatim_time = 0.0


# ---------------------------------------------------------------------------
# Nominatim
# ---------------------------------------------------------------------------

def _nominatim_get(params: dict) -> list:
    global _last_nominatim_time
    elapsed = time.time() - _last_nominatim_time
    if elapsed < RATE_LIMIT_SEC:
        time.sleep(RATE_LIMIT_SEC - elapsed)
    resp = requests.get(
        NOMINATIM_URL,
        params={**params, "format": "json", "limit": 3},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    _last_nominatim_time = time.time()
    resp.raise_for_status()
    return resp.json()


def nominatim(query: str) -> Optional[tuple[float, float, str]]:
    """Nominatim으로 쿼리 → (lat, lng, 주소) 반환."""
    try:
        results = _nominatim_get({"q": query, "addressdetails": 1})
        if results:
            r = results[0]
            return float(r["lat"]), float(r["lon"]), r.get("display_name", "")
    except Exception as e:
        print(f"    [Nominatim 오류] {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# DDGS 웹 검색 (서브프로세스 격리) → 주소 추출 → Nominatim 재시도
# ---------------------------------------------------------------------------
#
# DDGS().text()는 이 스크립트 자신을 `--_ddg-worker`로 재실행해 별도 프로세스에서
# 돌린다. primp가 SIGABRT로 죽어도 워커 프로세스만 죽고, 이 스크립트는 non-zero
# exit code를 받아 "검색 결과 없음"으로 처리하고 계속 진행한다 — 카트 전체 좌표
# 채우기가 항목 하나의 크래시 때문에 통째로 중단되는 것을 막는다.

def _ddgs_search_subprocess(query: str, max_results: int) -> list[dict]:
    # ddgs가 콤마로 묶인 여러 백엔드를 조회할 때 동시 조회 엔진 수를
    # min(엔진수, ceil(max_results/10)+1)로 제한한다. 우리가 쓰는 6개 백엔드를
    # 전부 실제로 조회시키려면 최소 max_results=60 이상을 요청해야 한다
    # (그렇지 않으면 뒤쪽 엔진 — 특히 결과가 좋은 yahoo — 이 아예 호출조차
    # 안 되는 채로 조용히 빠진다). 실제로 쓸 결과 개수(max_results)는 그 다음에
    # 잘라낸다.
    fetch_count = max(max_results, 60)
    try:
        proc = subprocess.run(
            [sys.executable, __file__, "--_ddg-worker", query, str(fetch_count)],
            capture_output=True, text=True, timeout=25,
        )
    except subprocess.TimeoutExpired:
        print(f"    [DDG 타임아웃] {query[:50]}", file=sys.stderr)
        return []
    if proc.returncode != 0:
        print(f"    [DDG 워커 비정상 종료 exit={proc.returncode}] {query[:50]}", file=sys.stderr)
        return []
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return results[:max_results]


# 주소처럼 보이는 패턴 (이탈리아어/영어 기준)
_ADDRESS_RE = re.compile(
    r'\b(?:Via|Viale|Piazza|Vicolo|Corso|Largo|Borgo|Rue|Rua|Calle|Street|St\.|Avenue|Ave\.)\s'
    r'[A-Za-zÀ-ÿ\s]+,?\s*\d+',
    re.IGNORECASE,
)


def _filter_relevant(results: list[dict], name: str) -> list[dict]:
    """
    검색 결과 중 실제로 장소 이름이 언급된 것만 남긴다.

    검색 백엔드가 진짜 매칭을 못 찾으면 완전 무관한 필러 콘텐츠를 대신
    반환하는 경우가 있다 — 그런 결과에서 우연히 주소처럼 보이는 패턴을
    추출해 엉뚱한 좌표로 확정하는 것을 막는다.
    """
    name_lower = (name or "").strip().lower()
    if not name_lower:
        return results
    return [
        r for r in results
        if name_lower in (r.get("title", "") + " " + r.get("body", "")).lower()
    ]


def _web_search_address(name: str, city: str) -> Optional[tuple[float, float, str]]:
    """
    DDGS로 장소 검색 → 스니펫에서 주소 패턴 추출 → Nominatim.
    """
    query = f'"{name}" {city} address indirizzo'
    results = _ddgs_search_subprocess(query, max_results=5)
    results = _filter_relevant(results, name)
    time.sleep(1.0)

    for r in results:
        text = r.get("body", "") + " " + r.get("title", "")
        m = _ADDRESS_RE.search(text)
        if m:
            found_address = m.group(0).strip().rstrip(",")
            query2 = f"{found_address}, {city}"
            print(f"    → 주소 추출: {found_address!r}", file=sys.stderr)
            result = nominatim(query2)
            if result:
                return result

    return None


# ---------------------------------------------------------------------------
# 도시 파싱 헬퍼
# ---------------------------------------------------------------------------

def _parse_city(destination: str) -> str:
    """
    'Rome, Italy (Trastevere)' → 'Rome, Italy'
    괄호 안 동네명 제거 후 도시만 반환.
    """
    return re.sub(r'\s*\(.*?\)', '', destination).strip()


def _parse_neighborhood(destination: str) -> str:
    """'Rome, Italy (Trastevere)' → 'Trastevere'"""
    m = re.search(r'\((.+?)\)', destination)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# 항목별 전체 전략 실행
# ---------------------------------------------------------------------------

def geocode_item(item: dict, destination: str) -> Optional[tuple[float, float, str, str]]:
    """
    장바구니 항목 하나에 대해 순서대로 전략을 시도.
    반환: (lat, lng, 확인주소, 사용된전략) 또는 None
    """
    name_local = (item.get("name_local") or "").strip()
    name = (item.get("name") or "").strip()
    address = (item.get("address") or "").strip()
    city = _parse_city(destination)
    neighborhood = _parse_neighborhood(destination)

    # 전략 1~5: Nominatim
    nominatim_strategies: list[tuple[str, str]] = []

    if name_local and address:
        nominatim_strategies.append((f"{name_local}, {address}", "현지어명+주소"))
    if name and address and name != name_local:
        nominatim_strategies.append((f"{name}, {address}", "이름+주소"))
    if address:
        nominatim_strategies.append((address, "주소만"))
    if name_local and neighborhood and city:
        nominatim_strategies.append((f"{name_local}, {neighborhood}, {city}", "현지어명+동네+도시"))
    if name_local and city:
        nominatim_strategies.append((f"{name_local}, {city}", "현지어명+도시"))
    if name and city and name != name_local:
        nominatim_strategies.append((f"{name}, {city}", "이름+도시"))

    for query, label in nominatim_strategies:
        print(f"    [Nominatim·{label}] {query}", file=sys.stderr)
        result = nominatim(query)
        if result:
            lat, lng, confirmed = result
            return lat, lng, confirmed, label

    # 전략 6: 웹 검색 → 주소 추출 → Nominatim 재시도
    search_name = name_local or name
    if search_name:
        print(f"    [웹검색→주소] {search_name} {city}", file=sys.stderr)
        result = _web_search_address(search_name, city)
        if result:
            lat, lng, confirmed = result
            return lat, lng, confirmed, "웹검색주소추출"

    return None


# ---------------------------------------------------------------------------
# 장바구니 처리
# ---------------------------------------------------------------------------

def process_cart(cart_path: Path, dry_run: bool = False) -> dict:
    with open(cart_path, encoding="utf-8") as f:
        cart = json.load(f)

    destination = cart.get("destination", "")
    items = cart.get("items", [])
    needs = [i for i in items if i.get("lat") is None or i.get("lng") is None]
    done = [i for i in items if i.get("lat") is not None]

    print(f"\n장바구니: {cart_path.name}", file=sys.stderr)
    print(f"여행지: {destination}", file=sys.stderr)
    print(f"전체 {len(items)}건 / 좌표 없음 {len(needs)}건 / 이미 있음 {len(done)}건\n", file=sys.stderr)

    results: dict = {"found": [], "not_found": [], "skipped": []}

    for item in items:
        label = item.get("name_local") or item.get("name", "(이름없음)")

        if item.get("lat") is not None and item.get("lng") is not None:
            print(f"  ⏭  {label} — 좌표 있음 ({item['lat']}, {item['lng']})", file=sys.stderr)
            results["skipped"].append(item["id"])
            continue

        print(f"\n  📍 {label}", file=sys.stderr)
        geo = geocode_item(item, destination)

        if geo:
            lat, lng, confirmed, strategy = geo
            print(f"    ✅ ({lat:.6f}, {lng:.6f}) [{strategy}]", file=sys.stderr)
            print(f"       확인주소: {confirmed[:90]}", file=sys.stderr)
            if not dry_run:
                item["lat"] = round(lat, 7)
                item["lng"] = round(lng, 7)
                if not item.get("address"):
                    item["address"] = confirmed
            results["found"].append({
                "id": item["id"],
                "name": label,
                "lat": round(lat, 7),
                "lng": round(lng, 7),
                "strategy": strategy,
            })
        else:
            print(f"    ❌ 좌표 미확인 — 수동 입력 필요", file=sys.stderr)
            results["not_found"].append({"id": item["id"], "name": label})

    if not dry_run and results["found"]:
        with open(cart_path, "w", encoding="utf-8") as f:
            json.dump(cart, f, ensure_ascii=False, indent=2)
        print(f"\n💾 저장 완료: {cart_path}", file=sys.stderr)
    elif dry_run:
        print("\n[dry-run] 파일 수정 없음", file=sys.stderr)

    return results


def print_summary(results: dict) -> None:
    found, not_found, skipped = results["found"], results["not_found"], results["skipped"]
    print("\n" + "─" * 55)
    print(f"✅ 좌표 확보: {len(found)}건")
    for r in found:
        print(f"   {r['name']}: ({r['lat']}, {r['lng']}) [{r['strategy']}]")
    if skipped:
        print(f"⏭  기존 유지: {len(skipped)}건")
    if not_found:
        print(f"❌ 미확인: {len(not_found)}건 — 수동 입력 필요")
        for r in not_found:
            print(f"   {r['name']}")
    print("─" * 55)


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

    parser = argparse.ArgumentParser(description="장바구니 JSON 좌표 자동 채우기")
    parser.add_argument("--cart", "-c", required=True)
    parser.add_argument("--dry-run", action="store_true", help="파일 수정 없이 결과만 출력")
    args = parser.parse_args()

    path = Path(args.cart)
    if not path.exists():
        print(f"오류: {path} 파일 없음", file=sys.stderr)
        sys.exit(1)

    results = process_cart(path, dry_run=args.dry_run)
    print_summary(results)
    print(json.dumps({"cart": str(path), "dry_run": args.dry_run, **results},
                     ensure_ascii=False, indent=2))
