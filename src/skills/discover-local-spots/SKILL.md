---
name: discover-local-spots
description: 여행지·장소 유형·테마를 물어본 뒤, 기성 리뷰 플랫폼·인플루언서가 아니라 지극히 개인적인 여행자의 "특별했던 경험" 글에서 숨은 명소·맛집 후보를 발굴해 제시한다. 각 후보에 현지어 리뷰 비율을 함께 표기한다. "삿포로 온천 찾아줘", "다낭 먹방 스팟 알려줘" 같은 요청에 사용한다.
---

# 목적

사용자가 여행지의 장소를 물으면, **관광객 쏠림을 재생산하는 소스는 배제**하고
**지극히 개인적인 여행자의 "특별했던 경험"이 묻어나는 글**에서 언급된 숨은 명소·맛집을 우선 찾는다.

이 스킬은 "여러 사람이 같은 곳을 추천해서 갔더니 관광객만 있더라"는 문제를 해결하기 위한 것이다.
목적은 **숨은 보석(hidden gem) 발굴**이다.

# 소스 원칙 (가장 중요)

**배제한다**
- Tabelog·대중점평(Dianping)·트립어드바이저 등 **기성 집계 리뷰 플랫폼** — 상위 노출 = 붐빔·관광객화.
  일본 추가 배제 도메인(검증으로 확인): `jalan.net`, `4travel.jp`, `rtrp.jp`, `newt.net`,
  `oyutabi.biglobe.ne.jp`, `asoview.com`, `yukoyuko.net`
- **인플루언서, 팔로워 많은 유명 블로거, 협찬·광고성 글** — 문구가 정형화되어 있거나 제휴 링크·
  "협찬받았습니다" 고지가 있으면 배제한다.
- 여러 글에서 **거의 동일한 문구로 반복**되는 곳 — 복붙·바이럴 신호이므로 배제하거나 하단으로 내린다.
- 제목에 **"N選", "ランキング", "永久保存版", "まとめ"** 등 집계형 문구가 있는 글.
- YouTube의 **ゆっくり解説(유쿠리 카이세츠) 형식** — 합성음성+텍스트 애니메이션 구성으로 직접 방문한
  현장 영상이 없다. 형식 자체로 배제한다.

**채택한다**
- 개인 블로그·커뮤니티 글 중, **직접 다녀온 개인적 서사**(그날의 감정·우연히 발견한 경위·현지인과의
  사소한 에피소드 등)가 담긴 글에서 언급된 장소.
- 각 나라에서 **현지인/개인 여행자가 실제로 많이 쓰는 검색 사이트·커뮤니티**를 경유해 발굴한다.
- **현지 자국민 유튜버의 YouTube 영상** — 단, 아래 조건을 모두 충족해야 한다:
  - 채널이 여행지 **자국어**로 운영되고, 댓글도 자국어가 대다수인 채널.
  - 방문자(한국인 등 외국인)가 올린 "해외 여행기" 영상이 아니라, **현지인이 자기 도시·지역을
    소개하는 영상**이어야 한다 (예: 일본인이 삿포로 로컬 온천을 소개하는 영상 ✅,
    한국 여행 유튜버가 삿포로 온천 방문기를 올린 영상 ❌).
  - 영상에서 **직접 방문해 찍은 현장 영상**이 있고, 개인적 코멘트가 담긴 브이로그·탐방기 형식.

# 절차

## 1. 입력 받기 (이미 말했으면 다시 묻지 않는다)

1. **여행지**가 어디인가 (예: 삿포로, 다낭)
2. 가고 싶은 **장소 유형** (예: 온천, 스키장, 카페, 야시장)
3. 이번 여행의 **테마** (예: 관광, 먹방, 기타(guitar) 구매)

## 2. 소스 선택 및 검색어 설계

