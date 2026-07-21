# Open Policy 2.0 — 구현 설계서 (SPEC.md) · 트랙 B: 웹 앱

> 이 문서 하나로 웹 앱 구현이 가능하도록 작성된 자기완결형 설계서입니다.
> 대상: Claude Code (자율 작업 전제) · 사람 검토자
> 버전: 1.5 (2026.07.21)

---

## 0. 작업 지시 요약 (Claude Code가 가장 먼저 읽을 것)

- **2트랙 병렬 개발 체제.** 트랙 A(수집·자막 파이프라인)는 별도 문서 **SPEC-PIPELINE.md**를 따르는 별도 모델이 개발한다. 이 문서(트랙 B)는 웹 앱만 담당한다. 두 트랙의 유일한 접점은 `/data` JSON 계약이며, **스키마의 SSOT는 SPEC-PIPELINE.md §2**다(파이프라인이 쓰는 쪽이므로). 이 문서 §4·§8과 충돌하면 SPEC-PIPELINE.md가 우선한다. 트랙 B는 파이프라인 완성을 기다리지 않고 **샘플 fixture JSON**(계약 준수)으로 개발한다.
- 이 프로젝트는 **국무회의·국민업무보고 영상 아카이브 웹서비스**다. 유튜브 임베드 + 자막 데이터 기반.
- **Phase 순서대로 구현한다** (§10). 각 Phase는 독립 배포 가능해야 하며, 완료 기준(✅)을 모두 만족한 뒤 다음 Phase로 넘어간다.
- **금지 사항(§9)을 위반하는 코드를 작성하지 않는다.** 특히: 관계 그래프 시각화 금지, 근거 배지 없는 연결 UI 금지.
- **수익화(광고·Pro 구독)는 §12 규칙 안에서만 구현한다.** 시민 기본 기능(검색·시청·스레드 열람·오픈데이터)은 영구 무료다. **결제 연동은 "구현 예정"이다(§12.4)** — PG·인앱결제 심사 승인이 필요해 PoC/MVP 단계와 갭이 있으므로, MVP에서는 결제 버튼을 스텁("출시 준비 중")으로 두고 실제 과금 코드를 작성하지 않는다.
- 모든 데이터는 `/data` 디렉토리의 JSON 파일이 단일 진실 원천(SSOT)이다. 별도 DB 서버를 세우지 않는다.
- 모호한 부분은 이 문서의 철학(§1)에 비추어 판단하고, 판단 근거를 커밋 메시지에 남긴다.
- **[2026-07-21 방향 확정] 부처 브리핑**: 실무 공무원용 파생 뷰 `/briefing/[id]` — 회의×부처로 자른 **지시사항(대통령 턴)·답변사항(해당 부처 화자 턴)**. 항목 판정은 웹 빌드 시 결정적 계산만(화자 부처 매칭 + 발언 내 부처 호명 + 과제 매핑 소관 — LLM 추가 없음), 항목마다 근거 표기. 개조식(□/○) 복사 제공하되 **"AI 추출 초안 · 원문 대조 필수" 라벨 고정**, 조치계획 칸은 만들지 않는다(§1-5 평가 금지 — 그건 공무원의 일). 화면은 2단: 좌 발췌 목록(항목 체크로 포함/제외 + 구간 재생 검증) / 우 복사 미리보기(체크된 항목만 개조식 실시간 반영 = 복사될 텍스트 그대로, 전체 복사 버튼 하나). 열람·복사 무료. (2026-07-21 사용자 결정: 이메일 발송·부서 키워드 필터는 만들지 않는다.)
- **[2026-07-21 방향 확정] 국정과제 축**: 서비스의 상위 프레임은 이재명 정부 123대 국정과제다(데이터 계약: SPEC-PIPELINE.md §2.4, `data/tasks/`). 구조는 국정과제 ⊃ 스레드 ⊃ 발언. 과제별 트래커 화면과 **부처별 뷰**(tasks.json ministries 피벗)를 스레드 화면(Phase 3)과 함께 설계한다. 노출은 상태 사실만("관련 발언 N건 · 마지막 보고 날짜 · 후속 대기 N일째" · "언급 0회") — §1-5 평가 금지 원칙 유지.

---

## 1. 설계 철학 (판단 기준)

**"연결은 해석이 아니라 각주다."** 아카이브는 기록을 보존하고 판단은 사용자가 한다.

1. **근거 없는 연결은 없다** — 회의·발언 간 모든 연결 UI에는 연결 등급 배지(§5.4)를 필수 표기
2. **종착점은 언제나 원문 영상** — 요약·스레드·알림·API 응답까지, 모든 파생물은 원문 구간 재생 링크로 끝난다
3. **시간축을 벗어나지 않는다** — 관계는 시간순(과거→미래)으로만 표현. 그래프/네트워크 시각화 금지
4. **새 문법을 만들지 않는다** — UI 패턴은 유튜브 문법(그리드·워치·재생목록·관련영상·답글 칩)만 차용
5. **평가하지 않는다** — 서비스 카피에 성과/실패/미흡 등 평가 어휘 금지. 상태 어휘(보고됨/예정/연결됨/대기)만 사용
6. **AI 산출물엔 라벨** — AI가 만든 모든 것에 표기: `AI 요약`, `화자 AI 추정`, `≈ AI 추정`
7. **비용 상한** — 무료 티어 + 월 LLM 수만 원을 넘는 설계 금지. 실시간 처리 금지(배치만)
8. **기록과 광고를 분리한다** — 광고는 기록(발언 인용·스레드·자막 패널) 내부에 진입할 수 없다. 수익화가 기록의 중립성을 건드리는 순간 아카이브가 아니다 (§12)

---

## 2. 기술 스택 (고정)

