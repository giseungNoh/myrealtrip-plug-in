# Search Verifier 검증 로그

검증 에이전트(`search-verifier`)가 실제 검색을 수행한 결과를 기록합니다.
새 검증을 실행할 때마다 이 파일에 항목을 추가합니다.

---

## #001 — 삿포로 / 온천 / 관광

- **일시:** 2026-07-02
- **판정:** NEEDS WORK
- **검색 환경 제약:** WebFetch 권한 거부 — 페이지 본문을 직접 열람하지 못해 합격 확정 불가. 도메인·제목·스니펫 기반으로만 분류.

### 소스 합격률

| 구분 | 검사 수 | 합격(확정) | 합격 후보 | 배제 확정 | 판별불가 |
|------|--------|-----------|----------|----------|---------|
| 텍스트 소스 | 26개 | 0개 | 8개(ameblo·hatena) | 17개 | 1개 |
| 유튜브 | 5개 | 0개 | 0개 | 2개 | 3개 |

배제 확정 분류:
- 기성 플랫폼: 10개 (jalan.net, 4travel.jp, rtrp.jp, newt.net, oyutabi.biglobe.ne.jp, asoview.com, yukoyuko.net 등)
- 여행 미디어·상업 사이트: 7개 (northsmile.net, tabimo.012cloud.jp, taxi-kanko.com 등)
- 인플루언서 경계 블로그: 1개 (温泉ソムリエマスター ameblo)
- YouTube 배제: 2개 (ゆっくり解説 형식 1개, 삿포로 관광협회 공식 채널 1개)

### 합격 후보 (본문 미확인 — WebFetch 필요)

| URL | 도메인 기준 판단 근거 |
|-----|----------------------|
| `ameblo.jp/nagippumama/...` | "札幌暮らし50代主婦" 일상 블로그, "ソロ活【つきさむ温泉】" 제목 |
| `ameblo.jp/junya828/...` | 개인 ameblo, ていね温泉ほのか 방문 포스팅 |
| `ameblo.jp/supersenntoutsukimiyu/` | 삿포로 銭湯(센토) 전용 개인 방문 기록 블로그 |
| `sapporo-sento-syosinsya.hatenablog.com/...` | 삿포로 목욕탕을 번호 매겨 순서대로 방문하는 개인 순례 기록 |
| `ameblo.jp/junya828/...` 외 3개 | ameblo 개인 블로그 추정 |

### 유튜브 채널 판정

| 채널/URL | 판정 | 사유 |
|---------|------|------|
| 【超穴場】道民が本当は教えたくない 北海道温泉TOP10 | ❌ 배제 | ゆっくり解説 형식 — 직접 방문 현장 영상 없음 |
| 札幌観光協会公式チャンネル【ようこそさっぽろ】 | ❌ 배제 | 기관 공식 홍보 채널, 개인 서사 없음 |
| @SHINYA_TRAVEL (秘境ハンター) | ❓ 판별불가 | 채널명 영어 포함, 인플루언서급 가능성, 본문 미확인 |
| 【北海道Vlog】札幌観光 | ❓ 판별불가 | 외부 여행자·현지인 여부 불명 |
| 【旅VLOG】癒しを求めて…温泉旅行 | ❓ 판별불가 | 삿포로 구체 여부, 업로더 자국민 여부 불명 |

### 발견된 문제 및 반영 현황

| # | 문제 | 조치 완료 |
|---|------|----------|
| 1 | 일반 키워드 검색 시 기성 플랫폼이 상위 8~9개 독식 | ✅ SKILL.md "소스 선택" 섹션을 site: 한정·배제 도메인 차단 전략으로 재설계 |
| 2 | 배제 도메인이 추상적으로만 명시되어 있었음 | ✅ jalan.net, 4travel.jp, rtrp.jp, newt.net 등 실명 추가 |
| 3 | "N選·ランキング·まとめ" 집계형 제목 걸러내는 기준 없었음 | ✅ 배제 원칙에 제목 패턴 명시 |
| 4 | ゆっくり解説 유튜브가 최상위 노출, 배제 기준 없었음 | ✅ 배제 원칙·유튜브 키워드(-ゆっくり解説 -ランキング) 추가 |
| 5 | WebFetch 없으면 본문 검증 불가 — 스킬에 명시 안 되어 있었음 | ✅ "운영 전제 조건" 섹션 신설 |

### 다음 검증 권장 사항

