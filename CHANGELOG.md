# CHANGELOG

## Phase P6 — 국정과제 축 (2026-07-21) · 트랙 A 파이프라인

- **방향 확정**: 서비스 목적 = 대통령 발언·지시와 부처 이행 추적. 상위 프레임은 이재명 정부
  123대 국정과제(korea.kr/govVision) — 구조: 과제 ⊃ 스레드 ⊃ 발언 (SPEC-PIPELINE.md §2.4)
- `data/tasks/tasks.json` — 123과제 마스터(5목표·23전략·과제명·주관 부처·원문 PDF 링크),
  govVision 페이지 파싱으로 구축. 정부 발표가 SSOT — 파이프라인은 수정하지 않음
- `pipeline/task_map.py`(11단계, run_all 편입) — Turn 단위 3단 판정
  (①과제명·"국정과제 N번" 직접 언급 → explicit ②키워드 2개 → topic ③1개 일치 LLM 판정 → ai_inferred)
  → `tasks/map.json`(과제↔스레드/턴 매핑, 전 123과제 entries 유지 — "언급 0회"도 기록)
- `tasks/keywords.json` — 과제별 검색 키워드 LLM 1회 생성 캐시.
  자막은 띄어쓰기가 제각각이라 매칭은 공백 무시, 키워드는 구어 통용형("개헌") 중심으로 생성
- 백필 결과(33개 회의): refs 228건(ai_inferred 205 · topic 15 · explicit 8),
  언급 보유 과제 63/123, 과제↔스레드 연결 129건. LLM 비용 $0.05
- korea.kr 공식 안건 앵커는 필수 해제(구두 지시가 공문에 선행할 수 있음 — 발화 기록이 1차 소스)

## Phase 1 — 기반 + 검색 (2026-07-21) · 트랙 B 웹 앱

- 스키마: **SPEC-PIPELINE.md §2 (Statement–Turn–Agenda 3층 구조) 기준으로 구현**
  - 개발 중 트랙 A가 실데이터(회의 34건·문장 35,451건)를 같은 저장소에 적재 → 구버전(§4.1)으로
    시작했던 타입·fixture를 3층 구조로 이관 완료. 화자 = Turn 역참조, chapters → agenda
  - turn_id/agenda_id는 파이프라인 처리 전 단계 데이터가 null일 수 있어 nullable 처리
  - summary가 brief만 있는 경우(문단 근거 sids 없음)에도 §9-3(요약은 PlayLink로 끝난다)을
    지키도록 첫 문장 구간 재생 링크로 폴백
- 샘플 fixture 1건 유지: `2026-cab-0708-dQw4w9`(`[샘플]` 표기) — 실데이터에 아직 없는
  turns/agenda/summary UI 시연용. 파이프라인이 해당 단계 산출을 시작하면 제거 예정
- `styles/tokens.css` — 유튜브 다크 정합 토큰 (색 정의 유일처)
- 공통 컴포넌트 7종: GradeBadge · PlayLink · AiLabel · AiNotice · QuoteText · ThreadStrip · MeetingCard
- 홈 `/` — 그리드(3/2/1열) · 필터 칩(단일 토글) · 인기 키워드/발언자 칩 · 검색바
- 검색 `/search?q=` — MiniSearch 클라이언트 검색 + 한국어 조사 대응 부분 문자열 보강,
  문장 카드(명조 인용 + 하이라이트 + PlayLink + 회의 메타)
- 시청 `/watch/[id]` — YouTube IFrame 플레이어(`?t=` 구간 시작) · AI 요약 카드(문단별 PlayLink) ·
  챕터 칩 시크 · 자막 패널(패널 내 검색·현재 문장 red 보더 자동 추적·문장 클릭 시크·자막 고지·AiNotice)
- `scripts/build-index.mjs` — meetings → index(meetings/search-{n}/keywords) 생성 + 검색
  페이지 fetch용 public 사본 (트랙 A build_index.py 완성 시 대체 예정)
- ⚠️ 검색 색인 총량 15MB(원본 기준)로 SPEC.md §2의 서버 검색 전환 기준(5MB) 초과 상태.
  Phase 1은 최소화 직렬화 + 검색 페이지 진입 시에만 로드로 완화. **Phase 2 이후 Meilisearch
  Cloud 전환 검토 필요**
- 환경 이슈: 이 개발 장비(Windows ARM64)에서 SWC 네이티브 바이너리 로드가 OS 수준에서
  거부됨(파일·아키텍처는 정상). `scripts/patch-swc-wasm.mjs`(postinstall)로 Next 로더가
  `@next/swc-wasm-nodejs`를 쓰도록 패치. next는 WASM 배포가 있는 14.2.33으로 고정
