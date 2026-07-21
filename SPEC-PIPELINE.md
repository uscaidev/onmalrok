# SPEC-PIPELINE.md — 유튜브 수집·자막 파이프라인 설계서

> **트랙 A (핵심 우선 개발).** 이 문서 하나로 파이프라인 구현이 가능하도록 작성된 자기완결형 설계서.
> 병렬 트랙 B(웹 앱)는 SPEC.md를 따르며, 두 트랙의 유일한 접점은 §2 데이터 계약이다.
> 파이프라인 관련 내용이 SPEC.md §8과 충돌하면 **이 문서가 우선**한다.
> 버전: 1.0 (2026.07.21)

---

## 0. 작업 지시 요약

- 목표: KTV 유튜브의 국무회의·국민업무보고 영상을 **사람 개입 0으로** 감지→자막 수집→가공→`/data` JSON 산출.
- 자막은 방송 직후 존재하지 않는다(VOD 자막 생성까지 수 시간~수일). 따라서 단발 처리가 아니라 **상태 머신 + 반복 폴링**으로 설계한다(§3).
- `/data`의 JSON이 웹 앱(트랙 B)이 읽는 유일한 인터페이스다. §2 계약을 어기는 산출물 금지.
- 실패는 기록하되 전체를 멈추지 않는다(§8). 원문(`text_raw`)은 어떤 경우에도 삭제하지 않는다.
- LLM은 배치 전용, 실시간 처리 금지. 월 사용량을 `pipeline/usage.json`에 누적한다.
- Phase 순서(§9)대로 구현하고, 완료 기준(✅)을 만족한 뒤 다음으로 넘어간다.

## 1. 스택

| 항목 | 선택 |
|------|------|
| 언어 | Python 3.11, 저장소 `/pipeline` |
| 실행 | GitHub Actions cron **일 3회** — KST 06:00 / 12:00 / 21:00 (`0 21,3,12 * * *` UTC) |
| 감지 | 유튜브 채널 RSS(`youtube.com/feeds/videos.xml?channel_id={KTV}`) — 키 불필요 · 보조: korea.kr 국무회의 브리핑 목록 크롤 |
| 자막 | yt-dlp (`--write-auto-subs --sub-langs ko`) |
| STT 폴백 | faster-whisper (옵션, §3.4) — 배치 전용이므로 "실시간 STT 금지" 원칙과 무충돌 |
| LLM | Anthropic API claude-sonnet 계열 (교정·화자·요약·관계추정) |
| 상태 저장 | `data/state/videos.json` (영상별 상태 머신) — Git 커밋으로 이력 관리 |

## 2. 데이터 계약 (트랙 B와의 인터페이스 — 변경 시 양 트랙 합의 필수)

### 2.1 산출 파일

```
data/
├─ meetings/{meeting_id}.json    # §2.2 Meeting
├─ threads/{thread_id}.json      # SPEC.md §4.2와 동일 (노드는 turn 참조로 확장, §2.3)
├─ index/meetings.json           # 경량 목록
├─ index/search-{n}.json         # 검색 샤드 (SPEC.md §4.3)
├─ index/keywords.json           # 키워드 카운트
├─ index/agenda.json             # 의제 뷰 인덱스 (§2.5) — 12 agenda_view.py 산출
├─ fields.json                   # 분야 매핑 테이블 (§2.5) — 사람이 PR로만 갱신
├─ dump/latest.json              # 전체 덤프 (오픈데이터)
├─ state/videos.json             # 상태 머신 (§3) — 파이프라인 내부용, 앱은 읽기만
├─ tasks/tasks.json              # 국정과제 123 마스터 (§2.4) — 공식 목록, 수동 구축·개정 시만 갱신
├─ tasks/keywords.json           # 과제별 검색 키워드 캐시 (§2.4) — LLM 1회 생성, 이후 재사용
├─ tasks/map.json                # 과제↔스레드/턴 매핑 (§2.4) — 파이프라인 산출
└─ glossary.json                 # 교정 용어집 (§5.2)
```

### 2.2 Meeting 스키마 — 3층 구조 (Statement–Turn–Agenda)

문장은 **저장·타임스탬프의 원자 단위**, 그 위에 화자 턴과 의제 구간을 겹층으로 얹는다. 문장을 재분할하지 않으므로 sid·검색·구간재생은 층 도입과 무관하게 유지된다.