- WebFetch 권한이 있는 환경에서 재검증 — 합격 후보 8개 본문을 실제로 열어 개인 서사·협찬 여부 확인 필요
- 개선된 검색어(site: 한정, 배제어 포함)로 재검색 후 합격률 재측정
- 베트남·태국 등 다음 대상국으로 검증 확장

---

---

## #002 — 삿포로 / 온천 / 관광 (재검증 — WebFetch 허용, 협찬 필터 강화)

- **일시:** 2026-07-02
- **판정:** PASS (개선 사항 있음)
- **변경 사항:** WebFetch 영구 허용 후 실제 페이지 본문 확인. 개인 서사 여부 판단 제거, 협찬 표기 유무만 판단 기준으로 단순화.

### 검색어별 소스 합격률

| 검색어 | 검사 수 | 합격 | 배제 | 합격률 |
|--------|--------|------|------|--------|
| `site:ameblo.jp 札幌 温泉 体験` | 3 | 2 | 1 | 67% |
| `site:hatenablog.com 札幌 銭湯 OR 温泉` | 2 | 2 | 0 | 100% |
| `site:note.com 札幌 温泉` | 4 | 4 | 0 | 100% |
| 일반 배제어 검색 (`体験記 -site:...`) | 1 | 0 | 1 | 0% |
| YouTube vlog | 2 | 0(판별불가) | 0 | — |

### 합격 소스 및 추출 장소

| # | URL | 언급 장소 |
|---|-----|----------|
| 1 | ameblo.jp/nagippumama | つきさむ温泉 |
| 2 | ameblo.jp/junya828 | ていね温泉ほのか |
| 3 | hatenablog — 銭湯순례 #1 | 奥の湯, さかえ湯, 大正湯 |
| 4 | hatenablog — 銭湯순례 #2 | 円山温泉, 神宮温泉, 福の湯, 琴似温泉, あけぼの湯 |
| 5 | note.com/denchilow | 小金湯温泉, 定山渓 |
| 6 | note.com/solo_onsen | 豊平峡温泉, 丸駒温泉旅館, ながぬま温泉, 森林公園温泉きよら |
| 7 | note.com/ojirowashi_381 | 北のたまゆら 桑園 |
| 8 | note.com/27takashima | 天然温泉あしべ屯田 |

**추출 장소 총 18개** (つきさむ温泉 / ていね温泉ほのか / 奥の湯 / さかえ湯 / 大正湯 / 円山温泉 / 神宮温泉 / 福の湯 / 琴似温泉 / あけぼの湯 / 小金湯温泉 / 豊平峡温泉 / 定山渓温泉 / 丸駒温泉旅館 / 森林公園温泉きよら / ながぬま温泉 / 北のたまゆら桑園 / 天然温泉あしべ屯田)

### 배제 소스

| URL | 사유 |
|-----|------|
| ameblo.jp/mwmhc | 【PR】 표기 + 楽天トラベル 아필리에이트 링크 |
| johnny88.jp | "記事内に広告を表示しています" 명시 + 아필리에이트 복수 링크 |

### 유튜브 채널 판정

| 영상 | 판정 | 사유 |
|------|------|------|
| 定山渓 日帰り温泉 vlog | ❓ 판별불가 | WebFetch가 푸터만 반환, 채널 정보 미확인 |
| Sapporo Vlog 1泊2日 | ❌ 채택 보류 | "JALトラベルレポーター" 문구 → 항공사 협력 콘텐츠 의심 |

### 현지어 리뷰 비율

추정 불가 — 합격 소스 전부 일본어 개인 블로그·note로 확인됐으나, 각 장소 리뷰 플랫폼 접근 안 함.

### 발견된 개선 사항

| # | 문제 | 권장 조치 |
|---|------|----------|
| 1 | 일반 배제어 검색어는 0% 합격 — 아필리에이트 SEO 글이 장악 | 해당 검색어 삭제 또는 URL 패턴 배제 추가 |
| 2 | ameblo에 PR 글 혼재 | `体験記` 대신 `感想 OR 行ってみた OR レポ` 구어체 키워드 사용 |
| 3 | YouTube WebFetch 기술적 한계 (푸터만 반환) | `@channel/about` URL 직접 페치 또는 description에서 `#PR`, `案件` 텍스트 검색으로 전환 |

---

## #003 — 삿포로 / 온천·銭湯 / 구어체 키워드 확장

