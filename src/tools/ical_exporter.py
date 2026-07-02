"""
ical_exporter.py — 장바구니 JSON → .ics 캘린더 파일 생성

Google/Apple/Outlook 모두 .ics 파일 임포트 가능. OAuth 불필요.

사용법:
    python3 src/tools/ical_exporter.py \
        --cart travel-cart/rome-trastevere-2026.json \
        --start 2026-09-10

출력: <trip-id>.ics (캘린더 앱에 드래그&드롭)
외부 라이브러리 불필요 — 표준 라이브러리만 사용.
"""

import json
import re
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 시간대 슬롯 (장소 유형 → 시작/종료 시간)
# ---------------------------------------------------------------------------

_SLOT_MAP: list[tuple[set, tuple[int, int], tuple[int, int]]] = [
    # (키워드 집합, (시작H, 시작M), (종료H, 종료M))
    ({"카페", "cafe", "coffee", "breakfast", "아침", "시장", "market"}, (9, 0), (10, 30)),
    ({"점심", "lunch", "식당", "맛집", "restaurant", "ristorante", "trattoria", "osteria"}, (12, 0), (13, 30)),
    ({"와인바", "bar", "enoteca", "에노테카", "pub", "izakaya", "居酒屋", "酒場", "beer"}, (19, 0), (21, 0)),
    ({"클럽", "club", "nightclub", "야시장"}, (21, 0), (23, 0)),
]
_DEFAULT_SLOT = ((14, 0), (16, 0))  # 오후