| 레이어 | 선택 | 비고 |
|--------|------|------|
| 프론트 | Next.js 14+ (App Router) + TypeScript | Vercel 배포, SSG 우선 |
| 스타일 | CSS Modules 또는 vanilla-extract | Tailwind 사용 금지(토큰 직접 관리, §5) |
| 데이터 | 정적 JSON (`/data`) → 빌드 시 로드 | Git = DB = 오픈데이터 덤프 |
| 검색 | 클라이언트: MiniSearch(BM25 계열) / 규모 초과 시 Meilisearch Cloud 무료 티어 | 3.5만 문장은 클라이언트로 충분. 색인 파일 5MB 초과 시 서버 검색 전환 |
| 파이프라인 | Python 3.11 스크립트 (`/pipeline`) + GitHub Actions cron | 일 1회 06:00 KST |
| 자막 수집 | yt-dlp | KTV 유튜브 채널 |
| LLM | Anthropic API (claude-sonnet 계열) — 요약·교정·관계추정 배치 전용 | 호출량 로그 필수 |
| 영상 재생 | YouTube IFrame Player API | `?t=` 구간 이동, 자체 호스팅 금지 |
| 알림 발송 | GitHub Actions + Resend 무료 티어(이메일) / 정적 RSS 생성 | 웹훅은 Phase 5 후순위 |
| 베타 폼 | 정적 폼 + Supabase (`beta_signups`) | |
| 인증 | Supabase Auth — 이메일 매직 링크 단일 | Pro 구독자 전용. 시민 기능은 로그인 없이 전부 사용 가능 |
| 결제 | 토스페이먼츠 정기결제 (구독 단일 플랜) | **구현 예정(§12.4)** — PG 심사 승인 후. MVP는 스텁만 |
| 광고 | Google AdSense 1구좌 | §12.1의 배치 규칙 엄수 |

---

## 3. 저장소 구조

```
open-policy/
├─ SPEC.md                  # 이 문서
├─ data/                    # ★ SSOT — 파이프라인이 쓰고 프론트가 읽는다
│  ├─ meetings/             # 회의당 1파일: {meeting_id}.json
│  ├─ threads/              # 스레드당 1파일: {thread_id}.json
│  ├─ index/
│  │  ├─ meetings.json      # 회의 목록 (경량 메타)
│  │  ├─ search-{n}.json    # 검색 색인 샤드 (문장)
│  │  └─ keywords.json      # 키워드별 문장 카운트
│  └─ dump/latest.json      # 전체 덤프 (오픈데이터 = API /v1/dump/latest 원본)
├─ pipeline/
│  ├─ 01_collect.py         # yt-dlp 자막+메타 수집
│  ├─ 02_segment.py         # 문장 분할 + 타임스탬프
│  ├─ 03_correct.py         # LLM 오인식 교정 (원문 보존)
│  ├─ 04_summarize.py       # 챕터 분할 + 요약
│  ├─ 05_speakers.py        # 화자 추정
│  ├─ 06_threads.py         # 스레드 연결 (룰→키워드→LLM)
│  ├─ 07_build_index.py     # 검색 색인 + keywords + dump 생성
│  ├─ 08_alerts.py          # 키워드 알림 매칭 + 이메일/RSS 생성
│  └─ run_all.py            # 전체 오케스트레이션 (실패 시 §8.3 규칙)
├─ app/                     # Next.js
│  ├─ page.tsx              # ① 홈
│  ├─ watch/[id]/page.tsx   # ② 시청
│  ├─ threads/[id]/page.tsx # ③ 스레드
│  ├─ data/page.tsx         # ④ 오픈데이터
│  ├─ pro/                  # ⑤~⑧ Pro 베타
│  │  ├─ alerts/page.tsx
│  │  ├─ report/page.tsx
│  │  ├─ api-docs/page.tsx
│  │  └─ beta/page.tsx
│  └─ api/v1/               # §7 API 라우트 (정적 JSON 서빙 래퍼)
├─ components/              # §5.5 공통 컴포넌트
├─ styles/tokens.css        # §5.1 디자인 토큰 (유일한 색 정의처)
└─ .github/workflows/daily.yml
```

---

## 4. 데이터 스키마 (TypeScript 타입 겸용)

> ⚠️ **SSOT 이관**: 스키마의 확정본은 **SPEC-PIPELINE.md §2**다. 그쪽은 문장 위에 **Turn(화자 턴)·Agenda(의제 구간) 겹층**을 추가한 3층 구조(Statement–Turn–Agenda)로 확장되었다: 화자는 Turn에만 존재(Statement는 turn_id로 역참조), chapters는 agenda[]로 승격, 스레드 노드는 tid+rep_sid 참조, pipeline_status에 waiting_captions·partial 추가. 아래 4.1은 참고용 구버전이며 충돌 시 SPEC-PIPELINE.md를 따른다. 프론트 구현 시 fixture도 그쪽 스키마로 만들 것.

### 4.1 Meeting — `data/meetings/{id}.json` (구버전 참고용)

```typescript
interface Meeting {
  id: string;                    // 예: "2026-rpt-0716-imQ8RH", "2026-cab-30"
  kind: "cabinet" | "report";    // 국무회의 | 국민업무보고
  title: string;
  date: string;                  // "2026-07-16" (KST)
  youtube_id: string;
  duration_sec: number;
  source: { video: string; text?: string };   // 원본 URL (KTV, korea.kr)
  summary: { brief: string; generated_at: string; model: string } | null;  // AI 요약
  chapters: { start_sec: number; title: string }[];
  statements: Statement[];
  stats: { statement_count: number };
  pipeline_status: "done" | "pending" | "failed";  // §8.3
}

interface Statement {
  sid: string;                   // "{meeting_id}#{seq}" 전역 유일
  start_sec: number;
  text: string;                  // 교정본 (표시 기본값)
  text_raw: string;              // 자동자막 원문 (교정 전, 반드시 보존)
  corrected: boolean;
  speaker: { name: string; inferred: boolean; verified: boolean } | null;
  // inferred=true → "화자 AI 추정" 라벨 · verified=true → "✓ 시민 검증" 라벨 (§13, verified가 inferred보다 우선 표시)
  text_verified: boolean;        // 교정문이 시민 3인 합의를 거쳤는지 (§13)
  history: { field: "speaker"|"text"; prev: string; at: string; via: "pipeline"|"citizen" }[];
  // 갱신 이력 — text_raw 보존 원칙의 확장. 시민 기여 반영 시 필수 기록
  thread_refs: { thread_id: string; grade: LinkGrade }[];  // 이 문장이 속한 스레드
}

type LinkGrade = "explicit" | "topic" | "ai_inferred";
```