- **일시:** 2026-07-02
- **판정:** PASS
- **목적:** 기존 `体験記` 키워드 대신 현지인 구어체(`行ってみた`, `レポ`, `地元` 등)로 바운더리 확장. YouTube는 WebFetch 없이 WebSearch 제목·채널명만 확인.

### 검색어별 합격률

| 검색어 | 합격 | 배제 | 합격률 | 평가 |
|--------|------|------|--------|------|
| ameblo 温泉 行ってみた | 4 | 1 | 80% | ★★☆ 우수 |
| ameblo 温泉 レポ | — | — | — | Q1 중복 |
| ameblo 温泉 リピ確定 | — | — | — | Q1 중복 |
| ameblo 銭湯 通ってる OR 近所 | 0 | 3 | 0% | ✗ 삿포로 결과 없음 |
| hatenablog 温泉 感想 | 1 | 1 | 50% | ★☆☆ 보통 |
| hatenablog 銭湯 行った | 3 | 1 | 75% | ★★☆ 우수 |
| note 温泉 ひとりで | 3 | 0 | 100% | ★★★ 최우수 |
| note 銭湯 地元 | 5 | 0 | 100% | ★★★ 최우수 |
| YouTube 温泉 穴場 vlog -ゆっくり解説 | 참고 가능 5개 | — | — | 제목 전부 일본어 |
| YouTube 銭湯 地元 行ってみた | 0(뉴스 점유) | — | — | ✗ 銭湯 화재 뉴스가 상위 독식 |

### 합격 소스 (16건) 및 추출 장소

**ameblo (4건)**
- nagippumama → つきさむ温泉
- junya828 → ていね温泉ほのか
- y-konatsu → 豊平峡温泉
- noguri-tukiyo → 定山渓ビューホテル

**hatenablog (4건 — 삿포로 銭湯 전문 블로그 재확인)**
- sapporo-sento-syosinsya #1 → 奥の湯, 大正湯, さかえ湯
- sapporo-sento-syosinsya #2 → さかえ湯
- sapporo-sento-syosinsya #3 → 円山温泉, 神宮温泉, 福の湯
- mariee.hatenablog → ホテルモントレエーデルホフ札幌(カルロビ・バリ・スパ)

**note (8건)**
- solo_onsen → 豊平峡温泉, 定山渓, 小金湯温泉, 丸駒温泉旅館, 森林公園温泉きよら, ながぬま温泉
- ojirowashi_381 → 北のたまゆら 東苗穂, 北のたまゆら 桑園
- ayunosukeeeee → 望月湯
- motoonote → 円山温泉
- repple → 湯処花ゆづき
- mzbr_boyslife → 喜楽湯
- mizuburoinochi → 美春湯, 月見湯
- hases → ぬくもりの宿ふる川, 定山渓第一寶亭留 외

### 배제 소스 (4건)

| URL | 사유 |
|-----|------|
| ameblo.jp/mwmhc | 楽天トラベル 아필리에이트 PR 링크 |
| naoha.hatenablog | "広告が表示されています" + ValueCommerce·楽天 배너 |
| sapporocco.hatenablog | 福祉事業所「晴ればれ」PR 표기 |
| 기타 가이드형 ameblo | 스니펫 기준 큐레이션 형식 |

### YouTube (WebSearch 기준)

- Q9 `温泉 穴場 vlog`: 제목 전부 일본어, 개인 vlog 형식 1개 포함 — 참고 가능
- Q10 `銭湯 地元 行ってみた`: 삿포로 銭湯 화재 뉴스가 상위 독식 — vlog 발굴 효과 없음

### 총 발굴 장소 (신규 포함)

23개 이상 — 銭湯 계열(さかえ湯, 奥の湯, 大正湯, 円山温泉, 神宮温泉, 福の湯, 喜楽湯, 望月湯, 湯処花ゆづき, 美春湯, 月見湯, 北のたまゆら×2) + 온천(つきさむ, ていね温泉ほのか, 豊平峡, 小金湯, 丸駒温泉旅館, 森林公園温泉きよら, ながぬま, 定山渓 계열)

### 검색어 개선 사항 (SKILL.md 반영 예정)

| 검색어 | 조치 |
|--------|------|
| ameblo `通ってる OR 近所` | 삭제 — OR 연산자 미작동, 삿포로 결과 0개 |
| ameblo `レポ`, `リピ確定` | 삭제 — `行ってみた`와 결과 완전 중복 |
| YouTube `銭湯 地元 行ってみた` | 삭제 — 뉴스가 상위 점유, vlog 발굴 불가 |
| **note `銭湯 地元`** | ★ 유지 — 100% 합격, 최우수 키워드 |
| **note `温泉 ひとりで`** | ★ 유지 — 100% 합격, 솔로 이주자 관점 강점 |
| **ameblo `温泉 行ってみた`** | ★ 유지 — 80% 합격, 구어체 효과 확인 |

