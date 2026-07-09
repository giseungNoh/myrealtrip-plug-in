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
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, asdict
from typing import Optional

import os

# DDG 검색 백엔드(primp/reqwest)가 시스템 프록시 설정을 조회하다 SIGABRT로 죽는
# 경우가 있다 (macOS, 메인 스레드에서도 발생해 프로세스 격리만으로는 완전히
# 막지 못한다). env 프록시를 명시해 시스템 조회 자체를 최대한 우회한다.
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

import aiohttp
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
        # 베트남어 협찬 표기 — 명시적 형태만 잡는다 ("quảng cáo", "tài trợ" 단독 단어는 제외:
        # 학자금 후원·일반 광고 배너 등 무관한 맥락에서도 흔히 등장해 오탐이 많다)
        r"được tài trợ bởi|bài (viết|đăng) (có |được )?tài trợ|nội dung (được )?tài trợ"
        r"|#quảng ?cáo\b|#ad\b|#sponsored\b|hợp tác (thương mại )?trả phí",
        re.IGNORECASE,
    ),
    "th": re.compile(
        # 태국어 협찬 표기 — 명시적 문장/해시태그만 잡는다 ("โฆษณา", "ร่วมกับ" 단독은 제외:
        # 너무 일반적인 단어라 무관한 페이지에서도 흔히 매치된다)
        r"บทความนี้ได้รับการสนับสนุน|ได้รับการสนับสนุนจาก|รีวิวนี้ได้รับสปอนเซอร์"
        r"|ได้รับสินค้ามารีวิว|#โฆษณา|#สปอนเซอร์",
        re.IGNORECASE,
    ),
    "zh": re.compile(
        # 중국어(번체) 협찬 표기 — 명시적 형태만 잡는다 ("廣告", "合作", "受邀", "試用" 단독은 제외:
        # 너무 일반적인 단어라 무관한 글에서도 흔히 매치된다)
        r"業配文?|置入性行銷|邀稿邀約|試吃邀約|收到(廠商|品牌)邀約"
        r"|本文由.{0,10}贊助|贊助商提供|#業配|#廣告合作",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        # 프랑스어 협찬 표기 — 명시적 형태만 잡는다 ("partenariat", "publicité" 단독은 제외:
        # 무보수 협업·일반 광고 언급과 구분이 안 돼 오탐이 많다)
        r"article sponsorisé|billet sponsorisé|en partenariat rémunéré avec"
        r"|collaboration rémunérée|publi-?reportage|#sponsorisé\b|#partenariat\b",
        re.IGNORECASE,
    ),
    "it": re.compile(
        # 이탈리아어 협찬 표기 — 명시적 형태만 잡는다 ("in collaborazione con", "pubblicità" 단독은 제외:
        # 무보수 협업·일반 광고 언급과 구분이 안 돼 오탐이 많다)
        r"articolo sponsorizzato|post sponsorizzato|collaborazione (retribuita|a pagamento)"
        r"|pubbliredazionale|#sponsorizzato\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        # 영어 협찬 표기 — 명시적 형태만 잡는다 ("gifted", "in collaboration with" 단독은 제외:
        # 일상적 의미로도 쓰여 오탐이 많다)
        r"\bsponsored post\b|\bpaid partnership\b|\bin paid collaboration with\b"
        r"|\b#ad\b|\b#sponsored\b|\bthis (post|article) (is|was) sponsored\b"
        r"|\bpr (gift|sample) received\b",
        re.IGNORECASE,
    ),
    "de": re.compile(
        # 독일어 협찬 표기 — 명시적 형태만 잡는다 ("werbung", "anzeige", "kooperation" 단독은 제외:
        # 메뉴명·일반 광고 배너 등에도 흔히 등장해 오탐이 많다)
        r"gesponserter (beitrag|artikel|post)|bezahlte (kooperation|partnerschaft)"
        r"|unbezahlte werbung|#werbung\b|#anzeige\b",
        re.IGNORECASE,
    ),
    "es": re.compile(
        # 스페인어 협찬 표기 — 명시적 형태만 잡는다 ("publicidad", "en colaboración con" 단독은 제외:
        # 무보수 협업·일반 광고 언급과 구분이 안 돼 오탐이 많다)
        r"artículo patrocinado|publirreportaje|colaboración (pagada|remunerada)"
        r"|#patrocinado\b|#publicidad\b",
        re.IGNORECASE,
    ),
    "ko": re.compile(
        # 한국어 협찬 표기 — 명시적 형태만 잡는다 ("광고", "제공", "대가", "무상", "지원받" 단독은 제외:
        # "정보 제공", "무상 임대" 등 무관한 맥락에서도 흔히 등장해 오탐이 많다)
        r"\[협찬\]|\(협찬\)|#협찬|#광고|협찬(을|받아서|받았습니다|받은)\b"
        r"|제공받아\s?작성|유료광고\s?포함|이 (글|포스팅)은 (업체|브랜드)(로부터|에서)?\s?(협찬|지원)을?\s?받아",
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
    "switzerland": {
        "lang": "de",
        "queries": lambda d, t: [
            # 독일어권(루체른·취리히 등) 개인 블로그·포럼 우선
            f'{d} {t} Geheimtipp Einheimische persönlicher Blog',
            f"site:blogspot.com {d} {t} Geheimtipp",
            f"site:reddit.com/r/switzerland {d} {t} Geheimtipp locals",
            # 프랑스어권(제네바·로잔 등) 대비 — 관광 공식 사이트 배제 강화
            f'{d} {t} "adresse secrète" OR "coup de coeur" blog personnel -tripadvisor',
        ],
        "exclude_domains": [
            "tripadvisor", "myswitzerland.com", "luzern.com", "myluzern.com",
            "switzerland.com", "getyourguide.com", "viator.com", "booking.com",
            "wikipedia.org", "switzerlanding.com", "planetware.com", "lonelyplanet.com",
            "thefork.com", "tour-switzerland.ch",
        ],
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
FETCH_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=4)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
FETCH_MAX_BYTES = 25000

# JS 렌더링 필요하거나 접근 제한된 도메인 — fetch 자체를 스킵
_SKIP_FETCH_DOMAINS = [
    "maps.google.com", "google.com/maps", "google.com/search",
    "maps.app.goo.gl", "goo.gl",          # 구글맵 단축 링크 (접근 제한)
    "youtube.com", "youtu.be",
    "instagram.com", "facebook.com", "twitter.com", "x.com", "t.co",
    "tiktok.com",
]


async def fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    """페이지 앞 25000바이트 가져온다 (협찬 표기 + 본문 일부 포함 범위)."""
    if any(skip in url for skip in _SKIP_FETCH_DOMAINS):
        return ""
    try:
        async with session.get(url, timeout=FETCH_TIMEOUT, allow_redirects=True) as resp:
            if resp.status == 200:
                raw = await resp.read()
                text = raw[:FETCH_MAX_BYTES].decode("utf-8", errors="ignore")
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
    """
    별도 프로세스(ProcessPoolExecutor)에서 실행되는 동기 DDG 검색.

    스레드 풀(asyncio.to_thread)에서 실행하면 안 된다: DDGS가 쓰는 HTTP
    백엔드(primp/reqwest)가 시스템 프록시 설정을 조회할 때 macOS의
    SystemConfiguration 프레임워크를 호출하는데, 이 프레임워크는 메인
    스레드가 아닌 곳에서 호출되면 인터프리터 전체가 죽는 네이티브
    크래시(세그폴트/abort)를 일으킨다 — Python 자체의 _scproxy 모듈도
    동일한 제약이 있는 것으로 알려진 macOS 고유 문제다. try/except로
    잡을 수 없는 크래시이므로, 각 프로세스가 자신의 메인 스레드를 갖도록
    프로세스 단위로 격리해서 실행한다.

    macOS 첫 실행 시 네트워크 권한 다이얼로그로 TLS 오류가 날 수 있어
    최대 2회 재시도한다 (duckduckgo 백엔드를 제외해도 남는 일반적인 네트워크
    오류에 대한 방어 — 자세한 원인은 위 `_DDGS_BACKENDS` 주석 참고).

    ddgs가 콤마로 묶인 여러 백엔드를 조회할 때 동시 조회 엔진 수를
    min(엔진수, ceil(max_results/10)+1)로 제한하는 문제가 있어, 우리가 쓰는
    6개 백엔드를 전부 실제로 조회시키려면 max_results=60 이상을 요청해야
    한다. 실제로 쓸 결과 개수(max_results)는 그 다음에 잘라낸다.
    """
    import time
    fetch_count = max(max_results, 60)
    last_exc: Exception = RuntimeError("DDG search not attempted")
    for attempt in range(3):
        try:
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=fetch_count, backend=_DDGS_BACKENDS))
            return results[:max_results]
        except Exception as e:
            last_exc = e
            if attempt < 2:
                time.sleep(1.5)  # macOS 네트워크 허용 대기 후 재시도
    print(f"[WARN] DDG 검색 3회 실패: {last_exc}", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# 검색 + 검증 (쿼리 1개)
# ---------------------------------------------------------------------------
async def search_and_verify(
    query: str,
    lang: str,
    exclude_domains: list[str],
    session: aiohttp.ClientSession,
    executor: ProcessPoolExecutor,
    max_results: int = 6,
) -> list[SpotCandidate]:
    loop = asyncio.get_running_loop()

    async def _do_search():
        return await loop.run_in_executor(executor, _ddgs_search_sync, query, max_results)

    try:
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

    # DDG 검색은 프로세스 풀에서 실행한다 (스레드 풀 사용 시 macOS에서
    # 네이티브 크래시 발생 — _ddgs_search_sync 문서 참고).
    # spawn 컨텍스트를 명시해 macOS의 fork() 안전성 문제(Objective-C
    # 런타임이 fork 이후 다른 스레드에서 초기화 중이던 경우 크래시)도
    # 함께 피한다. Windows는 원래 spawn만 지원하므로 동일하게 안전하다.
    mp_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=3, mp_context=mp_context) as executor:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            tasks = [
                search_and_verify(q, lang, exclude_domains, session, executor, max_results_per_query)
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