여행지 국가에 맞춰 현지에서 실제 많이 쓰는 검색 사이트·커뮤니티를 고른다. 검색어는 현지어를 우선한다.
(대상국별 소스 목록은 아래 "국가별 소스 힌트" 참고.)

**일반 키워드 검색은 배제 대상 소스가 상위를 점령한다.** 반드시 아래 두 전략을 우선한다:

**모든 검색은 `site:` 도메인 한정으로 수행한다.** 일반 키워드 검색은 기성 플랫폼·아필리에이트 SEO 블로그가 상위를 독식하므로 사용하지 않는다.

**텍스트 소스 — 도메인 한정 검색 (현지인 구어체 키워드 우선)**

검증으로 효과가 확인된 키워드만 사용한다. ★ 표시가 검증 통과 키워드.

```
site:ameblo.jp <여행지> <장소유형> 行ってみた      ★ 합격률 80%
site:hatenablog.com <여행지> <장소유형> 行った      ★ 합격률 75%
site:hatenablog.com <여행지> <장소유형> 感想
site:note.com <여행지> <장소유형> ひとりで          ★ 합격률 100%
site:note.com <여행지> <장소유형> 地元              ★ 합격률 100%
```

사용하지 않는다 (검증으로 효과 없음 확인):
- `レポ`, `リピ確定` — `行ってみた`와 결과 중복
- `通ってる OR 近所` — OR 연산자 미작동, 유효 결과 0개

**YouTube — WebSearch만 사용 (WebFetch 하지 않는다)**

YouTube 페이지는 JavaScript 렌더링이라 WebFetch로 열면 푸터만 반환된다.
WebSearch(`site:youtube.com`)로 구글 인덱싱 결과를 받아 제목·채널명이 현지어인지만 확인한다.
뉴스 채널이 상위를 점유할 때는 해당 키워드를 버리고 다른 키워드로 교체한다.

```
site:youtube.com <여행지> <장소유형> 穴場 vlog -ゆっくり解説 -ランキング   ★ 일본어 결과 확인
```

사용하지 않는다:
- `銭湯 地元 行ってみた` — 화재·사건 뉴스가 상위를 독식, vlog 발굴 불가

## 3. 개인 여행기 탐색 + 후보 정리

검색 결과에서 **소스 원칙**에 맞는 글만 추려 6~8개 후보를 정리한다. 각 후보에:
- 현지어 이름 + 한국어 이름(있으면), 종류
- **현지어 주소** — 글 본문·Google Maps 검색으로 최대한 추출한다.
  - 우선순위: 글 본문에 명시된 주소 > Google Maps에서 현지어 이름 검색 결과 > 동네(구·동) 단위 대략 위치
  - 주소를 끝내 찾지 못하면 "주소 미확인"으로 표기하고, 사용자에게 직접 확인을 권고한다.
  - 좌표(`lat`, `lng`)도 함께 기록한다. Google Maps 검색 결과 URL에서 추출하거나 WebFetch로 확인한다.
- 왜 골랐는지 한 줄 근거 + **출처 링크** (어떤 개인 글에서 나왔는지)
- **현지어 리뷰 비율(추정) 약 N%** — 지도/리뷰에서 현지어 리뷰 비중을 가늠해 표기.
  비율이 높을수록 로컬한 곳. 산출 근거가 약하면 "추정"임을 명시한다.

## 4. 제시

후보를 번호 매겨 제시하고 "장바구니에 담을 번호를 골라주세요"라고 안내한다.

# 출력 형식 (예시)

```
1. つきさむ温泉 (온천 / 삿포로 시로이시구)
   - 주소: 札幌市白石区南郷通20丁目 (좌표: 43.0421, 141.4012)
   - 근거: 개인 블로그 "50대 주부의 솔로 활동 일기" — 혼자 들른 동네 온천 방문기
   - 출처: https://ameblo.jp/nagippumama/...
   - 현지어(일본어) 리뷰 비율 약 82% — 로컬 색이 강함

2. 奥の湯 (銭湯 / 삿포로 기타구)
   - 주소: 札幌市北区北31条西5丁目 (좌표: 미확인 — Google Maps에서 확인 권고)
   - 근거: hatenablog 삿포로 銭湯 순례 블로그 — 번호 순서대로 방문한 기록
   - 출처: https://sapporo-sento-syosinsya.hatenablog.com/...
   - 현지어 리뷰 비율 약 74% (추정)
```