### 4.2 Thread — `data/threads/{id}.json`

```typescript
interface Thread {
  id: string;                    // 예: "ai-crisis-detection"
  title: string;                 // "AI 위기가구 발굴"
  topic_tags: string[];
  stage: "order" | "plan" | "progress" | "result" | "followup_pending";
  nodes: ThreadNode[];           // start(date, sec) 오름차순 정렬 필수
  followup: { expected: string; note: string } | null;  // 예정 노드
  updated_at: string;
}

interface ThreadNode {
  sid: string;                   // Statement 참조
  meeting_id: string;
  date: string;
  role: "order" | "report" | "interim" | "result";  // 노드 색 결정 (§5.2)
  grade: LinkGrade;              // 직전 노드와의 연결 근거
  grade_evidence: string;        // 근거 원문 (예: 발언 중 "지난 2월 지시하신")
  reviewed: boolean;             // ai_inferred 검수 여부. false → UI에 "검수 대기"
  rel_label: string;             // "지시에 대한 추진 계획 보고" 등
}
```

### 4.3 검색 색인 — `data/index/search-{n}.json`

```typescript
// 문장 배열 샤드 (회의 10개 단위). MiniSearch 필드: text, speaker_name
interface SearchDoc {
  sid: string; text: string; speaker_name: string;
  meeting_id: string; meeting_title: string; date: string; start_sec: number;
}
```

### 4.4 알림 구독 — 무료/Pro 이원화

- **무료(비로그인)**: 키워드 구독은 localStorage + URL 공유(`/pro/alerts?kw=...`). 사이트 내 피드·RSS만 제공, 이메일 발송 없음
- **Pro(로그인)**: Supabase `subscriptions`에 저장, 이메일 다이제스트·웹훅 발송 대상

```sql
create table subscriptions (
  user_id uuid references auth.users not null,
  keywords text[] not null default '{}',      -- 최대 20개 (무료는 10개, UI에서 제한)
  thread_ids text[] not null default '{}',    -- 리포트 구독 스레드
  email_digest boolean default true,
  webhook_url text,
  plan text not null default 'pro',           -- 'pro' 단일
  plan_status text not null default 'active', -- active | past_due | canceled
  billing_key text,                            -- 토스페이먼츠 빌링키
  primary key (user_id)
);
-- RLS: 본인 행만 select/update
```

### 4.5 베타 신청 — Supabase `beta_signups`

```sql
create table beta_signups (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  org_type text not null,       -- 언론/공공/기업/학계/시민단체/일반
  keywords text,
  wanted_feature text,
  created_at timestamptz default now()
);
-- RLS: anon insert only (select 불가)
```

### 4.6 시민 기여 — Supabase `contributions` (§13)

```sql
create table contributions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  kind text not null,            -- 'speaker_label' | 'text_correction' | 'missing_video'
  target_sid text,               -- speaker_label / text_correction 대상 문장
  payload jsonb not null,        -- {speaker:"보건복지부 장관"} | {text:"교정문"} | {url:"..."}
  status text not null default 'pending',  -- pending | merged | rejected | held
  created_at timestamptz default now()
);
create table contributor_stats (
  user_id uuid primary key references auth.users,
  points int not null default 0,          -- 채택 시 적립 (§13.3)
  merged_count int default 0,
  rejected_count int default 0,
  trust text not null default 'normal'    -- normal | limited(적립 정지) 
);
-- RLS: contributions는 본인 insert/select만. 합의 판정·머지는 파이프라인(service role)이 수행
```

---

## 5. 디자인 시스템

**기준: 유튜브 다크 테마.** 이 서비스의 UI 문법(§5.3)뿐 아니라 색·타이포·형태 토큰도 유튜브 다크 테마 실측값에 정합시킨다. 사용자가 "유튜브 같다"고 느끼는 것이 목표이며, 유튜브에 없는 개념(발언 성격·연결 등급·인용)만 확장 토큰으로 정의한다.

### 5.1 토큰 — `styles/tokens.css` (색은 반드시 여기서만 정의)

```css
:root {
  /* ── 유튜브 다크 테마 실측 정합 ── */
  --bg:#0F0F0F;        /* 유튜브 다크 배경 */
  --card:#212121;      /* 유튜브 상승 표면 (설명란·카드) */
  --card-sub:#272727;  /* 유튜브 칩·버튼 배경 */
  --hover:#3F3F3F;     /* 유튜브 호버 표면 */
  --line:#303030;      /* 유튜브 구분선 */
  --txt:#F1F1F1;       /* 유튜브 본문 텍스트 */
  --dim:#AAAAAA;       /* 유튜브 보조 텍스트 */
  --red:#FF0033;       /* 유튜브 브랜드 레드 — 브랜드·LIVE·재생바·[지시] */
  --blue:#3EA6FF;      /* 유튜브 다크 링크 블루 — 링크·타임스탬프·구간재생·[보고] */
  /* ── 확장 토큰 (유튜브에 없는 개념) ── */
  --green:#57D9A3;     /* [결과]·등급 "발언 명시"·시민 검증 */
  --amber:#FFD08E;     /* 발언자명·하이라이트·등급 "AI 추정"·재생바 ◆마커 */
  /* ── 형태 (유튜브 실측) ── */
  --r-thumb:12px;      /* 썸네일 (유튜브 동일) */
  --r-card:12px;       /* 카드 */
  --r-chip:8px;        /* 필터 칩 (유튜브 동일) */
  --r-pill:18px;       /* 버튼 pill (유튜브 동일) */
  --r-badge:4px;       /* 재생시간·등급 배지 (유튜브 duration 배지 동일) */
}
```