```typescript
interface Meeting {
  id: string;                    // "{연도}-{cab|rpt}-{MMDD}-{yid앞6}" 예: "2026-rpt-0716-imQ8RH"
  kind: "cabinet" | "report";
  title: string;
  date: string;                  // KST
  youtube_id: string;
  duration_sec: number;
  source: { video: string; text?: string };
  summary: { brief: string; generated_at: string; model: string } | null;
  agenda: AgendaBlock[];         // 의제 구간 (기존 chapters 승격) — 요약·챕터 UI의 단위
  turns: Turn[];                 // 화자 턴 — 스레드 노드·화자 라벨의 단위
  statements: Statement[];       // 문장 — 검색·타임스탬프의 단위
  stats: { statement_count: number; turn_count: number };
  pipeline_status: "done" | "partial" | "waiting_captions" | "failed";  // §3
}

interface AgendaBlock {
  aid: string;                   // "{meeting_id}@a{n}"
  title: string;                 // LLM 생성 기본. korea.kr 공식 안건명 앵커는 선택 보강(2026-07-21 필수 해제)
  start_sec: number;
  sid_range: [string, string];   // 포함 구간 [첫 sid, 끝 sid]
  official: boolean;             // korea.kr 안건 매핑 여부
}

interface Turn {
  tid: string;                   // "{meeting_id}@t{n}"
  speaker: { name: string; inferred: boolean; verified: boolean } | null;
  sid_range: [string, string];
  agenda_id: string;
  rep_sid: string;               // 대표 문장 (스레드 노드·카드 인용용)
}

interface Statement {
  sid: string;                   // "{meeting_id}#{seq}"
  start_sec: number;
  text: string;                  // 교정본
  text_raw: string;              // 자동자막 원문 — 영구 보존
  corrected: boolean;
  turn_id: string;
  agenda_id: string;
  text_verified: boolean;        // 시민 3인 합의 (SPEC.md §13)
  history: { field: "speaker"|"text"; prev: string; at: string; via: "pipeline"|"citizen" }[];
  thread_refs: { thread_id: string; grade: "explicit"|"topic"|"ai_inferred" }[];
}
```

※ 화자는 Turn에만 있다. 문장의 화자 = 소속 Turn의 화자 (앱은 turn_id로 역참조).

### 2.3 Thread 노드의 turn 참조

SPEC.md §4.2 ThreadNode에서 `sid` → `tid`로 참조를 승격한다: `{ tid, rep_sid, meeting_id, date, role, grade, grade_evidence, reviewed, rel_label }`. 노드의 실체는 "화자의 발언 턴"이고, UI 인용은 rep_sid를 쓴다.

### 2.4 국정과제 축 (GovTask) — 2026-07-21 방향 확정

서비스의 상위 프레임. 이재명 정부 **123대 국정과제**(korea.kr/govVision: 5대 국정목표 → 전략 → 과제 123개, 과제별 주관 부처 표기)를 고정 축으로 삼아 스레드·발언을 그 아래에 건다. 구조: **국정과제(고정 축) ⊃ 스레드(지시 단위) ⊃ Turn/Statement(원문)**. 부처별 뷰는 tasks.json의 ministries를 피벗해 프론트에서 파생한다(별도 산출물 없음).

```typescript
// tasks/tasks.json — 공식 목록 마스터. 정부 발표가 SSOT이며 파이프라인은 수정하지 않는다
interface GovTask {
  no: number;                    // 1~123 공식 순번
  title: string;                 // 공식 과제명
  goal: string;                  // 5대 국정목표
  strategy: string;              // 전략 (목표 하위)
  ministries: string[];          // 주관 부처 (공식 괄호 표기 기준, 복수 가능)
  source: string;                // korea.kr/govVision 원문 링크
}

// tasks/map.json — 파이프라인 산출 (11 task_map.py)
interface TaskMap {
  generated_at: string;
  entries: {
    task_no: number;
    thread_ids: string[];        // 이 과제에 연결된 지시 스레드
    turn_refs: {                 // 과제 관련 언급 전체(스레드 노드 포함 — 과제 타임라인·"언급 0회" 통계용)
      tid: string; meeting_id: string; date: string;
      grade: "explicit" | "topic" | "ai_inferred";   // explicit = 과제명·순번 직접 언급
      grade_evidence?: string;
    }[];
  }[];
}
```