# 다음 단계로 넘기기

사용자가 번호를 고르면 `manage-travel-cart` 스킬로 넘어가 장바구니에 저장한다.
이 스킬 자체는 저장을 하지 않는다 — 후보를 "제안"만 한다.

# 하지 않는 것

- 마이리얼트립이나 다른 예약 사이트의 상품을 여기서 검색하지 않는다 (`recommend-mrt-products`의 역할).
- 존재를 확인할 수 없는 곳을 지어내지 않는다. 검색 결과에 없으면 없다고 말한다.
- 배제 대상 소스(기성 플랫폼·인플루언서·협찬 글)를 근거로 쓰지 않는다.

# 운영 전제 조건

이 스킬은 **WebFetch(페이지 실제 열람) 권한이 필요하다.**
- WebFetch 없이는 도메인·제목 필터까지만 가능하며, 글 본문의 협찬 여부·개인 서사 유무·
  현지어 리뷰 비율 확인이 불가능하다.
- WebFetch 권한이 없는 환경에서는 후보를 "도메인 기준 잠재 후보"로만 제시하고,
  내용 검증이 불가능함을 사용자에게 명시한다.

# 국가별 소스 힌트

한국인이 많이 가는 여행지 순으로 확장한다. (아래는 초기 후보이며, 실제 검증은
`search-verifier` 에이전트로 확인한다.)

**아시아**

| 국가/지역 | 텍스트 소스(블로그·커뮤니티) | 현지 자국민 유튜브 탐색 키워드 예시 |
|-----------|------------------------------|--------------------------------------|
| 일본 | 아메바 블로그(ameblo), 하테나 블로그(hatena), note, 5ch 지역판 | `札幌 温泉 穴場 vlog -ゆっくり解説 -ランキング`, `地元民 温泉 札幌 行ってみた` |
| 베트남 | Facebook 지역 그룹, 개인 블로그, Foody의 개인 리뷰 본문 | `quán ăn ngon Đà Nẵng ít người biết`, `review thật lòng` |
| 태국 | Pantip 포럼(여행·리뷰 게시판), 개인 블로그 | `ร้านอาหารซ่อนเร้น กรุงเทพ`, `รีวิวจริง คนท้องถิ่น` |
| 대만 | PTT(여행판·Gossiping), 痞客邦(pixnet) 개인 블로그 | `台北隱藏版美食 在地人推薦`, `私房景點 vlog` |
| 필리핀 | Reddit r/Philippines, Facebook 지역 그룹(도시별), 개인 블로그 | `hidden gems Manila locals only`, `underrated cebu food vlog` |
| 홍콩 | LIHKG(連登討論區), 香港討論區(hkdiscuss), 개인 블로그 | `香港隱世食店 本地人`, `街坊推介 vlog` |
| 싱가포르 | HardwareZone 포럼 여행·음식판, Reddit r/singapore, 개인 블로그 | `hidden hawker stalls Singapore locals eat`, `neighbourhood food vlog` |
| 인도네시아(발리 등) | Kaskus 포럼 여행게시판, Facebook 지역 그룹, 개인 블로그 | `kuliner tersembunyi Bali warga lokal`, `review jujur tempat makan` |
| 튀르키예 | Ekşi Sözlük(개인 경험 서술 특화 포럼), 개인 블로그 | `İstanbul saklı mekanlar yerel halk`, `keşfedilmemiş restoran vlog` |

**북미**

