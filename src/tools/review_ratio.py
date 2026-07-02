"""
review_ratio.py — 장소별 현지어 리뷰 비율 실제 계산

방법:
  1. 장소를 현지어 키워드로 DDG 검색 → 상위 결과 스니펫 수집
  2. 영어/한국어 키워드로도 검색 → 관광객 텍스트 수집
  3. 전체 텍스트의 Unicode 문자 분포 + 언어 마커 단어 빈도로 언어 구분
  4. local_review_ratio = 현지어 마커 / (현지어 + 관광객어) * 100
  5. 장바구니 JSON 업데이트 (--no-write 시 출력만)

사용법:
    python3 src/tools/review_ratio.py --cart travel-cart/rome-trastevere-2026.json
    python3 src/tools/review_ratio.py --cart travel-cart/sapporo-2026.json --item 1
    python3 src/tools/review_ratio.py --cart travel-cart/rome-trastevere-2026.json --no-write

API 키 불필요. 외부 의존: ddgs, requests (표준 HTML 파싱은 re만 사용)
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from typing import Optional

import requests

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# ---------------------------------------------------------------------------
# 나라별 현지어 설정
# ---------------------------------------------------------------------------

# (local_lang_name, review_keyword, local_pattern, local_weight)
# local_pattern: 현지어로 작성된 텍스트임을 나타내는 Unicode 정규식
COUNTRY_LANG: dict[str, tuple[str, str, str]] = {
    "Japan":    ("ja", "口コミ レビュー 評判",        r"[぀-ヿ]"),
    "Italy":    ("it", "recensione opinioni dove mangiare", r"\b(?:di|del|della|degli|che|sono|per|con|una|questo|questa|anche|però|come|tutto|dalla|nella|molto)\b"),
    "France":   ("fr", "avis critique restaurant quartier", r"\b(?:de|du|des|les|est|avec|que|une|très|bien|pour|dans|sur|mais|vous|nous|leur)\b"),
    "Thailand": ("th", "รีวิว ร้านอาหาร ที่เที่ยว",    r"[฀-๿]"),
    "Vietnam":  ("vi", "đánh giá quán ăn địa điểm",   r"[đăơưắằặẹẻẽếềệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹàáâãèéêìíòóôõùúý]"),
    "Taiwan":   ("zh", "評論 心得 推薦",               r"[一-鿿]"),
    "Korea":    ("ko", "리뷰 후기 맛집",               r"[가-힯]"),
    "USA":      ("en", "hidden gem local spots neighborhood", r"\b(?:neighborhood|locals|hidden|gem|authentic|community|regulars|dive|joint|spot)\b"),
    "Spain":    ("es", "reseña opinión restaurante",   r"\b(?:de|del|que|con|para|por|una|este|esta|muy|bien|hay|los)\b"),
    "Germany":  ("de", "Bewertung Erfahrung Restaurant", r"\b(?:der|die|das|und|ist|von|mit|auf|ein|eine|ich|sehr|gut)\b"),
}

# 관광객 언어 패턴 (현지어 비율의 반대 방향)
TOURIST_PATTERNS: dict[str, str] = {
    "ko": r"[가-힯]",          # 한국어 관광객
    "en": r"\b(?:the|and|for|that|this|with|from|great|good|amazing|recommend|visited|loved|try|must)\b",
    "zh_cn": r"[一-鿿]",       # 중국어 간체 (관광객)
    "ja_tourist": r"[぀-ヿ]",  # 일본어 관광객
}

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
# Unicode 언어 문자 카운트
# ---------------------------------------------------------------------------

def _count_lang_markers(text: str) -> dict[str, int]:
    """텍스트에서 언어별 마커 출현 수 카운트."""
    tl = text.lower()
    return {
        "ja":  len(re.findall(r"[぀-ヿ]", text)),
        "ko":  len(re.findall(r"[가-힯]", text)),
        "zh":  len(re.findall(r"[一-鿿]", text)),
        "th":  len(re.findall(r"[฀-๿]", text)),
        "vi":  len(re.findall(r"[đăơưắằặẹẻẽếềệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹàáâãèéêìíòóôõùúý]", text)),
        "ar":  len(re.findall(r"[؀-ۿ]", text)),
        # 단어 마커 (소문자 처리 후)
        "it_w": len(re.findall(r"\b(?:di|del|della|degli|che|sono|per|con|una|questo|questa|anche|però|come|tutto|dalla|nella|molto|buono|ottimo|posto)\b", tl)),
        "fr_w": len(re.findall(r"\b(?:de|du|des|les|est|avec|que|une|très|bien|pour|dans|sur|mais|vous|nous|leur|bonne|adresse|recommande)\b", tl)),
        "en_w": len(re.findall(r"\b(?:the|and|for|that|this|with|from|great|good|amazing|recommend|visited|loved|must|try|place|spot|food|eat)\b", tl)),
        "es_w": len(re.findall(r"\b(?:de|del|que|con|para|por|una|este|esta|muy|bien|hay|los|las|sitio|lugar|comida|recomiendo)\b", tl)),
        "de_w": len(re.findall(r"\b(?:der|die|das|und|ist|von|mit|auf|ein|eine|ich|sehr|gut|schön|empfehle|tolles|lecker)\b", tl)),
        "en_local": len(re.findall(r"\b(?:neighborhood|locals|hidden|gem|authentic|community|regulars|dive|joint|hole.in.the.wall)\b", tl)),
    }


def _get_local_score(counts: dict[str, int], country: str) -> tuple[int, int]:
    """
    (local_score, tourist_score) 반환.
    country별로 어떤 마커가 '현지'인지 결정.
    """
    if country == "Japan":
        local = counts["ja"]
        tourist = counts["ko"] + counts["en_w"] + counts["zh"]
    elif country == "Italy":
        local = counts["it_w"] * 4  # 단어마커는 실제 글자수보다 희소 → 가중치
        tourist = counts["ko"] + counts["en_w"]
    elif country == "France":
        local = counts["fr_w"] * 4
        tourist = counts["ko"] + counts["en_w"]
    elif country == "Thailand":
        local = counts["th"]
        tourist = counts["ko"] + counts["en_w"] + counts["zh"]
    elif country == "Vietnam":
        local = counts["vi"]
        tourist = counts["ko"] + counts["en_w"] + counts["zh"]
    elif country == "Taiwan":
        local = counts["zh"]
        tourist = counts["ko"] + counts["en_w"]
    elif country == "Korea":
        local = counts["ko"]
        tourist = counts["en_w"] + counts["zh"] + counts["ja"]
    elif country == "USA":
        local = counts["en_local"] * 10  # "hidden gem / locals only" 같은 표현 집중
        tourist = counts["ko"] + counts["zh"]
    elif country == "Spain":
        local = counts["es_w"] * 4
        tourist = counts["ko"] + counts["en_w"]
    elif country == "Germany":
        local = counts["de_w"] * 4
        tourist = counts["ko"] + counts["en_w"]
    else:
        local = counts["en_w"]
        tourist = counts["ko"]
    return local, tourist


# ---------------------------------------------------------------------------
# DDG 검색 + 스니펫 텍스트 수집
# ---------------------------------------------------------------------------

def _search_snippets(query: str, max_results: int = 8) -> list[str]:
    """DDG 검색 결과의 title + body 스니펫 리스트 반환."""
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        time.sleep(1.2)
        texts = []
        for r in results:
            snippet = (r.get("title") or "") + " " + (r.get("body") or "")
            texts.append(snippet)
        return texts
    except Exception as e:
        print(f"  [DDG 오류] {query[:50]}: {e}", file=sys.stderr)
        return []


def _fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """
    URL 페이지의 텍스트 내용 추출 (정적 HTML만, JS 없음).
    실패 시 빈 문자열 반환.
    """
    skip_domains = {"google.", "facebook.", "instagram.", "twitter.", "youtube.",
                    "tripadvisor.", "yelp.", "booking.", "airbnb.", "wikipedia."}
    if any(d in url for d in skip_domains):
        return ""
    try:
        resp = requests.get(url, timeout=6, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        if resp.status_code != 200:
            return ""
        # HTML 태그 제거
        raw = resp.text[:max_chars * 5]
        text = re.sub(r'<script[^>]*>.*?</script>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>',  ' ', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&[a-zA-Z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text[:max_chars]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 핵심 계산 로직
# ---------------------------------------------------------------------------

def calculate_ratio(
    name: str,
    address: str,
    city: str,
    country: str,
    verbose: bool = True,
) -> Optional[int]:
    """
    장소 하나에 대한 현지어 리뷰 비율 계산 (0~100).
    반환값: int (0~100) 또는 None (계산 불가)
    """
    if country not in COUNTRY_LANG:
        print(f"  ⚠️  지원하지 않는 국가: {country}", file=sys.stderr)
        return None

    lang_name, review_kw, _ = COUNTRY_LANG[country]

    # 검색 대상 (현지어 쿼리 + 영어 쿼리 + 한국어 쿼리)
    place_query = f'"{name}" {city}'
    queries = [
        (f"{place_query} {review_kw}", "현지어"),
        (f"{place_query} review",      "영어"),
        (f"{place_query} 리뷰",        "한국어"),
    ]
    if address:
        # 주소 포함 현지어 쿼리 추가
        queries.insert(0, (f"{name} {address} {review_kw}", "현지어+주소"))

    all_text_parts: list[str] = []
    snippet_counts: dict[str, int] = {}

    for query, label in queries:
        if verbose:
            print(f"  🔍 [{label}] {query[:65]}", file=sys.stderr)
        snippets = _search_snippets(query, max_results=6)
        snippet_counts[label] = len(snippets)
        all_text_parts.extend(snippets)

    if not all_text_parts:
        print(f"  ❌ 검색 결과 없음 — 비율 계산 불가", file=sys.stderr)
        return None

    # 상위 결과 페이지 직접 fetch (현지어 검색 최상위 2건만)
    try:
        ddgs = DDGS()
        top_results = list(ddgs.text(queries[0][0], max_results=3))
        time.sleep(1.2)
        for r in top_results[:2]:
            url = r.get("href", "")
            if url:
                if verbose:
                    print(f"  📄 페이지 로드: {url[:70]}", file=sys.stderr)
                page_text = _fetch_page_text(url)
                if page_text:
                    all_text_parts.append(page_text)
                    time.sleep(0.5)
    except Exception:
        pass

    combined = " ".join(all_text_parts)
    counts = _count_lang_markers(combined)
    local_score, tourist_score = _get_local_score(counts, country)
    total = local_score + tourist_score

    if verbose:
        print(f"  📊 언어 마커: local={local_score}, tourist={tourist_score}, total={total}", file=sys.stderr)
        if total == 0:
            print(f"  ⚠️  언어 마커 미검출 (Latin 스크립트 국가는 낮을 수 있음)", file=sys.stderr)

    if total == 0:
        # 언어 마커가 전혀 없으면 None (신뢰 불가)
        return None

    ratio = round(local_score / total * 100)
    # 0~100 클리핑
    ratio = max(0, min(100, ratio))
    return ratio


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