- 매핑 판정은 **Turn 단위**(스레드와 동일한 3단: 과제명 직접 언급 → 키워드 → LLM, 근거 배지 원칙 동일)
- 매핑이 없는 과제도 entries에 빈 배열로 포함한다 — "국무회의 언급 0회"는 그 자체로 기록이다
- 평가 금지 원칙(SPEC.md §1-5) 유지: 이행률·달성도 산출 금지. 노출은 상태 사실만("관련 발언 N건 · 마지막 부처 보고 YYYY-MM-DD · 후속 대기 N일째")
- **부처 브리핑(SPEC.md §0)은 파이프라인 산출물이 아니다** — 웹이 turns·task_map에서 빌드 시 파생(결정적). 후속 과제(P7 후보): 대통령 지시 턴의 수신 부처 LLM 태깅으로 호명 없는 지시의 재현율 보강

### 2.5 의제 뷰 (Agenda View) — 2026-07-21 방향 확정

홈 "지금 활발한 의제" 섹션(SPEC.md §6.1)용 파생 인덱스. 스레드를 **기간 창 × 분야**로 자르고 기간별 "흐름 브리프"를 붙인다. 2층 설계가 원칙: **분야 칩은 룰(결정적·멱등), 흐름 브리프는 AI(매 실행 전량 재생성)** — 룰의 경직성은 브리프가 보완하고, AI 서술의 불안정성은 원문 재생 링크가 보완한다.

```typescript
// data/fields.json — 분야 매핑 테이블. 정적 룰이며 사람이 PR로만 갱신한다(LLM 자동 수정 금지)
interface FieldTable {
  fields: { id: string; label: string; keywords: string[] }[];  // 7±1개 굵은 분야(경제·물가, 과학기술, …)
  proposals?: { field_id: string; keyword: string; reason: string; thread_id: string }[];
  // proposals = 12 agenda_view.py가 미분류 스레드를 보고 남기는 "키워드 추가 제안".
  // 적용은 사람이 keywords로 옮기는 PR로만 — 룰은 결정적으로 유지하되 룰 자체는 진화시킨다
}

// data/index/agenda.json — 12 agenda_view.py 산출
interface AgendaIndex {
  generated_at: string;
  ref_date: string;                    // 기간 창 기준일 = 최신 회의 날짜 (실행일 아님 — 수집 공백 왜곡 방지)
  fields: { id: string; label: string; thread_count: number }[];   // "미분류(etc)" 포함 필수
  threads: {
    id: string; title: string; stage: string;
    field_ids: string[];               // 키워드 매칭 분야(최대 2). 미매치면 ["etc"] — 숨기지 않는다
    node_dates: string[];              // 기간 창(4주/3개월/6개월) 필터·집계는 프론트 클라이언트 계산
    seed: { date: string; quote: string; speaker: string | null;   // 스레드를 연 explicit 지시 발화
            meeting_id: string; youtube_id: string; t: number };   // t = rep_sid start_sec - 3(어긋남 여유)
    latest: { date: string; speaker: string | null; rel_label: string;
              meeting_id: string; youtube_id: string; t: number }; // 최신 노드(최근 응답)
  }[];
  briefs: { window_days: 28 | 90 | 180;
            items: { text: string; thread_ids: string[] }[] }[];   // 항목당 근거 thread_ids ≥1 필수
}
```

- 분야 매칭은 `topic_tags + title` 키워드 포함 검사만(결정적). 미분류율이 커지는 것 자체가 fields.json 갱신 신호이므로 미분류를 반드시 **노출**한다
- **Thread.title 생성 규칙 상향**(07 threads.py): 시드 지시 발화 범위 내 **명사형 의제문 25자 내외**(예: "유가 급등 대응 방안 마련과 소관 부처 지정"). 발화에 없는 내용 추가 금지. 기존 스레드 title은 1회 백필. title은 AI 산출이므로 웹 노출 시 AiLabel 대상
- 흐름 브리프: 기간 창 안에서 움직인 스레드 목록(제목·태그·노드 수·신규 여부)을 입력으로 LLM이 3~5항목 생성. 매 실행 전량 재생성(누적 편집 없음), 항목마다 thread_ids 필수, 웹은 "AI 요약 · 원문 대조 필요" 라벨 고정
- seed.quote = 시드 explicit 노드의 grade_evidence. speaker는 Turn 화자(inferred — 웹은 "AI 추정" 병기)

## 3. 상태 머신 (핵심)

`data/state/videos.json`의 영상별 상태:

```
discovered ──자막 확인──▶ waiting_captions ──자막 생성됨──▶ captioned ──가공 완료──▶ processed
                              │ (매 실행 재시도)                                        │
                              │ 7일 경과                                    실패 단계 존재 ▼
                              ▼                                                    partial
                        captions_missing ──(옵션) whisper 폴백──▶ captioned
```

### 3.1 감지 (매 실행)