<!-- 다음 검증 결과는 아래에 같은 형식으로 추가 -->

---

## #004 — 대만 타이페이 / 맛집 / 로컬 (병렬 에이전트 검증)

- **일시:** 2026-07-02
- **판정:** PASS (조건부 개선 권장)

### 검색어별 합격률

| 검색어 | 합격률 | 비고 |
|--------|--------|------|
| `site:pixnet.net 台北 隱藏版 美食 在地人` | ~70% | 개인 블로거 fancy6517 완전 합격 |
| `site:ptt.cc 台北 美食 推薦 在地` | 확인분 100% | 커뮤니티 일반 유저 작성 |
| `台北 隱藏版美食 "在地人" OR "私房" 部落格 2024` | ~30% | 집계/여행사 오염율 높음 |
| `site:youtube.com 台北隱藏版美食 -業配` | ~56% | 중국어 채널 5개 확보 |

### 합격 소스 및 추출 장소

- **fancy6517.pixnet.net** (協찬 없음): 阿財虱目魚肚, 稻香石磨腸粉, 國都甜不辣, 廣興無名臭豆腐, 龍抄手涼麵
- **PTT Food/WomenTalk**: 파인다이닝~로컬 단골 관점 다수
- **YouTube**: 觀光客幾乎沒有 (小巨蛋), 後車站華陰街必吃7家, 大稻埕隱藏美食 등 5개 채널 합격

### 배제 소스

| 소스 | 배제 이유 |
|------|---------|
| klook.com/zh-TW/blog | OTA 자사 홍보 |
| walkerland.com.tw | 집계 플랫폼 |
| cw.com.tw | 주류 미디어 |
| nixojov.pixnet.net | 블로그 프로필에 "邀稿歡迎洽詢" 명시 → 포스트별 협찬 여부 재확인 필요 |
| 阿星探店 YouTube 채널 | 중국 본토 기반 추정, 대만 로컬 아님 |

### 개선 제안

- 검색어 3은 `site:` 한정 필터 없이 일반 검색 → 집계 오염율 70%. `site:pixnet.net` 또는 `site:ptt.cc` 로 교체
- PTT는 `WomenTalk` 외 `Gossiping` / `Taiwan` 판도 추가
- `-業配` 필터 후에도 YouTube 설명란 협찬 재확인 권장

---

## #005 — 태국 방콕 / 맛집 / 로컬 (병렬 에이전트 검증)

- **일시:** 2026-07-02
- **판정:** NEEDS WORK (Pantip 우수, 개인 블로그 전무)

### 검색어별 합격률

| 검색어 | 합격률 | 비고 |
|--------|--------|------|
| `site:pantip.com กรุงเทพ ร้านอาหาร รีวิว ซ่อนเร้น` | **100%** | 협찬 표기 전무, 커뮤니티 일반 유저 |
| `กรุงเทพ "คนท้องถิ่น" OR "ไม่ค่อยมีคนรู้จัก" บล็อกส่วนตัว 2024` | **10%** | 개인 블로그 0건, 미디어·기업만 반환 |
| `site:youtube.com ร้านอาหารซ่อนเร้น กรุงเทพ รีวิวจริง -สปอนเซอร์` | **70%** | 태국어 채널 5개 확보 |

### 합격 소스 및 추출 장소

- **Pantip topic/36937705** (saturdaysisters): 20개 방콕 로컬 식당 목록
- **Pantip topic/41193973** (ธาราสินธุ์): ครัวบางนา, ฟาร์มมู, บ้านไอซ์ 등
- **YouTube**: เกี้ยแซ่บบ, ตะลอน ON ตลาด, อร่อย 100 เดียว 등 태국어 로컬 채널 5개

### 배제 소스

| 소스 | 배제 이유 |
|------|---------|
| thestandard.co | "Robinhood x THE STANDARD LIFE" 협찬 명시 |
| ryoiireview.com | "SPONSORED" 표기 |
| krungsriconsumer.com | 은행 브랜드 콘텐츠 + 신용카드 연동 |
| hungryhub.com | 집계 플랫폼 |

### 개선 제안

