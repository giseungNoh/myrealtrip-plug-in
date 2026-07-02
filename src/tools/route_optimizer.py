"""
route_optimizer.py — 장바구니 장소들을 거리 기반으로 Day별 배치 + 하루 동선 최적화

사용법:
    python3 src/tools/route_optimizer.py --cart travel-cart/rome-trastevere-2026.json --days 4
    python3 src/tools/route_optimizer.py --cart travel-cart/sapporo-2026-09.json --days 3

전제: geocoder.py로 lat/lng가 채워져 있어야 함.
외부 라이브러리 불필요 — 표준 라이브러리만 사용.
"""

import json
import math
import argparse
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 거리 계산 (Haversine)
# ---------------------------------------------------------------------------

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이의 직선 거리(km). 외부 라이브러리 없음."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def centroid(items: list[dict]) -> Optional[tuple[float, float]]:
    """좌표가 있는 장소들의 무게중심."""
    pts = [(i["lat"], i["lng"]) for i in items if i.get("lat") and i.get("lng")]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def dist_to_centroid(item: dict, center: tuple[float, float]) -> float:
    if not item.get("lat") or not item.get("lng"):
        return float("inf")
    return haversine(item["lat"], item["lng"], center[0], center[1])


# ---------------------------------------------------------------------------
# 시간대 추론 (장소 유형 → 방문 시간대 힌트)
# ---------------------------------------------------------------------------

_MORNING = {"카페", "cafe", "coffee", "아침", "朝", "市場", "시장", "market", "breakfast"}
_LUNCH   = {"맛집", "식당", "레스토랑", "restaurant", "ristorante", "昼食", "점심", "lunch", "trattoria", "osteria"}
_EVENING = {"와인바", "bar", "바", "enoteca", "에노테카", "酒場", "izakaya", "居酒屋", "pub", "beer"}
_NIGHT   = {"클럽", "club", "nightclub", "야시장", "夜市"}
_ANYTIME = {"관광", "박물관", "museum", "temple", "신사", "神社", "사원", "공원", "park", "산책", "온천", "温泉", "銭湯", "찜질방"}


def time_slot(item: dict) -> int:
    """
    장소 유형에서 권장 시간대를 숫자로 반환.
    0=아침, 1=점심, 2=오후, 3=저녁, 4=밤
    """
    type_str = (item.get("type") or "").lower()
    name_str = (item.get("name") or "").lower()
    combined = type_str + " " + name_str

    for kw in _MORNING:
        if kw.lower() in combined:
            return 0
    for kw in _LUNCH:
        if kw.lower() in combined:
            return 1
    for kw in _EVENING:
        if kw.lower() in combined:
            return 3
    for kw in _NIGHT:
        if kw.lower() in combined:
            return 4
    return 2  # 기본: 오후


TIME_LABELS = {0: "아침", 1: "점심", 2: "오후", 3: "저녁", 4: "밤"}


# ---------------------------------------------------------------------------
# 하루 동선 최적화 (Nearest Neighbor TSP)
# ---------------------------------------------------------------------------

def order_within_day(items: list[dict]) -> list[dict]:
    """
    좌표 있는 장소들은 Nearest Neighbor로 순서 최적화.
    좌표 없는 장소는 시간대 순으로 뒤에 배치.
    """
    has_coords = [i for i in items if i.get("lat") and i.get("lng")]
    no_coords  = [i for i in items if not (i.get("lat") and i.get("lng"))]

    if len(has_coords) <= 1:
        ordered = has_coords
    else:
        # 시간대가 가장 이른 장소를 출발점으로
        start = min(has_coords, key=time_slot)
        remaining = [i for i in has_coords if i is not start]
        ordered = [start]
        while remaining:
            last = ordered[-1]
            nearest = min(
                remaining,
                key=lambda x: haversine(last["lat"], last["lng"], x["lat"], x["lng"])
            )
            ordered.append(nearest)
            remaining.remove(nearest)

    # 좌표 없는 장소는 시간대 순으로 정렬해서 추가
    no_coords_sorted = sorted(no_coords, key=time_slot)
    return ordered + no_coords_sorted


# ---------------------------------------------------------------------------
# Day 배치 (고정 항목 유지 + null 항목 클러스터링)
# ---------------------------------------------------------------------------

def assign_days(items: list[dict], num_days: int) -> dict[int, list[dict]]:
    """
    day 지정된 항목은 그대로 유지.
    day=null 항목은 이미 배치된 항목들의 무게중심에 가장 가까운 day에 배정.
    """
    days: dict[int, list[dict]] = {d: [] for d in range(1, num_days + 1)}

    # 1단계: day 지정된 항목 먼저 배치
    fixed = [i for i in items if i.get("day") is not None]
    unassigned = [i for i in items if i.get("day") is None]

    for item in fixed:
        d = int(item["day"])
        if d in days:
            days[d].append(item)
        else:
            # 지정된 day가 num_days 초과인 경우 마지막 날에
            days[num_days].append(item)

    # 2단계: 좌표 없는 미배정 항목 → 빈 날이나 적은 날에 균등 배분
    no_coord_unassigned = [i for i in unassigned if not (i.get("lat") and i.get("lng"))]
    coord_unassigned = [i for i in unassigned if i.get("lat") and i.get("lng")]

    # 3단계: 좌표 있는 미배정 항목 → 가장 가까운 날의 무게중심에 배정
    for item in coord_unassigned:
        best_day = None
        best_dist = float("inf")

        for d, day_items in days.items():
            c = centroid(day_items)
            if c:
                dist = dist_to_centroid(item, c)
            else:
                # 비어 있는 날: 고르게 퍼뜨리기 위해 현재 항목 수 기준
                dist = len(day_items) * 999
            if dist < best_dist:
                best_dist = dist
                best_day = d

        if best_day is None:
            # 비어 있는 날 중 가장 적은 날
            best_day = min(days, key=lambda d: len(days[d]))
        days[best_day].append(item)

    # 4단계: 좌표 없는 미배정 항목 → 항목 수 적은 날에 균등 배분
    for item in no_coord_unassigned:
        least_day = min(days, key=lambda d: len(days[d]))
        days[least_day].append(item)

    return days