1. KTV 채널 RSS 파싱(최신 15개) → 제목 정규식 `국무회의|업무보고` 매치 → 미등록 youtube_id면 `discovered` 등록
2. 보조: korea.kr 국무회의 목록 크롤 → RSS에서 못 잡은 회의(제목 표기 상이)를 영상 검색으로 역추적. 실패 시 `state`에 `korea_kr_only` 플래그로 기록만
3. 시민 제보(`missing_video` 기여, SPEC.md §13) → 제목 필터 통과 시 `discovered` 등록

### 3.2 자막 폴링

- `discovered`/`waiting_captions` 대상: yt-dlp로 한국어 자동자막 존재 확인 → 있으면 다운로드 후 `captioned`, 없으면 `waiting_captions` 유지 + `retry_count` 증가
- 일 3회 실행이므로 방송 익일 06:00까지 대부분 포착. 사이트에는 `waiting_captions` 회의를 "자막 대기" 배지로 노출(숨기지 않음)

### 3.3 만료

- 최초 감지 후 **7일** 경과 시 `captions_missing` → Actions 로그 경고

### 3.4 whisper 폴백 (옵션, 기본 off)

- 환경변수 `ENABLE_WHISPER_FALLBACK=1`일 때만: `captions_missing` 영상의 오디오를 faster-whisper(medium)로 배치 전사 → `captioned`로 재진입. text_raw 출처를 `"whisper"`로 기록

## 4. 가공 단계 (captioned → processed)

| # | 스크립트 | 계약 |
|---|----------|------|
| 02 | segment.py | vtt → Statement[](text_raw, start_sec). 종결어미+구두점 분할, 타임스탬프 = 문장 시작 cue |
| 03 | correct.py | §5 교정 루프. 배치 50문장/호출, **오인식 교정만** — 의미 변경·요약·생략 금지. diff 없으면 corrected=false |
| 04 | turns.py | Turn 경계 탐지: 사회자 소개 발화 정규식(`다음은.*(장관|위원장|처장|청장)의?.*(보고|말씀)`) + 화자 전환 단서 LLM 판정 → Turn 생성 + 화자 부여(확신 낮으면 null, inferred=true 고정) + rep_sid 선정(가장 정보량 많은 문장 LLM 선택) |
| 05 | agenda.py | 화제 전환점 LLM 분할(official=false)이 기본이자 충분 조건. korea.kr 안건 앵커 매핑(official=true)은 선택 보강 — 구두 지시가 공식 문서에 선행할 수 있으므로 발화 기록을 1차 소스로 삼는다(2026-07-21 결정, 필수 아님) |
| 06 | summarize.py | **Agenda 단위** 요약 → 전체 brief(5문단 이내, 문단별 근거 sid 배열) |
| 07 | threads.py | 3단 판정(SPEC.md §8.2의 룰→키워드→LLM 동일)을 **Turn 단위**로 수행. 신규 스레드 생성은 대통령 화자 Turn의 명령형 발화에서만 |
| 08 | build_index.py | 검색 샤드·keywords·meetings 목록·dump 생성 |
| 09 | alerts.py | 키워드 알림 매칭 + Resend 발송 + RSS 정적 생성 |
| 10 | merge_contributions.py | 시민 기여 3인 합의 머지(SPEC.md §13.2) — Turn 단위 화자 라벨은 tid 대상 |
| 11 | task_map.py | §2.4 과제 매핑 — 신규 Turn·Thread × tasks.json 3단 판정 → tasks/map.json 갱신. 전 과제 entries 포함(빈 배열 유지) |
| 12 | agenda_view.py | §2.5 의제 뷰 — 결정적 부분(분야 매칭·seed/latest 조인·node_dates)은 코드로, 흐름 브리프만 LLM. 미분류 스레드에 대한 fields.json 키워드 제안(proposals) 기록 |

## 5. 자막 지속 보강 루프

### 5.1 원칙
`text_raw` 영구 보존 = 교정은 **멱등·반복 가능** 작업. 언제든 더 나은 교정으로 재실행할 수 있다.

### 5.2 용어집 (`data/glossary.json`)
- 구조: `{ "보금복 지부": "보건복지부", "숨문 위기": "숨은 위기", ... }` + 인명·부처·정책명 사전
- 축적: 03 교정에서 확정된 치환쌍 자동 추가(빈도 2회 이상) + 시민 교정(§13) 채택분 추가
- 사용: 03 교정 프롬프트에 주입 → 회차가 갈수록 품질 자동 상승