### 5.2 색-의미 매핑 (하드코딩 금지, 이 표대로만)

| 의미 | 색 | 적용처 |
|------|-----|--------|
| 대통령 지시 (role=order) | red | 스레드 노드 보더, `지시` 태그 |
| 부처 보고 (report/interim) | blue | 노드 보더, `계획 보고`/`중간 보고` 태그 |
| 이행 결과 (result) | green | 노드 보더, `이행 보고` 태그 |
| 예정/미래 | dashed #555 + opacity .6~.75 | 점선 보더, 색 사용 금지 |
| 등급 explicit | green 배지 `✓ 발언 명시` | |
| 시민 검증 | green 배지 `✓ 시민 검증` | 3인 합의 반영분(§13). explicit과 같은 green — "사람이 확인한 근거" 계열 |
| 등급 topic | blue 배지 `# 주제 연결` | |
| 등급 ai_inferred | amber 배지 `≈ AI 추정` | |

### 5.3 타이포그래피

- 본문/UI: **Roboto + Pretendard** 페어(`font-family: Roboto, 'Pretendard Variable', Pretendard, sans-serif`) — 유튜브 본문 서체(Roboto)를 라틴·숫자에 그대로 쓰고 한글만 Pretendard로 폴백. 크기·굵기 스케일도 유튜브 기준: 영상 제목 16px/500, 메타 12px/400, 칩 14px/500
- 발언 인용 **전용**: **Noto Serif KR** — Statement.text를 표시할 때만. AI 요약·시스템 문구에 명조 사용 금지. **유튜브에서 의도적으로 이탈하는 유일한 지점**이며, "이것은 UI가 아니라 기록"임을 서체로 구분하는 장치이므로 이탈로 취급하지 않는다
- 타임스탬프: `--blue` · Roboto 500 · `font-variant-numeric: tabular-nums` (유튜브 챕터 링크와 동일 처리)

### 5.3.1 유튜브 정합 규칙

- 상호작용 패턴은 유튜브 다크 테마의 실제 동작을 따른다: 칩·버튼 호버 = `--hover` 배경, 카드 호버 = 배경 변화 없이 썸네일만 미세 반응, 버튼은 pill(`--r-pill`)
- 재생시간 배지: 우하단, `rgba(0,0,0,.8)`, `--r-badge`, Roboto 500 12px (유튜브 동일)
- 판단이 애매한 컴포넌트는 "유튜브 다크 테마라면 어떻게 생겼을까"를 기본값으로 삼고, 유튜브에 대응물이 없을 때만 §5.1 확장 토큰으로 신규 설계한다
- 단, 유튜브의 광고·쇼츠·추천 알고리즘 UI는 참고 대상에서 제외(§12.1 광고 규칙이 우선)

### 5.4 필수 컴포넌트 계약 (components/)

| 컴포넌트 | Props | 규칙 |
|----------|-------|------|
| `<GradeBadge grade>` | LinkGrade | §5.2 색·문구 고정. 연결 UI에 이 컴포넌트 없이 연결 표시 금지 |
| `<PlayLink sid>` | sid → meeting+sec 해석 | 렌더: `▶ {mm:ss} 구간 재생`. 모든 파생 콘텐츠의 마지막 요소 |
| `<AiLabel type>` | "summary"\|"speaker"\|"link" | "AI 요약"/"화자 AI 추정"/"≈ AI 추정" |
| `<AiNotice/>` | — | 고지 문구. ai_inferred 요소가 1개라도 있는 패널 하단에 자동 삽입: "연결 관계 중 'AI 추정'은 오류가 있을 수 있습니다. 모든 연결은 원문 구간 재생으로 직접 확인할 수 있습니다." |
| `<QuoteText text raw>` | 교정본+원문 | 명조 렌더. corrected=true면 ⓘ 툴팁으로 text_raw 열람 제공 |
| `<ThreadStrip thread currentMeetingId>` | | 가로 재생목록 문법. 현재 회의 = red 보더 |
| `<MeetingCard meeting>` | | 16:9 썸네일(유튜브 mqdefault), 재생시간 배지 우하단, kind 배지 좌상단 |

### 5.5 시안 참조