# ---------------------------------------------------------------------------
# 결과 포맷
# ---------------------------------------------------------------------------

def format_output(days: dict[int, list[dict]], total_items: int) -> dict:
    result_days = {}
    total_distance_km = 0.0

    for day_num in sorted(days):
        items = days[day_num]
        if not items:
            continue

        ordered = order_within_day(items)
        day_distance = 0.0
        prev = None

        formatted = []
        for item in ordered:
            dist_from_prev = None
            if prev and item.get("lat") and item.get("lng") and prev.get("lat") and prev.get("lng"):
                d = haversine(prev["lat"], prev["lng"], item["lat"], item["lng"])
                dist_from_prev = round(d, 2)
                day_distance += d
            prev = item

            formatted.append({
                "id": item.get("id"),
                "name": item.get("name_local") or item.get("name"),
                "type": item.get("type", ""),
                "address": item.get("address", ""),
                "lat": item.get("lat"),
                "lng": item.get("lng"),
                "time_slot": TIME_LABELS[time_slot(item)],
                "dist_from_prev_km": dist_from_prev,
                "maps_url": (
                    f"https://www.google.com/maps/search/?api=1&query={item['lat']},{item['lng']}"
                    if item.get("lat") and item.get("lng")
                    else f"https://www.google.com/maps/search/?api=1&query="
                         + (item.get("name_local") or item.get("name", "")).replace(" ", "+")
                ),
            })

        total_distance_km += day_distance
        result_days[f"day{day_num}"] = {
            "items": formatted,
            "total_distance_km": round(day_distance, 2),
        }

    return {
        "total_items": total_items,
        "total_distance_km": round(total_distance_km, 2),
        "days": result_days,
    }


def print_readable(output: dict) -> None:
    print("\n" + "═" * 55)
    print(f"총 {output['total_items']}개 장소 / 전체 이동 {output['total_distance_km']} km")
    print("═" * 55)
    for day_key, day_data in output["days"].items():
        day_num = day_key.replace("day", "")
        items = day_data["items"]
        dist = day_data["total_distance_km"]
        print(f"\n  Day {day_num}  (이동 약 {dist} km)")
        print(f"  {'─'*50}")
        for i, item in enumerate(items, 1):
            arrow = ""
            if item["dist_from_prev_km"] is not None:
                arrow = f"  ↓ {item['dist_from_prev_km']} km"
            if i > 1:
                print(f"  {arrow}")
            slot = item["time_slot"]
            name = item["name"] or "(이름없음)"
            tp = f"({item['type']})" if item["type"] else ""
            addr = item["address"][:45] if item["address"] else "주소 미확인"
            print(f"  {i}. [{slot}] {name} {tp}")
            print(f"       📍 {addr}")
            print(f"       🗺  {item['maps_url']}")
    print("\n" + "═" * 55)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="장바구니 동선 최적화")
    parser.add_argument("--cart", "-c", required=True, help="장바구니 JSON 파일 경로")
    parser.add_argument("--days", "-d", type=int, default=None,
                        help="여행 일수 (미지정 시 장바구니의 최대 day 값 사용)")
    parser.add_argument("--quiet", action="store_true", help="읽기 좋은 출력 생략, JSON만 출력")
    args = parser.parse_args()

    path = Path(args.cart)
    if not path.exists():
        print(f"오류: {path} 없음", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        cart = json.load(f)

    items = cart.get("items", [])

    # lat/lng 없는 항목 경고
    missing = [i for i in items if not (i.get("lat") and i.get("lng"))]
    if missing:
        print(f"⚠️  좌표 없는 항목 {len(missing)}건 — geocoder.py 먼저 실행 권장:", file=sys.stderr)
        for m in missing:
            print(f"   - {m.get('name_local') or m.get('name')}", file=sys.stderr)
        print("   (좌표 없는 항목은 시간대 순으로 배치됩니다)\n", file=sys.stderr)

    # 여행 일수 결정
    assigned_days = [i["day"] for i in items if i.get("day") is not None]
    max_assigned = max(assigned_days) if assigned_days else 1
    num_days = args.days or max_assigned
    if num_days < max_assigned:
        print(f"⚠️  --days {num_days} < 최대 지정일 {max_assigned}, {max_assigned}로 조정", file=sys.stderr)
        num_days = max_assigned

    days = assign_days(items, num_days)
    output = format_output(days, total_items=len(items))

    if not args.quiet:
        print_readable(output)

    print(json.dumps(output, ensure_ascii=False, indent=2))
