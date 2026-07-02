---
name: sync-google-calendar
description: build-itinerary가 만든 일정표를 구글/애플/Outlook 캘린더로 내보낸다. ical_exporter.py로 표준 .ics 파일을 생성하고, 캘린더 앱에 드래그&드롭으로 임포트한다. OAuth·MCP 불필요. "캘린더에 넣어줘", "구글 캘린더로 옮겨줘" 같은 요청에 사용한다.
---

# 목적

`build-itinerary`가 완성한 일정표(`./travel-cart/<trip-id>.json`)를 읽어서
표준 `.ics` 파일을 생성하고, 사용자가 어떤 캘린더 앱에도 임포트할 수 있게 한다.

# 방식: ical_exporter.py (OAuth 불필요)

Google Calendar MCP나 OAuth 인증이 필요 없다.
`src/tools/ical_exporter.py`가 RFC 5545 표준 `.ics` 파일을 직접 생성한다.
생성된 파일은 구글 캘린더·애플 캘린더·Outlook 모두 임포트 가능하다.

```bash
# 실행 (Python 표준 라이브러리만 사용, 추가 설치 불필요)
python3 src/tools/ical_exporter.py \
  --cart travel-cart/<trip-id>.json \
  --start YYYY-MM-DD        # Day 1 = 이 날짜

# 출력: travel-cart/<trip-id>.ics
```

**출력 파일 임포트 방법**
- **구글 캘린더**: 브라우저에서 calendar.google.com → 톱니바퀴 → 설정 → 가져오기 → .ics 업로드
- **애플 캘린더**: .ics 파일 더블클릭 → "추가" 클릭
- **Outlook**: 파일 메뉴 → 열기 및 내보내기 → 가져오기/내보내기 → iCalendar 파일

# 전제 조건

`ical_exporter.py`가 제대로 동작하려면 장바구니 JSON에 아래가 채워져 있어야 한다:

| 필드 | 필요성 | 채우는 스크립트 |
|------|--------|----------------|
| `day` | 필수 (없으면 경고 후 마지막 날 뒤에 배치) | `route_optimizer.py` |
| `lat`, `lng` | 권장 (있으면 GEO 필드 + Maps URL 자동 생성) | `geocoder.py` |
| `address` | 권장 (없으면 이름으로 Maps URL 구성) | `geocoder.py` |
| `local_review_ratio` | 선택 (있으면 DESCRIPTION에 포함) | `review_ratio.py` |

권장 선행 순서: `geocoder.py` → `route_optimizer.py` → `review_ratio.py` → `ical_exporter.py`

# 이벤트 구성

## 장소 이벤트 (유형 B)

장바구니 각 항목이 VEVENT 하나가 된다.

- **SUMMARY**: `장소명 (종류)` — 예: `Enoteca La Vite (에노테카(와인바))`
- **DTSTART / DTEND**: 장소 유형 키워드로 자동 추론

  | 유형 | 시작 | 종료 |
  |------|------|------|
  | 카페·아침 | 09:00 | 10:30 |
  | 점심·식당 | 12:00 | 13:30 |
  | 오후 (기본) | 14:00 | 16:00 |
  | 와인바·에노테카·저녁 | 19:00 | 21:00 |
  | 클럽·야시장 | 21:00 | 23:00 |

- **LOCATION**: 현지어 주소
- **GEO**: 위도;경도 (좌표 있을 때)
- **DESCRIPTION**: 현지어 리뷰 비율 / Google Maps URL / 발굴 출처 / 메모

## 여백 슬롯

각 Day마다 16:30–17:00 자유 탐방 블록이 자동 추가된다.
"이 시간은 비워두세요 — 근처를 걷다 우연히 발견한 곳에 들러보세요."

## 숙소 이벤트 (향후)

현재 장바구니 JSON 스키마에 숙소 필드가 없다.
숙소 정보가 추가되면 체크인~체크아웃 전일 이벤트(`DTSTART;VALUE=DATE`)로 처리한다.

# 절차

1. **장바구니 상태 확인** — `travel-cart/<trip-id>.json`이 존재하는지, `day` 필드가 채워져 있는지 확인한다.
2. **여행 시작일 확인** — 사용자에게 실제 출발일을 묻는다. ("Day 1이 몇 월 며칠인가요?")
3. **미리보기 제시** — 아래 형식으로 생성될 이벤트를 보여주고 확인을 받는다:

   ```
   📅 생성 예정 이벤트 (총 N개)
   출력 파일: travel-cart/rome-trastevere-2026.ics

   [Day 1 — 9/10(목)]
   Enoteca La Vite (에노테카) — 19:00~21:00 / Piazza San Cosimato
   🚶 자유 탐방 — 16:30~17:00

   [Day 2 — 9/11(금)]
   Enoteca L'Antidoto (에노테카) — 19:00~21:00 / Vicolo del Bologna 19

   이대로 .ics 파일을 생성할까요?
   ```

4. **확인 후 실행** — 승인이 나면 `ical_exporter.py`를 실행한다.
5. **완료 안내** — 생성된 `.ics` 경로와 각 캘린더별 임포트 방법을 알려준다.

# 하지 않는 것

- 구글 캘린더 API에 직접 접근하지 않는다 (OAuth 불필요).
- `.ics` 없이 캘린더 앱을 프로그램으로 조작하지 않는다.
- 사용자 동의 없이 파일을 생성하지 않는다.
- 시간대를 모르는 항목에 임의 시간을 넣지 않는다 — 위 표의 기본값을 사용하고 그 사실을 알린다.
