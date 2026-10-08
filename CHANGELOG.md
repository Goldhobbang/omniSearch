# Changelog

형식은 [Keep a Changelog](https://keepachangelog.com/)를 따른다.

## [Unreleased]

### Added
- 웹 UI 전면 개편: Vite + React + shadcn/ui. 라우팅 카드, 엔진별 점수·상태, 출처 배지가 붙은 통합(RRF) 결과, 라이트/다크 테마.
- GitHub Pages 브라우저 데모(`npm run build:demo`): 서버 없이 CORS 허용 엔진으로 같은 분류·융합 실행.
- `/api/smart-search` 응답에 엔진별 `status`·`detail` 추가.
- `tests/test_web.py`: 빌드된 UI가 서빙되는지 확인하는 스모크 테스트.

### Changed
- `/api/search`: DuckDuckGo가 결과 0건을 예외로 알리면 에러 대신 빈 목록을 돌려준다.
- 웹 UI 일반 검색(`/`)과 스마트 검색(`/smart`)을 한 화면으로 통합 (`/smart`는 호환용으로 유지).

## [0.2.0]

- 설치형 도구로 재구성: CLI, MCP 서버, 웹 UI.
- 병렬 hedged 검색, 데드라인, 실패 시 쿨다운, 쿼터 인지 가속.
- 가중 RRF 융합, Bing·Google 뉴스 RSS 엔진, 정직한 점수 산정.
