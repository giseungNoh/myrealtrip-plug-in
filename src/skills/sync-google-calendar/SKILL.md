---
name: sync-google-calendar
description: build-itinerary가 만든 일정표를 google-calendar 플러그인으로 Google Calendar에 실제 이벤트로 등록한다. 플러그인이 없으면 설치를 안내한 뒤 진행한다. "캘린더에 넣어줘", "구글 캘린더로 옮겨줘" 같은 요청에 사용한다.
---

# 목적

`build-itinerary`가 완성한 일정표(`./travel-cart/<trip-id>.json`)를 읽어서
Google Calendar에 실제 이벤트로 등록한다.

# 방식: google-calendar 플러그인

## 0. 연결 확인 및 설치 유도 (가장 먼저)

- **Codex**: `google-calendar` 플러그인이 설치돼 있는지 확인한다 (`codex plugin list`로 확인).
  없으면 사용자에게 설치를 안내한다:
  ```
  codex plugin add google-calendar@openai-curated
  ```
  설치 후 최초 사용 시 Google 계정 인증(OAuth) 창이 뜬다 — **사용자가 직접 로그인**해야 하며,
  이 스킬이 대신 로그인하거나 인증 정보를 다루지 않는다.
- **Claude Code**: 연결된 Google Calendar MCP 커넥터가 있는지 먼저 확인한다. 없으면
  사용자에게 연결을 안내하고 멈춘다.

설치·인증을 사용자가 원하지 않으면 억지로 진행하지 않는다 — 대신 아래 "다른 캘린더 앱만
쓰고 싶다면" 절차로 안내한다.

## 사용하는 도구 (google-calendar 플러그인)

Codex의 google-calendar 플러그인은 아래 도구를 제공한다. 이 스킬에서 실제로 쓰는 것만 정리한다
(Claude Code MCP 커넥터는 도구 이름이 다를 수 있으니 연결 시점에 실제 제공 도구를 확인한다):

| 도구 | 이 스킬에서 쓰는 시점 |
|------|----------------------|
| `get_profile` | 최초 1회 — 연결된 계정이 맞는지 사용자에게 확인시킨다 |
| `search_events` | 이벤트 생성 전 — 여행 날짜 범위(`time_min`~`time_max`)에 같은 이름의 이벤트가 이미 있는지 확인 (중복 등록 방지) |
| `create_event` | 신규 이벤트 생성. **`add_google_meet`은 쓰지 않는다** — 여행 일정에 화상회의 불필요 |
| `update_event` | `search_events`에서 이미 존재하는 이벤트를 찾으면 재생성 대신 갱신 |
| `batch_read_event` | 생성/수정한 이벤트 ID들을 한 번에 다시 읽어 실제로 반영됐는지 검증 |
| `get_colors` | 여백 슬롯(🚶)에 일반 장소 이벤트와 다른 `color_id`를 지정해 캘린더에서 구분되게 표시 |
| `delete_event` | 사용자가 특정 이벤트만 빼달라고 할 때 |
| `get_availability` | (선택) 생성 전 그 시간대에 이미 다른 일정이 있는지 확인하고 싶을 때. 겹치면 사용자에게 알리고 계속할지 묻는다 |

그 외 (`fetch`, `read_event`, `read_event_all_fields`, `search`, `search_events_all_fields`,
`respond_event`)는 이 스킬의 기본 흐름에 필요 없다 — 확장 필드 조회나 초대 응답이 필요한
별도 요청이 오면 그때만 쓴다.

`search_events`/`search`/`get_availability`의 `time_min`/`time_max`는 RFC3339(타임존 오프셋
또는 `Z` 포함)로 넘긴다 — 목적지 현지 시각 기준으로 변환해서 넣는다.

# 전제 조건

이벤트를 제대로 구성하려면 장바구니 JSON에 아래가 채워져 있어야 한다:

| 필드 | 필요성 | 채우는 스크립트 |
|------|--------|----------------|
| `day` | 필수 (없으면 경고 후 마지막 날 뒤에 배치) | `route_optimizer.py` |
| `lat`, `lng` | 권장 (있으면 GEO 필드 + Maps URL 자동 생성) | `geocoder.py` |
| `address` | 권장 (없으면 이름으로 Maps URL 구성) | `geocoder.py` |
| `local_review_ratio` | 선택 (있으면 DESCRIPTION에 포함) | `review_ratio.py` |

