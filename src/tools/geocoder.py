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
import re
import time
import argparse
import sys
from pathlib import Path
from typing import Optional

import requests

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

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
# DDGS 웹 검색 → 주소 추출 → Nominatim 재시도
# ---------------------------------------------------------------------------

# 주소처럼 보이는 패턴 (이탈리아어/영어 기준)
_ADDRESS_RE = re.compile(
    r'\b(?:Via|Viale|Piazza|Vicolo|Corso|Largo|Borgo|Rue|Rua|Calle|Street|St\.|Avenue|Ave\.)\s'
    r'[A-Za-zÀ-ÿ\s]+,?\s*\d+',
    re.IGNORECASE,
)


def _web_search_address(name: str, city: str) -> Optional[tuple[float, float, str]]:
    """
    DDGS로 장소 검색 → 스니펫에서 주소 패턴 추출 → Nominatim.
    """
    query = f'"{name}" {city} address indirizzo'
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=5))
        time.sleep(1.0)
    except Exception as e:
        print(f"    [DDGS 오류] {e}", file=sys.stderr)
        return None

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