| 국가/지역 | 텍스트 소스 | 현지 자국민 유튜브 탐색 키워드 예시 |
|-----------|-------------|--------------------------------------|
| 미국 | Reddit 도시 서브레딧(r/nyc, r/LosAngeles, r/chicago, r/seattle 등), 개인 음식 블로그 | `hidden gem NYC locals only`, `underrated LA food spots vlog` |
| 캐나다 | Reddit 도시 서브레딧(r/vancouver, r/toronto, r/montreal 등), 개인 블로그 | `hidden restaurants Vancouver locals`, `undiscovered spots Toronto vlog` |

**유럽**

| 국가/지역 | 텍스트 소스 | 현지 자국민 유튜브 탐색 키워드 예시 |
|-----------|-------------|--------------------------------------|
| 영국·아일랜드 | Reddit 도시 서브레딧(r/london, r/edinburgh, r/ireland), 개인 블로그 | `hidden London locals only`, `underrated Edinburgh spots vlog` |
| 프랑스 | Le Routard 포럼(개인 게시글만, 편집 기사 제외), Over-Blog 개인 블로그 | `endroits cachés Paris habitants`, `resto méconnu vlog français` |
| 이탈리아 | Viaggiare.net 포럼 개인 글, Reddit r/italy, 개인 블로그 | `posti nascosti Roma residenti`, `trattoria sconosciuta vlog italiano` |
| 스페인·포르투갈 | Mochileros.org 포럼, Reddit r/spain·r/portugal, 개인 블로그 | `lugares escondidos Madrid locales`, `restaurante desconocido vlog` |
| 독일·오스트리아·스위스 | Reiseforum.de 개인 여행기, Reddit r/germany, 개인 블로그 | `versteckte Orte Berlin Einheimische`, `geheimtipp Restaurant vlog` |
| 네덜란드·벨기에 | Reddit r/netherlands·r/belgium, 개인 블로그 | `verborgen plekken Amsterdam locals`, `onbekend restaurant vlog` |
| 북유럽(스웨덴·노르웨이 등) | Reddit 국가 서브레딧, 개인 블로그 | `dolda platser Stockholm lokalinvånare`, `skjulte steder Oslo vlog` |
| 동유럽(체코·폴란드·헝가리 등) | Reddit 도시 서브레딧(r/prague, r/krakow 등), 개인 블로그 | `skrytá místa Praha místní`, `ukryte miejsca Kraków vlog` |
| 그리스 | Reddit r/greece, 개인 블로그 | `κρυμμένα μέρη Αθήνα ντόπιοι`, `άγνωστο εστιατόριο vlog` |

**오세아니아**

| 국가/지역 | 텍스트 소스 | 현지 자국민 유튜브 탐색 키워드 예시 |
|-----------|-------------|--------------------------------------|
| 호주 | Reddit 도시 서브레딧(r/sydney, r/melbourne, r/brisbane), 개인 블로그 | `hidden gems Melbourne locals eat`, `underrated Sydney food vlog` |
| 뉴질랜드 | Reddit r/newzealand, 개인 블로그 | `hidden spots Auckland locals`, `underrated NZ food vlog` |

※ 위 소스에서도 "개인적 서사가 담긴 글/영상"만 채택하고, 집계 점수·인플루언서·협찬 콘텐츠는 배제한다.
※ Reddit은 집계 플랫폼이 아닌 커뮤니티이므로 소스로 사용하되, 도시/국가 특화 서브레딧의 개인
  경험담만 대상으로 한다. 범용 서브레딧(r/travel, r/solotravel)은 관광객 쏠림 가능성이 있으므로
  보조 참고에 머문다.
※ YouTube는 **현지 자국민 채널만** 참고한다. 채널 운영 언어와 댓글 언어가 자국어인지 반드시 확인하고,
  외국인(한국인 포함)이 올린 여행기 영상은 소스로 쓰지 않는다.