1. 개인 블로그 검색어 → `site:medium.com OR site:bloggang.com กรุงเทพ ร้านอาหาร ซ่อนเร้น` 로 교체
2. 집계 명시 배제 `-hungryhub -wongnai -soimilk -tripadvisor` 추가
3. YouTube 지역 필터: `"กรุงเทพ" OR "กทม"` 명시로 타 지역 유입 차단

---

## #006 — 베트남 다낭 / 맛집 / 로컬 (병렬 에이전트 검증)

- **일시:** 2026-07-02
- **판정:** NEEDS WORK (Foody 개인 리뷰 합격, 개인 블로그 전무)

### 검색어별 합격률

| 검색어 | 합격률 | 비고 |
|--------|--------|------|
| `site:facebook.com "Đà Nẵng" "quán ăn" nhóm địa phương` | 판별불가 | Facebook 로그인 없이 WebFetch 접근 불가 |
| `Đà Nẵng quán ăn ngon ít người biết blog cá nhân 2024` | **0%** | 개인 블로그 0건, 전부 상업 플랫폼 |
| `site:foody.vn Đà Nẵng review chi tiết` | **100%** | `/bai-viet/` 경로 개인 리뷰 협찬 없음 |
| `site:youtube.com Đà Nẵng quán ăn ngon ít biết review thật` | 베트남어 10/10 | "ít người biết" 제목 영상 0건 |

### 합격 소스 및 추출 장소