### 5.3 재보강 배치 (월 1회, 별도 workflow)
- 대상: 과거 회의 중 corrected=false 비율이 높거나 용어집 갱신 이후 미재처리 건
- 동작: 03 재실행 → diff 있는 문장만 갱신(history에 via:"pipeline" 기록)
- korea.kr 공식 원고가 존재하는 회의는 대조 교정을 우선 적용

## 6. LLM 사용 규칙

- 모델: claude-sonnet 계열 고정. 호출마다 `usage.json`에 (단계, 토큰, 비용 추정) 누적
- 재시도: 실패 시 3회 → 그래도 실패면 해당 산출물만 null로 두고 진행(예: summary=null이어도 meeting은 배포)
- 프롬프트는 `/pipeline/prompts/*.md`로 버전 관리 — 코드에 하드코딩 금지

## 7. 산출 검증 (매 실행 마지막, validate.py)

1. 모든 Statement.sid 유일 + turn_id/agenda_id가 실존 참조
2. Turn.sid_range·AgendaBlock.sid_range가 겹치지 않고 전 문장을 커버
3. text_raw 비어있는 문장 0건
4. thread_refs의 grade 값이 3종 enum 내
5. agenda.json: 전 스레드 포함, field_ids가 fields.json에 실존(또는 "etc"), seed/latest의 meeting_id·youtube_id 실존, briefs 각 항목 thread_ids ≥1
6. 검증 실패 → 해당 meeting을 `partial`로 강등하고 커밋은 진행(무너지지 않는 실패)

## 8. 실패 규칙

- 단계 실패: 해당 회의만 `partial`/`failed` 기록, 다른 회의 처리 계속, 다음 실행에서 실패 단계부터 재시도
- 전체 크래시 방지: run_all.py는 회의별 try/except 격리
- 알림: Actions 실패 로그만(별도 알림 시스템 만들지 않음)

## 9. 구현 Phase

### Phase P1 — 감지 + 자막 상태 머신 (최우선)
- [ ] RSS 감지 + state/videos.json + yt-dlp 폴링 + 일 3회 cron
- [ ] 02 segment → 최소 Meeting JSON(문장만, 층 없이) 산출
- ✅ 신규 영상 업로드 → 자막 생성 전엔 waiting_captions 유지 → 생성 후 다음 실행에서 자동 처리
- ✅ 기존 28개 회의 전체 백필 완료

### Phase P2 — 교정 + 용어집
- [ ] 03 correct + glossary 축적 + validate
- ✅ 샘플 회의에서 "보금복 지부"류 오인식이 교정되고 text_raw 보존 확인
- ✅ 동일 입력 재실행 시 결과 불변(멱등성)

### Phase P3 — 3층 구조 (Turn·Agenda)
- [ ] 04 turns + 05 agenda + rep_sid
- ✅ 전 문장이 정확히 하나의 Turn·Agenda에 속함(validate 통과)
- ~~korea.kr official=true 매핑 확인~~ → 2026-07-21 필수 해제: LLM 분할(official=false)만으로 완료 인정

### Phase P4 — 요약·스레드·색인·알림
- [ ] 06~09 + 월간 재보강 workflow
- ✅ 신규 회의 무개입 전체 처리(감지→배포) 3회 연속 성공

### Phase P6 — 국정과제 축 (2026-07-21 추가)
- [ ] tasks/tasks.json 마스터 구축(korea.kr/govVision 123과제: 목표·전략·과제명·주관 부처)
- [ ] 11 task_map.py + run_all 편입 + validate(전 123과제 entries 존재, task_no 유효 범위)
- ✅ 임의 과제 3개에서 매핑 turn_refs의 rep_sid 인용이 실제 관련 발언인지 수동 확인
- ✅ 백필: 기존 33개 회의 전체에 대해 map.json 생성

### Phase P7 — 의제 뷰 (2026-07-21 추가)
- [ ] fields.json 초안(7±1분야 — 미분류율 20% 이하 목표) + 12 agenda_view.py + run_all 편입 + validate §7-5
- [ ] 07 threads.py title 의제문 규칙 상향 + 기존 스레드 title 1회 백필
- ✅ agenda.json 임의 스레드 3개의 seed 재생 링크가 실제 지시 발화 구간인지 수동 확인
- ✅ 동일 입력 재실행 시 briefs 제외 산출 불변(결정적 부분 멱등)

### Phase P5 — 시민 기여 머지
- [ ] 10 merge_contributions (SPEC.md §13 계약)
- ✅ 3인 합의 → 반영 + history 기록, 불일치 → held 확인