def _time_slot(item: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    combined = ((item.get("type") or "") + " " + (item.get("name") or "")).lower()
    for keywords, start, end in _SLOT_MAP:
        if any(kw.lower() in combined for kw in keywords):
            return start, end
    return _DEFAULT_SLOT


# ---------------------------------------------------------------------------
# iCal 이스케이프
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    """iCal 텍스트 필드 이스케이프."""
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: 75옥텟 초과 줄은 CRLF + 공백으로 접기."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line + "\r\n"
    result = []
    buf = b""
    for char in line:
        char_bytes = char.encode("utf-8")
        if len(buf) + len(char_bytes) > 75:
            result.append(buf.decode("utf-8"))
            buf = b" " + char_bytes
        else:
            buf += char_bytes
    if buf:
        result.append(buf.decode("utf-8"))
    return "\r\n".join(result) + "\r\n"


def _dt(date: datetime) -> str:
    """datetime → iCal 기본 날짜시간 포맷 (로컬 float time)."""
    return date.strftime("%Y%m%dT%H%M%S")


def _uid(trip_id: str, item_id: str) -> str:
    return f"{trip_id}-{item_id}@myrealtrip-curator"


# ---------------------------------------------------------------------------
# VEVENT 생성
# ---------------------------------------------------------------------------

def _make_vevent(item: dict, date: datetime, trip_id: str) -> str:
    (sh, sm), (eh, em) = _time_slot(item)
    dtstart = date.replace(hour=sh, minute=sm, second=0, microsecond=0)
    dtend   = date.replace(hour=eh, minute=em, second=0, microsecond=0)

    name = item.get("name_local") or item.get("name") or "장소"
    item_type = item.get("type", "")
    summary = f"{name}" + (f" ({item_type})" if item_type else "")

    address = item.get("address") or ""
    lat = item.get("lat")
    lng = item.get("lng")

    maps_url = ""
    if lat and lng:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    elif address:
        maps_url = "https://www.google.com/maps/search/?api=1&query=" + address.replace(" ", "+")

    ratio = item.get("local_review_ratio")
    source = item.get("source_url") or ""
    note = item.get("note") or ""

    desc_parts = []
    if ratio is not None:
        desc_parts.append(f"현지어 리뷰 비율: {ratio}%")
    if maps_url:
        desc_parts.append(f"Google Maps: {maps_url}")
    if source:
        desc_parts.append(f"발굴 출처: {source}")
    if note:
        desc_parts.append(f"메모: {note}")
    description = "\\n".join(_esc(p) for p in desc_parts)

    lines = [
        "BEGIN:VEVENT",
        f"UID:{_uid(trip_id, item.get('id', name))}",
        f"DTSTART:{_dt(dtstart)}",
        f"DTEND:{_dt(dtend)}",
        f"SUMMARY:{_esc(summary)}",
    ]
    if address:
        lines.append(f"LOCATION:{_esc(address)}")
    if lat and lng:
        lines.append(f"GEO:{lat:.6f};{lng:.6f}")
    if description:
        lines.append(f"DESCRIPTION:{description}")
    lines.append("END:VEVENT")

    return "\r\n".join(lines) + "\r\n"


def _make_free_slot(day_num: int, date: datetime, trip_id: str) -> str:
    """하루 여백 슬롯 — 자유 탐방 이벤트."""
    dtstart = date.replace(hour=16, minute=30, second=0, microsecond=0)
    dtend   = date.replace(hour=17, minute=0,  second=0, microsecond=0)
    return "\r\n".join([
        "BEGIN:VEVENT",
        f"UID:{trip_id}-free-day{day_num}@myrealtrip-curator",
        f"DTSTART:{_dt(dtstart)}",
        f"DTEND:{_dt(dtend)}",
        "SUMMARY:🚶 자유 탐방 (여백)",
        "DESCRIPTION:이 시간은 비워두세요 — 근처를 걷다 우연히 발견한 곳에 들러보세요.",
        "END:VEVENT",
    ]) + "\r\n"


# ---------------------------------------------------------------------------
# 메인 변환
# ---------------------------------------------------------------------------

def export_ical(cart_path: Path, start_date: datetime, out_path: Optional[Path] = None) -> Path:
    with open(cart_path, encoding="utf-8") as f:
        cart = json.load(f)

    trip_id = cart.get("trip_id", "trip")
    destination = cart.get("destination", "")
    items = cart.get("items", [])

    # Day별 묶기
    days: dict[int, list[dict]] = {}
    no_day: list[dict] = []
    for item in items:
        d = item.get("day")
        if d is not None:
            days.setdefault(int(d), []).append(item)
        else:
            no_day.append(item)

    # day 없는 항목은 마지막 날 이후로 배치 (경고 포함)
    if no_day:
        print(f"⚠️  day 미지정 항목 {len(no_day)}건 — route_optimizer.py 먼저 실행 권장", file=sys.stderr)

    # iCal 조립
    vevents: list[str] = []
    days_with_items: set[int] = set()

    for day_num in sorted(days):
        date = start_date + timedelta(days=day_num - 1)
        for item in days[day_num]:
            vevents.append(_make_vevent(item, date, trip_id))
        vevents.append(_make_free_slot(day_num, date, trip_id))
        days_with_items.add(day_num)

    # day 없는 항목: 가장 마지막 날 다음 날
    if no_day:
        extra_day = (max(days_with_items) + 1) if days_with_items else 1
        extra_date = start_date + timedelta(days=extra_day - 1)
        for item in no_day:
            vevents.append(_make_vevent(item, extra_date, trip_id))

    cal_lines = [
        "BEGIN:VCALENDAR\r\n",
        "VERSION:2.0\r\n",
        "PRODID:-//myrealtrip-curator//KO\r\n",
        f"X-WR-CALNAME:{_esc(destination)} 여행일정\r\n",
        "X-WR-TIMEZONE:Asia/Seoul\r\n",
        "CALSCALE:GREGORIAN\r\n",
        "METHOD:PUBLISH\r\n",
    ]
    cal_lines.extend(vevents)
    cal_lines.append("END:VCALENDAR\r\n")

    # 출력 경로
    if out_path is None:
        out_path = cart_path.parent / f"{trip_id}.ics"

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(cal_lines)

    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="장바구니 → .ics 캘린더 파일 생성")
    parser.add_argument("--cart", "-c", required=True)
    parser.add_argument("--start", "-s", required=True,
                        help="여행 시작일 (YYYY-MM-DD). Day 1 = 이 날짜.")
    parser.add_argument("--out", "-o", default=None, help="출력 파일 경로 (기본: cart 옆에 .ics)")
    args = parser.parse_args()

    cart_path = Path(args.cart)
    if not cart_path.exists():
        print(f"오류: {cart_path} 없음", file=sys.stderr)
        sys.exit(1)

    try:
        start = datetime.strptime(args.start, "%Y-%m-%d")
    except ValueError:
        print("오류: --start는 YYYY-MM-DD 형식이어야 합니다", file=sys.stderr)
        sys.exit(1)

    out = Path(args.out) if args.out else None
    result = export_ical(cart_path, start, out)

    print(f"✅ .ics 생성 완료: {result}")
    print(f"   → 구글 캘린더: 캘린더 앱에서 '다른 캘린더 가져오기' 또는 파일 드래그&드롭")
    print(f"   → 애플 캘린더: 파일 더블클릭")
    print(f"   → Outlook: 파일 → 열기 → 캘린더 파일")