- **Foody.vn/bai-viet/** (T Y, Tim Le 등): 다낭 3일 800k 루트, 17곳 로컬 식당, 길거리 음식 多
- **foody.vn/da-nang/an-vat-via-he**: Bánh Tráng Kẹp Dì Hoa, Ăn Vặt Cô Liên 등

### 배제 소스

klook.com, ivivu.com, bazantravel.com, vinpearl.com, tourism.danang.vn 등 전부 상업 플랫폼

### 개선 제안

1. 개인 블로그: `site:blogspot.com Đà Nẵng quán ăn ngon` 또는 `site:wordpress.com Đà Nẵng ẩm thực` 로 교체
2. Foody.vn은 집계 점수 페이지(`/da-nang/quan-an`)는 배제, `/bai-viet/` 경로 개인 후기만 채택
3. Facebook 그룹: WebFetch 불가, Google 캐시 경유 또는 수동 확인 필요

---

## #007 — 프랑스 파리 / 카페·식당 / 로컬 (병렬 에이전트 검증)

- **일시:** 2026-07-02
- **판정:** NEEDS WORK (Over-Blog 부분 합격, Routard 포럼 접근 불가)

### 검색어별 합격률

| 검색어 | 합격률 | 비고 |
|--------|--------|------|
| `site:routard.com/forum Paris café restaurant "endroit caché"` | **판별불가** | HTTP 403 전 URL 차단 |
| `site:over-blog.com Paris restaurant "découvert" OR "coup de coeur" local 2024` | 50~67% | 2014~2018 구작 많음 |
| `Paris café "les locaux" blog personnel 2024 -tripadvisor` | 20~40% | 비개인 미디어 다수 |
| `site:youtube.com Paris restaurant caché habitants vlog -sponsorisé` | 40~50% | YouTube 설명란 협찬 미확인 |

### 합격 소스 및 추출 장소

- **emilieaparis.over-blog.com** (개인 블로거 Lily): Restaurant Nouilles Fraîches (15구), Restaurant Ensuite (1구)
- **monpetit20e.com** (독립 동네 저널): Candle kids coffee, Restaurant La Colline, Jolie Môme 등 8곳 (20구)
- **YouTube 조건부**: "La bonne adresse parisienne", "NOS RESTAURANTS PRÉFÉRÉS" 등 3건 (설명란 미확인)

### 배제 소스

| 소스 | 배제 이유 |
|------|---------|
| PVAM YouTube | Paris Vous Aime Magazine, 편집 매거진 채널 |
| relations-publiques.pro | 홍보 에이전시 사이트 |
| paris.fr | 파리시 공식 |

### 개선 제안

1. **Routard 우회**: Google Cache (`cache:routard.com/forum_message/...`) 또는 Wayback Machine 경유
2. **Over-Blog 신규 글**: `"j'ai testé" OR "j'y suis allée" OR "notre adresse"` + `2024 OR 2025` 날짜 조건
3. **YouTube 협찬 확인**: 설명란 `#ad`, `#sponsorisé`, `#partenariat` 해시태그 수동 확인 필요

---

## #008 — 미국 뉴욕 / 맛집 / 로컬 (재검증)

- **일시:** 2026-07-02
- **판정:** NEEDS WORK (Reddit 크롤러 차단, 개인 블로그 18%)

### 검색어별 합격률

| 검색어 | 합격률 | 비고 |
|--------|--------|------|
| `site:reddit.com/r/nyc "hidden gem" restaurant 2024` | **0% (N/A)** | reddit.com HTTP 403 — 크롤러 완전 차단 |
| `site:reddit.com/r/FoodNYC underrated restaurant 2024` | **0% (N/A)** | 동일 |
| `NYC "neighborhood spot" OR "hidden gem" restaurant personal blog 2024 -yelp -tripadvisor -eater` | **18%** | 11건 중 2건 합격 |
| `site:youtube.com NYC hidden gem restaurant locals vlog -sponsored` | 44% 채널 확인 | 9건 중 4건 채널명 확인 |

### 합격 소스 및 추출 장소

- **thewinechef.com** (Lisa Denning 개인 블로그, 협찬 없음): Jungsik, Frevo, Thai Diner, Laser Wolf(Brooklyn), Pinch Chinese, Cosme 등 22곳 (파인다이닝 편향)
- **eatthisny.com** (익명 NYC 탐방 블로그, 협찬 없음): TBD Gimbap, Quique Crudo, Traze Pizza, Los Burritos Juárez, House of Joy, Chubby Skewers, Diljān Bakery, Falafel Plant

### 배제 소스

| 소스 | 배제 이유 |
|------|---------|
| resy.com/blog | 레스토랑 예약 집계 플랫폼 블로그 |
| joinmytrip.com | 그룹 여행 플랫폼 콘텐츠 |
| nimbuskitchen.com | 주방 렌탈 기업 블로그 |
| tastingtable.com | 미디어 집계 사이트 |
| browneyedflowerchild.com | Affiliate 링크 공시 (경계선) |

### YouTube

- Adam Glyn (개인 채널): "5 Manhattan Hidden Gems: A Local's NYC Food Guide" — 합격
- Kaitlyn Rosati (개인 채널): "New York City's hidden restaurant gems" — 합격
- @HereBeBarr / Jon Barr: 10년 NYC 거주, 구독자 40만+ → 후속 협찬 확인 필요

### 핵심 이슈 및 개선

| 이슈 | 해결 방법 |
|------|---------|
| reddit.com 크롤러 완전 차단 | `NYC hidden gem restaurant reddit 2024` 우회 검색으로 대체 |
| 개인 블로그 18% 정확도 | `site:substack.com`, `site:wordpress.com`, `site:blogspot.com` 도메인 한정 추가 |
| YouTube 채널명 44% 미확인 | 영상 제목에 채널명 포함된 검색 스니펫 우선 활용 |

---

## #009 — spot_searcher.py 성능 테스트 (삿포로 / 온천)

- **일시:** 2026-07-02
- **방식:** Python 병렬 검색 스크립트 (`src/tools/spot_searcher.py`)

### 성능 비교

| 방식 | 소요 시간 | 결과 수 | 비고 |
|------|----------|--------|------|
| LLM 순차 WebSearch | 2~5분 | ~20건 | 각 쿼리 순차 실행 |
| spot_searcher.py | **~5~12초** | 17~29건 | asyncio 병렬 |

**속도 향상: 약 10~30배**

### 합격 소스 샘플 (17건)

- `sapporo-sento-syosinsya.hatenablog.com` — 삿포로 銭湯 전문 순례 블로그
- `note.com/kourichill` — 湯屋・サーモン (地元 사우나)
- `note.com/ono3log` — 北海道民 7년 거주자 추천 日帰り温泉
- `ameblo.jp/catmimi53` — 근처 온천 방문기
- `yukko-de-memo.hatenablog.com` — 정산계 온천 개인 여행기

### 주요 이슈 및 해결

| 이슈 | 해결 방법 |
|------|---------|
| DDG 병렬 TLS 충돌 | `asyncio.Semaphore(3)` + `asyncio.to_thread` |
| site: 필터 미준수 결과 혼입 | `url_matches_site()` 도메인 검증 추가 |
| bing.com/aclick 광고 URL 유입 | `_ALWAYS_EXCLUDED` 리스트에 추가 |
| 일본어 "PR" 과잉 차단 | 명시적 협찬 형태(`【PR】`, `#PR`, `PR記事` 등)로 패턴 축소 |
