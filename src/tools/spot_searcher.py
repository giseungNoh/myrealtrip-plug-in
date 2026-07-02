"""
spot_searcher.py — myrealtrip-curator discover-local-spots 병렬 검색 엔진

사용법:
    python spot_searcher.py --destination 삿포로 --country japan --type 온천
    python spot_searcher.py --destination 다낭 --country vietnam --type 맛집 --theme 먹방

출력: JSON (stdout) — 협찬 배제된 후보 목록
"""

import asyncio
import json
import re
import argparse
import sys
from dataclasses import dataclass, asdict
from typing import Optional

import aiohttp
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# ---------------------------------------------------------------------------
# 협찬 표기 감지 패턴 (언어별)
# ---------------------------------------------------------------------------
SPONSORED_PATTERNS: dict[str, re.Pattern] = {
    "ja": re.compile(
        # 일본어 협찬 표기 — 명시적 형태만 잡는다 (단순 "PR" 단어는 제외)
        r"【PR】|\[PR\]|#PR\b|PR記事|本記事はPR|この記事はPR"
        r"|案件です|案件として|モニターとして|モニター品"
        r"|招待いただきました|ご招待いただき"
        r"|提供品|商品提供|タイアップ|ステルスマーケ"
        r"|協賛いただき|協賛を受け",
    ),
    "vi": re.compile(
        r"tài trợ|quảng cáo|hợp tác thương mại|được tài trợ|collab",
        re.IGNORECASE,
    ),
    "th": re.compile(
        r"สปอนเซอร์|ได้รับการสนับสนุน|โฆษณา|ร่วมกับ|#ad",
        re.IGNORECASE,
    ),
    "zh": re.compile(
        r"贊助|廣告|合作|業配|置入|邀稿|試吃邀約|試用|受邀",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        r"sponsorisé|partenariat|offert par|en collaboration avec|publicité|#ad",
        re.IGNORECASE,
    ),
    "it": re.compile(
        r"sponsorizzato|in collaborazione con|offerto da|pubblicità|#ad",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\bsponsored\b|\bgifted\b|\b#ad\b|\bpaid partnership\b"
        r"|\bin collaboration with\b|\bpaid post\b",
        re.IGNORECASE,
    ),
    "de": re.compile(
        r"gesponsert|werbung\b|kooperation|anzeige|#werbung",
        re.IGNORECASE,
    ),
    "es": re.compile(
        r"patrocinado|publicidad|en colaboración con|regalo de|#ad",
        re.IGNORECASE,
    ),
    "ko": re.compile(
        r"협찬|광고|제공|스폰서|PR\b|대가|무상|지원받",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# 국가별 검색 쿼리 빌더 (검증된 키워드 우선)
# ---------------------------------------------------------------------------
COUNTRY_CONFIG: dict[str, dict] = {
    "japan": {
        "lang": "ja",
        "queries": lambda d, t: [
            f"site:ameblo.jp {d} {t} 行ってみた",
            f"site:hatenablog.com {d} {t} 行った",
            f"site:note.com {d} {t} ひとりで",
            f"site:note.com {d} {t} 地元",
            f"site:ameblo.jp {d} {t} 感想",
        ],
        "exclude_domains": [
            "jalan.net", "4travel.jp", "rtrp.jp", "newt.net",
            "oyutabi.biglobe.ne.jp", "asoview.com", "yukoyuko.net",
            "tabelog.com", "tripadvisor",
        ],
    },
    "vietnam": {
        "lang": "vi",
        "queries": lambda d, t: [
            # foody.vn/bai-viet/ 경로만 채택 — 집계 점수 페이지(/quan-an) 배제
            f"site:foody.vn {d} {t} bài viết cá nhân",
            f"site:blogspot.com {d} {t} quán ăn ngon ít biết",
            f"site:wordpress.com {d} {t} ăn ngon giá rẻ",
        ],
        "exclude_domains": [
            "klook.com", "ivivu.com", "bazantravel.com", "tripadvisor",
            "agoda.com", "vinpearl.com", "tourism.danang.vn",
            "foody.vn/da-nang/quan-an",  # 집계 점수 페이지
        ],
    },
    "thailand": {
        "lang": "th",
        "queries": lambda d, t: [
            # Pantip 합격률 100% — 우선 순위
            f"site:pantip.com {d} {t} รีวิว",
            f"site:pantip.com {d} {t} ซ่อนเร้น กทม",
            # 개인 블로그 대체 소스
            f"site:medium.com {d} {t} ร้านอาหาร คนท้องถิ่น",
            f"site:bloggang.com {d} {t} ร้านอาหาร",
        ],
        "exclude_domains": [
            "hungryhub.com", "wongnai.com", "tripadvisor",
            "thestandard.co", "krungsriconsumer.com", "soimilk.com",
        ],
    },
    "taiwan": {
        "lang": "zh",
        "queries": lambda d, t: [
            f"site:pixnet.net {d} {t} 在地人",
            f"site:ptt.cc {d} {t} 推薦",
            f"site:pixnet.net {d} {t} 隱藏版",
        ],
        "exclude_domains": [
            "tripadvisor", "walkerland.com.tw", "travel.yam.com", "klook.com",
        ],
    },
    "france": {
        "lang": "fr",
        "queries": lambda d, t: [
            # Over-Blog 개인 블로그 — 검증 합격 소스
            f"site:over-blog.com {d} {t} j'ai testé 2024",
            f"site:over-blog.com {d} {t} j'y suis allée coup de coeur",
            # 일반 검색 — 개인 블로그 표현 강화 (Routard 포럼 HTTP 403 우회)
            f'{d} {t} "mon adresse secrète" OR "resto de quartier" blog 2024',
            f'{d} {t} "endroit caché" "les locaux" -tripadvisor -thefork -michelin',
        ],
        "exclude_domains": [
            "tripadvisor", "thefork.com", "michelin.com", "paris.fr",
            "pvam.fr", "parisvousalime.com", "routard.com",  # 편집 기사 배제
        ],
    },
    "italy": {
        "lang": "it",
        "queries": lambda d, t: [
            f"site:reddit.com/r/italy {d} {t} nascosto",
            f'{d} {t} "trattoria nascosta" OR "posto sconosciuto" blog personale',
        ],
        "exclude_domains": [
            "tripadvisor", "thefork.com", "gamberorosso.it",
        ],
    },
    "usa": {
        "lang": "en",
        "queries": lambda d, t: [
            # Reddit 직접 검색(site:reddit.com)은 HTTP 403 차단됨 — 우회 검색 사용
            f'{d} {t} hidden gem locals reddit 2024 -yelp -tripadvisor',
            f"site:substack.com {d} {t} hidden gem locals",
            f"site:wordpress.com {d} {t} neighborhood restaurant locals",
            f"site:blogspot.com {d} {t} hidden gem food",
        ],
        "exclude_domains": [
            "tripadvisor", "yelp.com", "eater.com", "timeout.com",
            "resy.com", "joinmytrip.com", "nimbuskitchen.com",
            "tastingtable.com", "rockefellercenter.com",
        ],
    },
    "uk": {
        "lang": "en",
        "queries": lambda d, t: [
            f"site:reddit.com/r/{d.lower().replace(' ', '')} {t} hidden locals",
            f'{d} {t} "hidden gem" "locals only" personal blog',
        ],
        "exclude_domains": ["tripadvisor", "timeout.com"],
    },
    "germany": {
        "lang": "de",
        "queries": lambda d, t: [
            f'{d} {t} Geheimtipp Einheimische persönlicher Blog',
            f"site:reddit.com/r/germany {d} {t} Geheimtipp",
        ],
        "exclude_domains": ["tripadvisor", "yelp.de"],
    },
    "spain": {
        "lang": "es",
        "queries": lambda d, t: [
            f'{d} {t} "lugar escondido" OR "rincón secreto" blog personal',
            f"site:reddit.com/r/spain {d} {t} desconocido",
        ],
        "exclude_domains": ["tripadvisor", "timeout.com"],
    },
    "indonesia": {
        "lang": "id",
        "queries": lambda d, t: [
            f"site:kaskus.co.id {d} {t} review jujur",
            f'{d} {t} "kuliner tersembunyi" blog pribadi',
        ],
        "exclude_domains": ["tripadvisor", "traveloka.com"],
    },
    "hongkong": {
        "lang": "zh",
        "queries": lambda d, t: [
            f"site:lihkg.com {d} {t} 隱世",
            f"site:hkdiscuss.com {d} {t} 推介",
        ],
        "exclude_domains": ["tripadvisor", "openrice.com"],
    },
}

# ---------------------------------------------------------------------------
# 데이터 클래스
# ---------------------------------------------------------------------------
@dataclass
class SpotCandidate:
    title: str
    source_url: str
    snippet: str
    sponsored: bool
    sponsored_marker: Optional[str]
    query_used: str


# ---------------------------------------------------------------------------
# 비동기 fetch + 협찬 검사
# ---------------------------------------------------------------------------
FETCH_TIMEOUT = aiohttp.ClientTimeout(total=8, connect=3)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


async def fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    """페이지 앞 6000자만 가져온다 (협찬 표기는 보통 상단에 있음)."""
    try:
        async with session.get(url, timeout=FETCH_TIMEOUT, allow_redirects=True) as resp:
            if resp.status == 200:
                raw = await resp.read()
                text = raw[:12000].decode("utf-8", errors="ignore")
                return text
    except Exception:
        pass
    return ""


def detect_sponsored(text: str, lang: str) -> tuple[bool, Optional[str]]:
    """협찬 표기 감지. (is_sponsored, matched_marker) 반환."""
    pattern = SPONSORED_PATTERNS.get(lang, SPONSORED_PATTERNS["en"])
    m = pattern.search(text)
    if m:
        return True, m.group(0)
    return False, None


_ALWAYS_EXCLUDED = [
    "bing.com/aclick", "bing.com/search", "google.com/search",
    "instagram.com", "facebook.com/watch",
    "booking.com", "hotels.com", "agoda.com", "expedia.com",
    "tripadvisor", "jalan.net", "4travel.jp", "rtrp.jp",
    "livejapan.com", "matcha-jp.com", "tsunagulocal.com",
]


def is_excluded_domain(url: str, exclude_list: list[str]) -> bool:
    all_excludes = _ALWAYS_EXCLUDED + exclude_list
    return any(ex in url for ex in all_excludes)


def extract_site_domain(query: str) -> Optional[str]:
    """'site:ameblo.jp ...' 에서 'ameblo.jp' 추출."""
    m = re.search(r"site:([^\s]+)", query)
    return m.group(1) if m else None


def url_matches_site(url: str, site_domain: Optional[str]) -> bool:
    """site: 한정 쿼리의 경우 결과 URL이 해당 도메인인지 검증."""
    if not site_domain or not url:
        return True  # site: 없는 일반 쿼리는 통과
    return site_domain in url


def _ddgs_search_sync(query: str, max_results: int) -> list[dict]:
    """스레드 풀에서 실행되는 동기 DDG 검색."""
    ddgs = DDGS()
    return list(ddgs.text(query, max_results=max_results))


# ---------------------------------------------------------------------------
# 검색 + 검증 (쿼리 1개)
# ---------------------------------------------------------------------------
async def search_and_verify(
    query: str,
    lang: str,
    exclude_domains: list[str],
    session: aiohttp.ClientSession,
    max_results: int = 6,
    sem: Optional[asyncio.Semaphore] = None,
) -> list[SpotCandidate]:
    async def _do_search():
        return await asyncio.to_thread(_ddgs_search_sync, query, max_results)

    try:
        if sem:
            async with sem:
                raw_results = await _do_search()
        else:
            raw_results = await _do_search()
    except Exception as e:
        print(f"[WARN] Search failed for '{query}': {e}", file=sys.stderr)
        return []

    # URL 필드명 정규화
    for r in raw_results:
        if "url" in r and "href" not in r:
            r["href"] = r["url"]
        r.setdefault("href", "")
        r.setdefault("title", "")
        r.setdefault("body", "")

    # site: 도메인 추출 (결과 URL 검증용)
    site_domain = extract_site_domain(query)

    # URL이 없는 결과는 스니펫으로만 협찬 확인
    no_url = [r for r in raw_results if not r["href"]]
    yt_results = [r for r in raw_results if "youtube.com" in r["href"]]
    text_results = [
        r for r in raw_results
        if r["href"]
        and "youtube.com" not in r["href"]
        and not is_excluded_domain(r["href"], exclude_domains)
        and url_matches_site(r["href"], site_domain)  # site: 필터 준수 검증
    ]

    # 텍스트 소스 병렬 fetch
    fetch_tasks = [fetch_page(session, r["href"]) for r in text_results]
    pages = await asyncio.gather(*fetch_tasks)

    candidates: list[SpotCandidate] = []

    # URL 없는 결과 — 스니펫 텍스트만으로 협찬 검사
    for result in no_url:
        snippet_text = result.get("title", "") + " " + result.get("body", "")
        is_sp, marker = detect_sponsored(snippet_text, lang)
        candidates.append(SpotCandidate(
            title=result["title"],
            source_url="",
            snippet=result["body"][:250],
            sponsored=is_sp,
            sponsored_marker=marker,
            query_used=query,
        ))

    for result, page_text in zip(text_results, pages):
        # page_text가 없으면 스니펫으로 대체 검사
        check_text = page_text if page_text else (result["title"] + " " + result["body"])
        is_sp, marker = detect_sponsored(check_text, lang)
        candidates.append(SpotCandidate(
            title=result["title"],
            source_url=result["href"],
            snippet=result["body"][:250],
            sponsored=is_sp,
            sponsored_marker=marker,
            query_used=query,
        ))

    # YouTube: 제목만으로 협찬 표기 확인 (WebFetch 불가)
    for result in yt_results:
        title = result.get("title", "")
        is_sp = bool(re.search(r"#[Aa][Dd]|sponsored|スポンサー|협찬|업체제공", title))
        candidates.append(SpotCandidate(
            title=title,
            source_url=result.get("href", ""),
            snippet=result.get("body", "")[:250],
            sponsored=is_sp,
            sponsored_marker="title-keyword" if is_sp else None,
            query_used=query,
        ))

    return candidates


# ---------------------------------------------------------------------------
# 메인 검색 오케스트레이터
# ---------------------------------------------------------------------------
async def discover(
    destination: str,
    country: str,
    place_type: str,
    theme: str = "",
    max_results_per_query: int = 6,
) -> dict:
    config = COUNTRY_CONFIG.get(country.lower())
    if not config:
        supported = ", ".join(COUNTRY_CONFIG.keys())
        return {"error": f"지원하지 않는 국가: '{country}'. 지원: {supported}"}

    lang: str = config["lang"]
    queries: list[str] = config["queries"](destination, place_type)
    exclude_domains: list[str] = config.get("exclude_domains", [])

    print(f"[INFO] {destination}/{place_type} — {len(queries)}개 쿼리 병렬 실행 중...", file=sys.stderr)

    # Semaphore를 이벤트 루프 안에서 생성 (Python 3.9 호환)
    sem = asyncio.Semaphore(3)

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        tasks = [
            search_and_verify(q, lang, exclude_domains, session, max_results_per_query, sem)
            for q in queries
        ]
        all_groups = await asyncio.gather(*tasks)

    all_candidates = [c for group in all_groups for c in group]
    clean = [asdict(c) for c in all_candidates if not c.sponsored]
    blocked = [asdict(c) for c in all_candidates if c.sponsored]

    print(
        f"[INFO] 완료 — 전체 {len(all_candidates)}건 / 합격 {len(clean)}건 / 협찬 배제 {len(blocked)}건",
        file=sys.stderr,
    )

    return {
        "destination": destination,
        "country": country,
        "place_type": place_type,
        "theme": theme,
        "lang": lang,
        "queries_run": queries,
        "candidates": clean,
        "blocked_count": len(blocked),
        "blocked_preview": [{"title": b["title"], "marker": b["sponsored_marker"]} for b in blocked[:5]],
    }


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="myrealtrip-curator 로컬 스팟 병렬 검색기")
    parser.add_argument("--destination", "-d", required=True,
                        help="여행지 현지어 (예: 札幌, Đà Nẵng, Bangkok)")
    parser.add_argument("--destination-kr", default="",
                        help="여행지 한국어 표기 (출력용, 선택)")
    parser.add_argument("--country", "-c", required=True,
                        help=f"국가 코드: {', '.join(COUNTRY_CONFIG.keys())}")
    parser.add_argument("--type", "-t", dest="place_type", required=True,
                        help="장소 유형 현지어 (예: 温泉, quán ăn, อาหาร)")
    parser.add_argument("--theme", default="", help="여행 테마 (선택)")
    parser.add_argument("--max-results", type=int, default=6,
                        help="쿼리당 최대 결과 수 (기본 6)")
    args = parser.parse_args()

    result = asyncio.run(
        discover(
            destination=args.destination,
            country=args.country,
            place_type=args.place_type,
            theme=args.theme,
            max_results_per_query=args.max_results,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
