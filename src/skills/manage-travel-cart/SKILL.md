---
name: manage-travel-cart
description: 사용자가 고른 여행 장소를 장바구니 파일(JSON)에 담고, 목록을 보여주고, 빼는 작업을 한다. 장바구니가 차면 1단계로 Google Maps 링크를 생성하고, 2단계로 Google My Maps 커스텀 지도를 만들어 공유 링크를 제공한다. "이거 담아줘", "장바구니 보여줘", "3번 빼줘", "지도로 보여줘", "My Maps 만들어줘" 같은 요청에 사용한다.
---

# 목적

`discover-local-spots`에서 고른 장소, 또는 사용자가 직접 알려준 장소를 **여행(trip) 단위**로 저장하고,
저장된 목록을 Google Maps에서 바로 확인하거나 나만의 커스텀 지도로 만들어준다.

# 저장 위치와 JSON 형식

`./travel-cart/<trip-id>.json` 에 저장한다. `trip-id`는 사용자가 이름을 안 정했으면
"목적지-대략날짜" 형태로 자동으로 만든다 (예: `sapporo-2026-09`).

```json
{
  "trip_id": "sapporo-2026-09",
  "destination": "Sapporo, Japan",
  "items": [
    {
      "id": "1",
      "name": "つきさむ温泉",
      "name_local": "月寒温泉",
      "type": "온천",
      "address": "札幌市白石区南郷通20丁目",
      "lat": 43.0421,
      "lng": 141.4012,
      "local_review_ratio": 82,
      "source_url": "https://ameblo.jp/nagippumama/entry-12870499502.html",
      "note": "50대 주부 솔로 방문기, 협찬 없음",
      "day": null
    }
  ]
}
```

필드 설명:
- `name_local` : 현지어 이름 (Google Maps 검색 정확도 향상에 사용)
- `address` : 현지어 주소 (좌표보다 주소가 검색에 더 정확할 때 사용)
- `lat`, `lng` : 좌표. 모르면 `null`로 두고 주소로 대체한다
- `local_review_ratio` : 현지어 리뷰 비율 %. `discover-local-spots`에서 전달받은 값
- `source_url` : 이 장소를 발굴한 개인 블로그·커뮤니티 글 링크
- `day` : 일정 배정 전 `null`. `build-itinerary`가 채운다

# 절차

## 1. 담기

사용자가 번호나 이름으로 장소를 지정하면, **아래 형식으로 선택을 유도한다:**

```
담을 번호와 가고 싶은 날짜를 함께 알려주세요.
날짜를 아직 모르면 번호만 말해도 돼요.

예시:
  "1번 1일차, 3번 2일차, 5번 3일차"   ← 날짜 포함
  "1 3 5"                              ← 날짜 미정, 나중에 일정 짤 때 배치
```

입력을 받으면:
- 날짜가 포함된 항목 → JSON `day` 필드에 바로 기록한다 (`"day": 1`)
- 날짜가 없는 항목 → `day: null`로 저장하고, 나중에 `build-itinerary`가 배치한다
- 해당 trip 파일이 없으면 새로 만들고, 있으면 `items` 배열에 추가한다
- 같은 이름이 이미 있으면 중복 담지 않고 알려준다
- 파일을 고칠 때는 항상 전체를 읽고 → 수정 → 전체를 다시 쓴다 (부분 수정으로 JSON을 깨뜨리지 않는다)

담은 뒤 현재 장바구니 상태를 간략히 보여준다:
```
✅ 3곳 담았어요.

Day 1 확정: さかえ湯
Day 2 확정: 奥の湯
날짜 미정:  豊平峡温泉
```

## 2. 보기

JSON을 읽어 아래 형식으로 보여준다:

```
📍 삿포로 여행 장바구니 (3개)

1. つきさむ温泉 (온천)
   📍 札幌市白石区南郷通20丁目
   🗾 현지어 리뷰 비율 약 82%
   🔗 출처: https://ameblo.jp/...

2. 奥の湯 (銭湯)
   📍 北区北31条
   🗾 현지어 리뷰 비율 약 74%
   ...
```

## 3. 빼기

사용자가 지정한 번호·이름의 항목을 `items`에서 제거하고 파일을 다시 저장한다.

---

# Google Maps 연동