확정 시안 7장이 레이아웃 기준: concept-D-영상아카이브형(홈·시청), concept-D-발언스레드, concept-D-시청화면-과거연결(시청 최종), Pro-⑤~⑧. 단 시안의 색·radius는 구버전 토큰이므로 **§5.1 유튜브 정합 토큰이 우선**한다(예: 시안의 card #1C1C1E → #212121로 구현). 시안과 이 문서가 충돌하면 항상 이 문서가 우선.

---

## 6. 화면 명세

### 6.1 ① 홈 `/`

- 헤더: 로고(開 red 마크) + 통합 검색바 + LIVE 배지(당일 생중계 있을 때만)
- 필터 칩: 전체/국무회의/업무보고 + 인기 키워드(keywords.json 상위) + 주요 발언자. 다중 선택 아님(단일 토글)
- 영상 그리드: 3열(≥1024px)/2열/1열. MeetingCard, 최신순. pipeline_status≠done인 회의는 "처리 대기" 배지로 노출(숨기지 않음)
- 검색 실행 → `/search?q=` 결과 페이지: 문장 카드(명조 인용 + 하이라이트 + PlayLink + 회의 메타). 검색은 MiniSearch 클라이언트

### 6.2 ② 시청 `/watch/[id]`

- 좌 1.9fr / 우 1fr (모바일: 세로 스택, 자막 패널은 플레이어 아래)
- 플레이어: YouTube IFrame. 재생바 위에 ◆ amber 마커 = thread_refs 있는 문장 위치 (IFrame 제약으로 커스텀 바 오버레이 구현)
- 플레이어 하단 순서: 제목/메타 → **ThreadStrip**(이 회의 문장이 스레드에 속할 때만) → AI 요약 카드(`<AiLabel summary>` + 요약 각 문단 끝 PlayLink) → 챕터 칩 → "이 회의로 이어진 과거 회의" 카드 행(GradeBadge + 인용 1문장 + PlayLink)
- 우측 자막 패널: 전 문장 스크롤 + 패널 내 검색(하이라이트+건수) + 현재 재생 문장 red 좌보더 자동 추적 + thread_refs 있는 문장엔 `↩ {rel_label}` 칩(GradeBadge 포함, 탭→스레드) + 하단 AiNotice
- 문장 클릭 → 해당 초로 시크

### 6.3 ③ 스레드 `/threads/[id]`

- 헤더: 태그 · 제목(명조) · "N개 회의에 걸친 발언 M건 · 관계는 AI 추정 포함, 원문 링크 제공"
- 진행 단계 바: 지시→계획→이행→후속 4단계. 완료 green / 현재 amber / 미도달 무채색
- 세로 타임라인: 노드 시간순, 색 §5.2, 각 카드 = 태그+날짜+발언자(amber)+명조 인용+PlayLink. 노드 사이 `↳ {rel_label}` + GradeBadge. reviewed=false → "검수 대기" 배지 추가
- followup 존재 시 마지막에 점선 예정 노드 + "알림 받기"(→ /pro/alerts로 키워드 프리셋 이동)
- 하단: 다른 스레드 카드 2열 (점 프리뷰: 노드 role 색 나열)

### 6.4 ④ 오픈데이터 `/data`

- dump/latest.json 다운로드 버튼 + 파일 크기/갱신일 + 스키마 문서(§4 표를 렌더) + CC BY 4.0 안내 + GitHub 저장소 링크

### 6.5 ⑤ Pro 알림 `/pro/alerts`

- **무료(비로그인)**: 키워드 최대 10개(localStorage), 사이트 내 피드 + RSS(`/rss/{kw}.xml` 정적 생성)만
- **Pro(로그인)**: 키워드 20개 + 이메일 다이제스트 + 웹훅. 잠긴 기능엔 🔒 + "Pro에서 제공" 표시(다크 패턴 금지 — 무료 기능을 가리거나 축소하지 않는다)
- 알림 피드: 구독 키워드 매칭 최근 7일 문장. 각 항목 = 키워드 배지 + kind 배지 + 메타 + 명조 인용(mark) + PlayLink + (thread_refs 있으면) 스레드 링크. 하단 자막 오인식 고지

### 6.6 ⑥ Pro 리포트 `/pro/report`

- 스레드 선택 → 주간 뷰: 요약 3칸(새 연결 N건 / 현재 단계 / AI 추정 검수 현황) → 이번 주 변화 타임라인(§6.3 축약형, NEW 배지) → 상태 줄: "지시 대비 이행 보고까지 N일 · **상태 기록이며 평가가 아닙니다**"(문구 고정) → 변화 없는 구독 스레드 목록("후속 대기 N일째" 배지)
- PDF 내보내기: 브라우저 print CSS로 구현(별도 라이브러리 금지)

### 6.7 ⑦ API 문서 `/pro/api-docs` 및 ⑧ 베타 신청 `/pro/beta`

- API 문서: §7 엔드포인트 표 + curl/응답 예시(코드블록) + 티어 안내(무료: 시간당 100회 / Pro: 5,000회 / 덤프는 무제한·무인증)
- 베타 신청: 폼(이메일*/소속유형*/키워드/기대기능) → Supabase insert → 완료 메시지 교체. 하단 고정 문구는 §11 사전 참조
- 베타 기간엔 Pro 전 기능 무료 개방, 결제 미가동. 베타 화면에 "정식 출시 시 Pro는 유료 전환(시민 기능은 영구 무료)"을 사전 고지 — 약속 후 조건 변경 금지

### 6.8 ⑨ Pro 요금 `/pro/pricing` (Phase 6)

- 2열 비교: **시민(무료·영구)** — 검색·시청·스레드·오픈데이터·알림 10개·RSS / **Pro(월 ₩9,900)** — 알림 20개·이메일 다이제스트·웹훅·리포트 PDF·API 5,000회/h
- 결제: 토스페이먼츠 정기결제(빌링키). 해지 즉시 가능, 남은 기간 유지, 환불 정책 명시
- 광고 제거는 Pro 혜택에 포함하지 않는다(광고 자체가 §12.1 규칙으로 이미 최소화 — "광고 제거 팔이" 금지)

---

## 7. API (`/api/v1/*` — 정적 JSON 서빙 래퍼, 무인증)

| 엔드포인트 | 동작 |
|-----------|------|
| `GET /v1/statements?q=&limit=&offset=` | 색인 샤드에서 검색. 응답 항목: text, text_raw, speaker{name,inferred}, meeting_id, timestamp(초), video_url(`youtu.be/{yid}?t={sec}`), thread{id,link_grade}? |
| `GET /v1/meetings` / `GET /v1/meetings/{id}` | index/meetings.json · meetings/{id}.json 그대로 |
| `GET /v1/threads/{id}` | threads/{id}.json 그대로 |
| `GET /v1/dump/latest` | dump/latest.json 리다이렉트 |

규칙: 응답에서 `inferred`·`link_grade` 필드 생략 금지(철학 6이 API까지 적용).

티어(Phase 6부터 적용, 그 전엔 전부 무제한):
- 무인증: 시간당 100회 (IP 기준, Vercel Edge에서 카운트)
- Pro 키(`op_live_...`): 시간당 5,000회. 키 발급·검증은 Supabase 조회
- `GET /v1/dump/latest`는 **영구 무인증·무제한** — 오픈데이터 약속은 과금 대상이 아니다

---

## 8. 파이프라인 명세

> ⚠️ **트랙 A로 분리됨**: 파이프라인은 **SPEC-PIPELINE.md**가 확정본이며 별도 모델이 개발한다(감지 RSS 방식, 일 3회 폴링, waiting_captions 상태 머신, 교정 용어집·월간 재보강, Turn/Agenda 생성 포함). 아래 내용은 구버전 참고용이고 충돌 시 SPEC-PIPELINE.md가 우선한다. 트랙 B가 파이프라인에서 알아야 할 것은 단 두 가지: ① `/data` 계약(SPEC-PIPELINE.md §2) ② pipeline_status별 UI 처리(`waiting_captions`="자막 대기" 배지, `partial`/`failed`="처리 대기" 배지, 모두 숨기지 않고 노출).

### 8.1 실행: GitHub Actions cron `0 21 * * *` (UTC = KST 06:00) → `python pipeline/run_all.py`

### 8.2 단계별 계약

| 스크립트 | 입력 → 출력 | 핵심 규칙 |
|----------|-------------|-----------|
| 01_collect | KTV 채널 신규 영상 → raw 자막(vtt)+메타 | 대상 판별: 제목에 "국무회의" 또는 "업무보고" 포함. 기존 처리분 스킵(meeting id 기준) |
| 02_segment | vtt → Statement[] (text_raw, start_sec) | 문장 분할: 종결어미+구두점 기준. 타임스탬프 = 문장 시작 cue |
| 03_correct | text_raw → text | LLM 배치(50문장/호출). 프롬프트 원칙: 오인식 교정만, 의미 변경·요약·생략 금지. diff 없으면 corrected=false |
| 04_summarize | statements → chapters + summary.brief | 챕터: 화제 전환점 추출. 요약: 5문단 이내, 각 문단에 근거 sid 배열 첨부(프론트가 PlayLink 생성) |
| 05_speakers | statements → speaker | 사회자 소개 발화("다음은 ○○부 장관")+문체 단서로 추정. 확신 낮으면 null. inferred=true 고정 |
| 06_threads | 신규 statements × 기존 threads | 3단 판정 — ①룰: 정규식(`지난\s*(회의\|[0-9]+월)`, `지시하신`, `말씀하신`) 매치 → explicit + grade_evidence=해당 구절 ②키워드: thread.topic_tags 2개 이상 포함 → topic ③LLM: 후보쌍(같은 태그 스레드 최근 노드)만 판정 → ai_inferred, reviewed=false. 신규 스레드 생성은 explicit 지시 발화(대통령 화자 + 명령형)에서만 |
| 07_build_index | 전체 → search 샤드 + keywords.json + dump | dump = meetings+threads 병합, 라이선스 필드 포함 |
| 08_alerts | 베타 명단 CSV × 신규 문장 | 키워드 매치 시 Resend 발송(매치 없으면 미발송) + `/public/rss/{kw}.xml` 갱신 |

### 8.3 실패 규칙 (무너지지 않는 실패)

- 단계 실패 시: 해당 회의 `pipeline_status: "failed"` 기록, **다른 회의 처리는 계속**, Actions 로그에 원인, 사이트에는 "처리 대기" 배지로 노출. 재실행 시 failed 건부터 재시도
- LLM 호출 실패: 3회 재시도 → 그래도 실패면 그 산출물만 null (예: summary=null이어도 배포는 진행)
- 월간 LLM 사용량 로그를 `pipeline/usage.json`에 누적. 상한 경고만, 자동 차단 없음

---

## 9. 금지 목록 (코드 리뷰 기준)

1. 관계 그래프·네트워크·마인드맵 렌더링
2. GradeBadge 없는 회의 간 연결 UI / inferred·link_grade 누락된 API 응답
3. PlayLink 없이 끝나는 요약·스레드·알림 콘텐츠
4. AI 생성 텍스트의 명조체 렌더 / AiLabel 누락
5. red·blue·green·amber의 §5.2 외 의미 사용, tokens.css 밖 색상 하드코딩
6. 평가 어휘("성과", "미흡", "지연 중" 등)를 서비스 카피에 사용 — "후속 대기 N일째"처럼 사실 서술만
7. §12 범위를 벗어난 수익화 — 시민 기본 기능(검색·시청·스레드 열람·오픈데이터·덤프 API) 유료화, 광고 2구좌 이상, 기록 영역(인용·스레드·자막 패널) 내 광고, 네이티브 광고·스폰서 콘텐츠, "광고 제거" 판매, 다크 패턴(무료 기능 은폐·해지 방해)
8. 실시간 STT/스트리밍 처리, 영상 자체 호스팅
9. 라이트 테마, Tailwind
10. text_raw 삭제(교정 원문은 영구 보존)

---

## 10. 구현 Phase 및 완료 기준

### Phase 1 — 기반 + 검색 (홈·시청·검색)
- [ ] `/data` 스키마 확정, 샘플 회의 2건 수작업 제작(2026-rpt-0716-imQ8RH 실데이터 참조)
- [ ] tokens.css + 공통 컴포넌트 7종(§5.4)
- [ ] 홈(그리드·필터·검색바) / 검색 결과 / 시청(플레이어·자막 패널·문장 클릭 시크)
- ✅ 검색어 입력 → 문장 결과 → 클릭 → 해당 영상 구간 재생까지 무중단 동작
- ✅ Lighthouse 모바일 성능 80+

### Phase 2 — 파이프라인 자동화
- [ ] pipeline 01~05, 07 + run_all + GitHub Actions
- ✅ 신규 회의 업로드 → 다음날 06:00 배치 → 사람 개입 0으로 사이트 반영
- ✅ 임의 단계 강제 실패 시에도 배포 성공 + "처리 대기" 노출 확인

### Phase 3 — 스레드
- [ ] 06_threads + 스레드 페이지 + 시청 화면 통합(Strip·과거 카드·↩칩·◆마커)
- [ ] 검수 UI: `data/threads` 파일의 reviewed 필드를 PR로 수정하는 운영 문서(별도 admin 화면 만들지 않음)
- ✅ 샘플 스레드 1개(지시→계획→이행)가 3화면(스레드/시청/홈)에서 상호 이동
- ✅ ai_inferred 노드에 검수 대기 배지 + AiNotice 자동 표시

### Phase 4 — 오픈데이터 + API
- [ ] /data 페이지, dump 생성, /api/v1 4종
- ✅ curl로 4개 엔드포인트 응답 확인, dump 다운로드 동작

### Phase 5 — Pro 베타
- [ ] /pro 4화면(§6.5~6.7) + 08_alerts + RSS 정적 생성 + Supabase 폼
- ✅ 키워드 등록 → 피드 표시 → RSS URL 구독 가능
- ✅ 베타 폼 제출 → Supabase 레코드 확인
- ✅ print CSS로 리포트 PDF 저장 동작

### Phase 6a — 수익화 기반 (MVP 범위: 결제 없이 구축 가능한 것)
- [ ] Supabase Auth(매직 링크) + subscriptions 테이블(billing_key는 null 유지)
- [ ] /pro/pricing(§6.8) — 결제 버튼은 스텁: 비활성 + "출시 준비 중 · 베타 기간 Pro 무료" 표기
- [ ] 알림·리포트·API의 무료/Pro 게이트 구조(플래그로 전환 가능하게) — 베타 중엔 전원 Pro 취급
- [ ] AdSense 1구좌 삽입(§12.1 배치 규칙) + 광고 라벨 — 광고는 심사 외 절차 없어 MVP 포함
- ✅ 비로그인 상태에서 시민 기능 전부(검색·시청·스레드·덤프) 이용 가능 회귀 테스트
- ✅ 광고가 기록 영역(§12.1 금지 위치)에 렌더되지 않음을 전 화면 확인

### Phase 6b — 결제 연동 (구현 예정: PG 심사 승인 후 착수, §12.4)
- [ ] 토스페이먼츠 빌링키 정기결제 + 해지·환불 흐름 + API 키 발급·rate limit 과금 적용
- ✅ 가입 → 결제 → Pro 활성 → 해지 → 만료 후 무료 전환 전체 흐름 동작
- ✅ 결제 활성화 전후로 무료 한도(§12.2 영구 무료 표)가 변하지 않음 확인

각 Phase 완료 시: 스크린샷 저장 + CHANGELOG.md 갱신 + 배포.

---

## 11. 카피 문구 사전 (그대로 사용)

| 위치 | 문구 |
|------|------|
| AiNotice | "연결 관계 중 'AI 추정'은 오류가 있을 수 있습니다. 모든 연결은 원문 구간 재생으로 직접 확인할 수 있습니다." |
| 자막 고지 | "발언 문장은 유튜브 자동자막 기반으로 오인식이 있을 수 있습니다. 원문 구간 재생으로 확인해 주세요." |
| 리포트 상태 | "상태 기록이며 평가가 아닙니다" |
| 예정 노드 | "후속 보고가 확인되면 이 스레드에 자동으로 연결됩니다" |
| 베타 하단 | "신청 정보는 베타 초대와 피드백 요청에만 사용하며 베타 종료 시 파기합니다 · 베타 기간 전 기능 무료 · 정식 출시 시 Pro 기능은 유료 전환되며 검색·시청·스레드·오픈데이터는 영구 무료입니다 · 데이터 CC BY 4.0" |
| 수익 안내 | "광고와 Pro 구독 수익은 서버·데이터 처리 비용에 사용됩니다. 기록 영역에는 광고를 싣지 않습니다." |
| 광고 라벨 | "광고" (모든 광고 구좌 상단에 표기) |
| 기여 안내 | "제출한 라벨·교정은 서로 다른 3인의 일치로만 반영되며, 반영 전까지 화면에 나타나지 않습니다. 채택 시 포인트가 적립됩니다." |
| 시민 검증 툴팁 | "이 정보는 시민 3인의 일치된 검증으로 확정되었습니다. 이전 값과 변경 이력은 공개 저장소에서 확인할 수 있습니다." |
| 푸터 공통 | "요약·화자 구분·연결 관계는 AI가 생성한 것으로 오류가 있을 수 있습니다. 원문 확인을 권장합니다. 영상 출처: KTV 국민방송 · 텍스트 출처: korea.kr·유튜브 자동 자막" |

---

## 12. 수익 모델 규칙 (광고 + Pro 구독)

전제: **수익화는 운영비 충당 수단이지 성장 목표가 아니다.** 시민 기본 기능의 영구 무료(§0)와 기록의 중립성(철학 8)이 상위 규칙이며, 충돌 시 수익 기능을 제거한다.

### 12.1 광고 (Google AdSense)

| 항목 | 규칙 |
|------|------|
| 구좌 수 | 페이지당 **정확히 1구좌** |
| 허용 위치 | 홈: 영상 그리드 하단(푸터 위) · 시청: 페이지 최하단 · 검색 결과: 결과 목록 끝 |
| 금지 위치 | 발언 인용 카드 안/사이 · 자막 패널 · 스레드 타임라인 · 오픈데이터 페이지 · 플레이어 주변 · 그리드 카드 사이 삽입(피드 광고) |
| 형식 | 배너만. 네이티브·스폰서 콘텐츠·전면(interstitial)·앵커(화면 고정) 금지 |
| 표기 | 구좌 상단 "광고" 라벨(§11) 필수 |
| 콘텐츠 | 정치 광고 카테고리 차단 설정 필수(중립성) |

### 12.2 Pro 구독

| 항목 | 규칙 |
|------|------|
| 플랜 | 단일: 월 ₩9,900 (연간 플랜·다단계 플랜 만들지 않음) |
| Pro 전용 | 키워드 20개 · 이메일 다이제스트 · 웹훅 · 리포트 PDF · API 5,000회/h |
| 영구 무료 | 검색 · 시청 · 스레드 열람 · 오픈데이터 · 덤프 다운로드 · 덤프 API · 키워드 10개 · RSS |
| 결제 | 토스페이먼츠 빌링키 정기결제. 해지 즉시 처리 + 잔여 기간 이용 유지. 해지 버튼은 설정 첫 화면에 노출(해지 방해 금지) |
| 베타 전환 | 베타 사용자에겐 유료 전환 최소 30일 전 이메일 고지 |

### 12.3 경계 불변 조건 (테스트로 검증)

1. 비로그인·비결제 상태에서 시민 기능 100% 동작
2. 덤프(`/v1/dump/latest`)는 어떤 조건에서도 무인증·무제한
3. 광고 컴포넌트가 금지 위치 셀렉터 안에 렌더되지 않음
4. Pro 게이트가 기존 무료 한도(키워드 10개·RSS)를 소급 축소하지 않음

### 12.4 결제 유예 규칙 (구현 예정)

PG 정기결제·인앱결제는 심사·승인 절차가 필요해 PoC/MVP 일정과 갭이 발생한다. 따라서:

1. **MVP(Phase 6a)에서는 결제 코드를 작성하지 않는다.** 요금 페이지·게이트 구조·subscriptions 테이블까지만 만들고, 결제 버튼은 비활성 스텁("출시 준비 중 · 베타 기간 Pro 무료")
2. Pro 게이트는 기능 플래그(`BILLING_ENABLED=false`)로 제어 — 베타 중엔 로그인 사용자 전원 Pro 취급, 승인 완료 후 플래그 전환만으로 과금 개시 가능해야 한다
3. 결제 활성화(Phase 6b) 조건: 토스페이먼츠 가맹 심사 통과 + 통신판매업 신고 완료 + 베타 사용자 30일 전 고지(§12.2) 발송
4. 앱스토어 배포는 로드맵에 없음(웹 단일) — 인앱결제 수수료·심사 이슈는 원천 회피. 웹 결제만 사용한다

---

## 13. 시민 기여 시스템 (라벨·교정 크라우드소싱)

전제: 이 서비스는 "누가 뭐라고 말했는가"의 기록이므로, 기여 시스템은 조작 통로가 될 수 있다. **1인 제출 즉시 반영은 어떤 경우에도 금지**하며, 아래 합의 규칙 없이는 어떤 기여도 화면에 나타나지 않는다.

### 13.1 기여 유형

| 유형 | kind | 입력 UI | 반영 대상 |
|------|------|---------|-----------|
| 화자 라벨 투표 | `speaker_label` | 자막 패널 문장 옆 "화자 지정" → 후보 목록(해당 회의 참석자 + 직접 입력) 선택 | Statement.speaker |
| 교정 제안 | `text_correction` | 문장 옆 "정정 제안" → 수정문 입력. korea.kr 공식 원고 붙여넣기 환영(유튜브 자막 복붙은 이미 보유한 원본이므로 무의미) | Statement.text |
| 누락 영상 제보 | `missing_video` | 제보 폼에 유튜브 링크 제출 | 파이프라인 discovered 큐 |

### 13.2 합의 규칙 (머지 파이프라인 — 08.5_merge_contributions.py, 일일 배치)

1. 같은 대상(sid+kind)에 **서로 다른 사용자 3인이 동일 값** 제출 → `merged`, 데이터 반영
2. 반영 시 필수 동작: Statement.history에 이전 값 기록(via:"citizen") + `verified` 또는 `text_verified` = true + Git 커밋(감사 추적)
3. 값 불일치 → 전건 `held`, LLM 스팟체크로 다수값 검증 후 판정. LLM도 불확실하면 held 유지(현상 유지 = 기본값)
4. 동일 IP·기기 시그널이 겹치는 계정 간 합의는 1인으로 계산(다계정 무효)
5. `missing_video`는 합의 불요 — 파이프라인이 제목 필터로 자동 검증 후 큐 등록
6. 골든셋: 정답이 확정된 문장을 무작위로 섞어 제출자 신뢰도 측정. 골든셋 오답률 높은 계정은 trust='limited'

### 13.3 마일리지 (Pro 연계)

| 규칙 | 내용 |
|------|------|
| 적립 | merged 채택 건당: 화자 라벨 1P · 교정 5P · 누락 제보(신규 영상 확인 시) 20P |
| 교환 | 100P = Pro 1개월 (자동 적용, 현금·상품권 등 현금성 보상 금지) |
| 크레딧 | 기여자 페이지(`/contributors`)에 닉네임·채택 수 공개(옵트인) |
| 제재 | rejected 비율 50% 초과 또는 골든셋 오답 반복 → trust='limited', 적립 정지(제출은 가능) |
| 한도 | 신규 계정(7일 미만) 일 20건, 이후 일 100건 |

### 13.4 UI 규칙

- 반영된 화자·교정에는 `✓ 시민 검증` green 배지(§5.2) + 툴팁(§11)으로 이력 열람 안내
- 반영 전 기여는 제출자 본인에게만 "검토 중 N/3" 상태로 표시
- 기여 입력부에 §11 "기여 안내" 문구 상시 노출
- 화자 배지 우선순위: `✓ 시민 검증` > `화자 AI 추정` > (null = "화자 미상")

### 13.5 불변 조건 (테스트로 검증)

1. contributions 테이블에서 화면 데이터로 가는 유일한 경로는 3인 합의 머지 배치뿐(직접 조회 렌더 금지)
2. 모든 merged 건은 history에 이전 값 보존 — 롤백 스크립트로 언제든 복원 가능
3. 비로그인 사용자도 기여 UI를 볼 수 있으나 제출 시 로그인 요구(기여만 계정 필수, 열람은 무제한)

---

## 14. 구현 Phase 추가

### Phase 7 — 시민 기여 (Phase 6 이후)
- [ ] contributions·contributor_stats 테이블 + RLS
- [ ] 자막 패널 기여 UI(화자 지정·정정 제안) + 제보 폼 + /contributors
- [ ] 08.5_merge_contributions.py(합의 판정·history 기록·Git 커밋) + 골든셋 운영
- [ ] 포인트 적립·Pro 교환 자동화
- ✅ 3인 일치 → 다음 배치에서 반영 + ✓ 시민 검증 배지 + history 기록 확인
- ✅ 2인 일치 + 1인 불일치 → held 상태, 화면 무변화 확인
- ✅ 동일 IP 3계정 제출 → 머지되지 않음 확인
- ✅ 100P 도달 계정 → Pro 자동 활성 확인