권장 선행 순서: `geocoder.py` → `route_optimizer.py` → `review_ratio.py` → (아래 절차대로 캘린더 등록)

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

0. **플러그인/커넥터 연결 확인** — 위 "연결 확인 및 설치 유도" 단계를 먼저 처리한다.
1. **장바구니 상태 확인** — `travel-cart/<trip-id>.json`이 존재하는지, `day` 필드가 채워져 있는지 확인한다.
2. **여행 시작일 확인** — 사용자에게 실제 출발일을 묻는다. ("Day 1이 몇 월 며칠인가요?")
3. **미리보기 제시** — 아래 형식으로 등록될 이벤트를 보여주고 확인을 받는다:

   ```
   📅 등록 예정 이벤트 (총 N개) — Google Calendar

   [Day 1 — 9/10(목)]
   Enoteca La Vite (에노테카) — 19:00~21:00 / Piazza San Cosimato
   🚶 자유 탐방 — 16:30~17:00

   [Day 2 — 9/11(금)]
   Enoteca L'Antidoto (에노테카) — 19:00~21:00 / Vicolo del Bologna 19

   이대로 구글 캘린더에 등록할까요?
   ```

4. **중복 확인** — `search_events`로 여행 날짜 범위 안에 같은 이름의 이벤트가 이미 있는지 확인한다.
   있으면 사용자에게 "이미 등록된 이벤트는 업데이트할까요, 건너뛸까요?"라고 묻는다.
5. **확인 후 실행** — 승인이 나면 항목별로 처리한다:
   - 신규 항목 → `create_event` (여백 슬롯은 `get_colors`로 조회한 색상 중 하나를 `color_id`로 지정)
   - 이미 있는 항목(4번에서 발견, 업데이트 선택 시) → `update_event`
6. **검증** — `batch_read_event`로 방금 생성/수정한 이벤트 ID들을 다시 읽어 실제로 반영됐는지 확인한다.
7. **완료 안내** — 신규 생성/업데이트/건너뛴 개수와, 실패한 항목이 있으면 무엇인지 알린다.
   실제 도구 호출 결과를 근거로만 "등록됐다"고 말한다 — 호출 없이 등록됐다고 말하지 않는다.

# 등록 후 개별 수정·취소

일정표 전체를 다시 만들지 않고 이벤트 하나만 바꾸거나 빼고 싶다는 요청이 오면:
- 빼달라는 요청 → 해당 이벤트를 `search_events`로 찾아 `delete_event`
- 시간·장소 등 특정 항목만 수정 → `search_events`로 찾고, 참석자·반복 설정처럼 민감한 값을
  바꿀 때는 `update_event` 전에 먼저 `read_event`로 현재 상태를 확인한 뒤 수정한다

# 다른 캘린더 앱(애플·Outlook)만 쓰고 싶다면

Google Calendar 플러그인을 쓰고 싶지 않거나 애플 캘린더·Outlook에만 넣고 싶으면,
`src/tools/ical_exporter.py`로 표준 `.ics` 파일을 만들어 해당 앱에 직접 임포트할 수 있다
(OAuth·플러그인 설치 불필요, 이 경우에만 사용):

```bash
python3 src/tools/ical_exporter.py \
  --cart travel-cart/<trip-id>.json \
  --start YYYY-MM-DD        # Day 1 = 이 날짜
# 출력: travel-cart/<trip-id>.ics
```

- **애플 캘린더**: .ics 파일 더블클릭 → "추가" 클릭
- **Outlook**: 파일 메뉴 → 열기 및 내보내기 → 가져오기/내보내기 → iCalendar 파일
- **구글 캘린더**로도 이 파일을 수동 임포트할 수 있다 (calendar.google.com → 설정 → 가져오기),
  다만 위 플러그인 방식보다 번거로우니 Google Calendar가 목적지면 플러그인을 우선 안내한다.

# 하지 않는 것

- 사용자 동의 없이 플러그인을 설치하거나 Google 계정 인증을 대신 진행하지 않는다.
- 실제 도구 호출 없이 "캘린더에 등록됐다"고 말하지 않는다.
- 시간대를 모르는 항목에 임의 시간을 넣지 않는다 — 위 표의 기본값을 사용하고 그 사실을 알린다.