## 1단계 — Google Maps URL 생성 (로그인 불필요, 즉시 사용 가능)

"지도로 보여줘" 요청이 오면 장바구니 항목마다 Google Maps 검색 링크를 생성해 목록으로 보여준다.

**개별 링크 (이름+주소 검색):**
```
https://www.google.com/maps/search/?api=1&query=<name_local>+<address>
```

**좌표가 있는 경우:**
```
https://www.google.com/maps/search/?api=1&query=<lat>,<lng>
```

출력 예시:
```
🗺️ Google Maps 링크

1. つきさむ温泉
   https://www.google.com/maps/search/?api=1&query=月寒温泉+札幌市白石区南郷通20丁目

2. 奥の湯
   https://www.google.com/maps/search/?api=1&query=奥の湯+北区北31条
...
```

## 2단계 — Google My Maps 커스텀 지도 생성 (Google Drive 연동 필요)

"My Maps 만들어줘" 또는 "커스텀 지도 만들어줘" 요청이 오면 아래 절차를 실행한다.

### 2-1. Google Drive 커넥터 확인

`sync-google-calendar`와 동일하게, 이 스킬은 OAuth 코드를 직접 다루지 않는다.
Codex 환경에 연결된 Google Drive 커넥터(MCP)가 있는지 먼저 확인한다.
없으면 사용자에게 연결을 안내하고 멈춘다.

### 2-2. KML 파일 생성

장바구니 항목을 KML 포맷으로 변환한다. KML은 Google My Maps가 인식하는 지도 데이터 형식이다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name><trip_id> 여행 장바구니</name>
    <description>myrealtrip-curator로 발굴한 로컬 스팟 목록</description>

    <!-- 항목마다 Placemark 하나 -->
    <Placemark>
      <name>つきさむ温泉</name>
      <description>
        종류: 온천
        현지어 리뷰 비율: 82%
        출처: https://ameblo.jp/nagippumama/...
      </description>
      <!-- 좌표가 있으면 Point 사용 -->
      <Point>
        <coordinates>141.4012,43.0421,0</coordinates>
      </Point>
    </Placemark>

    <!-- 좌표 없이 주소만 있는 경우 -->
    <Placemark>
      <name>奥の湯</name>
      <description>
        종류: 銭湯
        주소: 北区北31条
        현지어 리뷰 비율: 74%
      </description>
      <address>北区北31条, 札幌市</address>
    </Placemark>
  </Document>
</kml>
```

KML 파일은 `./travel-cart/<trip-id>.kml`로 로컬에도 저장한다.

### 2-3. Google Drive에 업로드

Google Drive 커넥터로 KML 파일을 업로드한다:
- 파일명: `<trip-id>-map.kml`
- mimeType: `application/vnd.google-earth.kml+xml`
- 공유 설정: 링크 있는 사람 누구나 보기 가능

업로드 후 받은 Drive 파일 ID로 My Maps 임포트 URL을 생성한다:
```
https://www.google.com/maps/d/edit?mid=<file-id>
```

### 2-4. 사용자에게 전달

```
✅ Google My Maps 지도가 준비됐어요!

🗺️ 지도 열기: https://www.google.com/maps/d/edit?mid=xxxx
📎 KML 파일: ./travel-cart/sapporo-2026-09.kml

지도에 총 3개 장소가 핀으로 표시돼 있어요.
로그인하면 직접 편집하거나 다른 사람과 공유할 수 있어요.
```

### 사용자 확인 원칙

Drive에 파일을 올리기 전에 반드시 "지도를 만들어 Google Drive에 저장할까요?"라고 확인받는다.
사용자 동의 없이 Drive에 파일을 생성하지 않는다.

---

# 다음 단계로 넘기기

- "일정 짜줘" → `build-itinerary` 스킬
- "캘린더에 넣어줘" → `sync-google-calendar` 스킬
- "마이리얼트립 상품 찾아줘" → `recommend-mrt-products` 스킬

# 하지 않는 것

- 마이리얼트립 상품을 여기서 검색하거나 추천하지 않는다
- Google OAuth 토큰·API 키를 이 스킬 안에 저장하거나 직접 다루지 않는다
- 사용자 동의 없이 Drive에 파일을 업로드하지 않는다
- 좌표를 모를 때 임의로 지어내지 않는다 — 주소 검색으로 대체한다
