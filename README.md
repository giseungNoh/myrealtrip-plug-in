# 마이리얼트립 여행 큐레이터 (myrealtrip-curator)

기성 리뷰 플랫폼·인플루언서가 아니라, **지극히 개인적인 여행자의 "특별했던 경험"이 묻어나는 글**에서
숨은 명소·맛집을 발굴해 장바구니에 담고, 일정표나 구글 캘린더로 만들고, 그 위에 마이리얼트립 실제
상품을 추천해 연결하는 Codex 플러그인입니다.

## 전체 흐름

5개의 스킬이 파이프라인처럼 이어집니다. 사용자는 스킬 이름을 몰라도 자연어로 요청하면 되고,
**각 단계가 끝나면 플러그인이 먼저 다음 단계를 제안**합니다 — 사용자가 "다음엔 뭘 해야 하지?"를
매번 기억할 필요가 없도록 설계했습니다.

```
discover-local-spots        (여행지·장소유형·테마를 묻고, 개인 여행기에서 숨은 후보 발굴, 마이리얼트립 무관)
        │  "장바구니에 담을 번호를 골라주세요" → 사용자가 번호로 선택
        ▼
manage-travel-cart           (선택한 장소를 로컬 JSON 장바구니에 저장, 마이리얼트립 무관)
        │  "더 담으실 곳 있으세요? 다 담으셨으면 일정표 짜드릴까요?"
        ▼
build-itinerary               (Day별로 배치, 숙소·액티비티 포함 일정표를 Google Sheets로 생성)
        │                                  │
        │ "구글 캘린더에도 등록해드릴까요?"    │ 숙소·액티비티 슬롯
        ▼                                  ▼
sync-google-calendar     recommend-mrt-products  ← 여기서만 마이리얼트립 MCP 호출
   (구글 캘린더 커넥터 사용)      (mcp-servers.myrealtrip.com/mcp)
```

핵심 설계 원칙: **마이리얼트립 MCP는 마지막 상품 추천 한 지점에서만 사용합니다.**
장소 발굴, 장바구니, 일정 조립, 캘린더 등록은 플러그인이 새로 만드는 기능이며 마이리얼트립 앱에
지금 없는 기능이어도 동작합니다.

### 실사용 예시 (처음부터 끝까지)

1. **사용자**: "삿포로 온천 로컬 스팟 찾아줘"
   → `discover-local-spots`가 개인 블로그·현지 유튜버 글에서 후보 6~8개를 **현지어 리뷰 비율**과 함께 제시
2. **사용자**: "1번, 3번 담아줘"
   → `manage-travel-cart`가 장바구니(JSON)에 저장하고, 곧바로 *"다 담으셨으면 일정표 짜드릴까요?"*라고 되물음
3. **사용자**: "응, 3일 일정으로"
   → `build-itinerary`가 (숙소가 미정이면) `recommend-mrt-products`로 인근 숙소부터 추천 →
     장소들을 동네 단위로 묶어 Day별 동선을 짜고 여백 슬롯을 넣어 **Google Sheets**로 생성·공유,
     끝에 *"구글 캘린더에도 등록해드릴까요?"*라고 되물음
4. **사용자**: "응, 등록해줘"
   → `sync-google-calendar`가 실제 캘린더 이벤트로 등록

각 스킬은 이 순서를 몰라도 단독으로도 호출할 수 있습니다 (예: 이미 채워둔 장바구니로 바로
"일정 짜줘"만 요청하면 1~2단계를 건너뛰고 바로 시작합니다).

## 발굴 철학 — 무엇을 소스로 쓰고, 무엇을 배제하는가

이 플러그인의 차별점은 "어디서 찾느냐"에 있습니다. 관광객 쏠림을 재생산하는 소스는 의도적으로 피합니다.

**배제하는 소스**
- Tabelog·대중점평(Dianping) 등 **기성 집계 리뷰 플랫폼** — 상위 노출이 곧 붐빔·관광객화
- **인플루언서, 너무 유명한 블로거, 협찬성 글**

**채택하는 소스**
- 지극히 **개인적인 여행자의 "특별했던 경험"이 묻어나는 글** (개인 블로그·커뮤니티 글)에서
  언급된 명소·맛집. 목적은 **숨은 보석(hidden gem) 발굴**.
- 각 나라에서 **현지인이 실제로 많이 쓰는 검색 사이트·커뮤니티**를 경유해 수집.

**입력 흐름 (`discover-local-spots`가 먼저 묻는 것)**
1. 여행지가 어디인가 (예: 삿포로, 다낭)
2. 가고 싶은 장소 유형 (예: 온천, 스키장)
3. 이번 여행의 테마 (예: 관광, 먹방, 기타(guitar) 구매)

→ 답변에 맞춰 해당 국가에서 주로 쓰는 웹 검색 사이트·커뮤니티를 골라 개인 여행기를 탐색합니다.

**관광객 필터 (핵심 기능)**
- 후보 장소마다 **"현지어 리뷰 비율"** 등의 신호로 관광객 쏠림을 자동 감지합니다.
- 사용자에게 결과를 보여줄 때 **"현지어 리뷰 비율 약 N%"**를 함께 표기해, 얼마나 로컬한 곳인지
  한눈에 판단하게 합니다. (예: `⛩ ○○온천 — 현지어 리뷰 비율 약 82%`)

**커버 우선순위**
- 한국인이 많이 가는 해외 여행지 순으로 커버리지를 넓혀갑니다.
  (예: 일본 → 베트남 → 태국 → … 실제 순위는 최신 통계로 확정 예정)

## 폴더 구조

```
src/
├── .codex-plugin/plugin.json     필수 매니페스트
├── .mcp.json                     마이리얼트립 공식 MCP 등록 (mcp-servers.myrealtrip.com/mcp)
└── skills/
    ├── discover-local-spots/SKILL.md
    ├── manage-travel-cart/SKILL.md
    ├── build-itinerary/SKILL.md
    ├── sync-google-calendar/SKILL.md
    └── recommend-mrt-products/SKILL.md
logs/                              개발 중 AI 대화 로그 (훅으로 자동 저장, 편집 금지)
```
## 출처

- 마이리얼트립 공식 MCP 서버: `https://mcp-servers.myrealtrip.com/mcp`
- 마이리얼트립 해커톤에서의 API/MCP 활용 사례: https://about.myrealtrip.com/stories
- 마이리얼트립 마케팅 파트너 프로그램(수익 50% 배분) 및 가입자·GMV 규모: https://namu.wiki/w/마이리얼트립

### 수요 근거 통계 (Q1 서술 근거)

- 25,000명 설문(91% 계획+유연, 97% 자유시간, 61% 현지인처럼): https://www.travelresearchonline.com/blog/index.php/2026/03/new-survey-of-25000-north-america-travelers-signals-a-shift-back-to-designed-flexible-travel/
- 90% "현지인처럼", 62% 문화 경험 못 하면 낭비: https://www.travelagentcentral.com/your-business/survey-travelers-want-experience-destinations-locals-crave-more-authenticity
- 2026 글로벌 트렌드(87% 발견 여백, 진정성 수요): https://www.americanexpress.com/en-us/travel/discover/get-inspired/global-travel-trends
- 한국 자유여행 vs 패키지 설문(패키지 13.9%, 정해진 일정 불편 48.9%): https://www.traveltimes.co.kr/news/articleView.html?idxno=110076
- 일본 현지인은 Tabelog, 구글 리뷰는 관광객 편향(관광객 필터 필요성 근거): https://www.planetware.com/2098812/tabelog-app-japan-find-top-restaurants-ditch-google-reviews/

