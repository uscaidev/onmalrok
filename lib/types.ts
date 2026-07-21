// 데이터 스키마 — SSOT: SPEC-PIPELINE.md §2 (Statement–Turn–Agenda 3층 구조).
// 화자는 Turn에만 존재하며 Statement는 turn_id로 역참조한다.
// 파이프라인 처리 전 단계의 실데이터는 turn_id/agenda_id가 null일 수 있어 nullable로 둔다.

export type LinkGrade = "explicit" | "topic" | "ai_inferred";

export type MeetingKind = "cabinet" | "report";

export type PipelineStatus = "done" | "partial" | "waiting_captions" | "failed";

export interface SummaryParagraph {
  text: string;
  sids: string[]; // 문단별 근거 문장 — 프론트가 PlayLink 생성 (SPEC-PIPELINE.md §4-06)
}

export interface MeetingSummary {
  brief: string;
  paragraphs?: SummaryParagraph[];
  generated_at: string;
  model: string;
}

export interface Speaker {
  name: string;
  inferred: boolean; // true → "화자 AI 추정" 라벨
  verified: boolean; // true → "✓ 시민 검증" 라벨 (inferred보다 우선)
}

export interface AgendaBlock {
  aid: string; // "{meeting_id}@a{n}"
  title: string;
  start_sec: number;
  sid_range: [string, string];
  official: boolean; // korea.kr 안건 매핑 여부
}

export interface Turn {
  tid: string; // "{meeting_id}@t{n}"
  speaker: Speaker | null;
  sid_range: [string, string];
  agenda_id: string;
  rep_sid: string; // 대표 문장 (스레드 노드·카드 인용용)
}

export interface StatementHistory {
  field: "speaker" | "text";
  prev: string;
  at: string;
  via: "pipeline" | "citizen";
}

export interface ThreadRef {
  thread_id: string;
  grade: LinkGrade;
}

export interface Statement {
  sid: string; // "{meeting_id}#{seq}" 전역 유일
  start_sec: number;
  text: string; // 교정본 (표시 기본값)
  text_raw: string; // 자동자막 원문 — 영구 보존 (§9-10)
  corrected: boolean;
  turn_id: string | null;
  agenda_id: string | null;
  text_verified: boolean;
  history: StatementHistory[];
  thread_refs: ThreadRef[];
}

export interface Meeting {
  id: string; // "{연도}-{cab|rpt}-{MMDD}-{yid앞6}"
  kind: MeetingKind;
  title: string;
  date: string; // KST
  youtube_id: string;
  duration_sec: number;
  source: { video: string; text?: string };
  summary: MeetingSummary | null;
  agenda: AgendaBlock[]; // 의제 구간 — 요약·챕터 UI의 단위
  turns: Turn[]; // 화자 턴 — 스레드 노드·화자 라벨의 단위
  statements: Statement[]; // 문장 — 검색·타임스탬프의 단위
  stats: { statement_count: number; turn_count: number };
  pipeline_status: PipelineStatus;
}

// Thread — SPEC.md §4.2, 노드는 SPEC-PIPELINE.md §2.3의 turn 참조로 확장
export type ThreadStage = "order" | "plan" | "progress" | "result" | "followup_pending";

export type NodeRole = "order" | "report" | "interim" | "result";

export interface ThreadNode {
  tid: string; // Turn 참조 — 노드의 실체는 "화자의 발언 턴"
  rep_sid: string; // UI 인용용 대표 문장
  meeting_id: string;
  date: string;
  role: NodeRole;
  grade: LinkGrade;
  grade_evidence: string;
  reviewed: boolean;
  rel_label: string;
}

export interface Thread {
  id: string;
  title: string;
  topic_tags: string[];
  stage: ThreadStage;
  nodes: ThreadNode[];
  followup: { expected: string; note: string } | null;
  updated_at: string;
}

// 국정과제 축 — SPEC-PIPELINE.md §2.4 (과제 ⊃ 스레드 ⊃ 발언)
export interface GovTask {
  no: number; // 1~123 공식 순번
  title: string;
  goal: string; // 5대 국정목표
  strategy: string;
  ministries: string[]; // 주관 부처 (공식 표기)
  source: string; // korea.kr/govVision 원문 PDF
}

export interface TaskTurnRef {
  tid: string;
  meeting_id: string;
  date: string;
  grade: LinkGrade;
  grade_evidence: string;
}

export interface TaskMapEntry {
  task_no: number;
  thread_ids: string[];
  turn_refs: TaskTurnRef[]; // 과제 관련 언급 전체 — 빈 배열 = "언급 0회"도 기록
}

// 의제 뷰 — SPEC-PIPELINE.md §2.5 (data/index/agenda.json)
export interface AgendaSeed {
  date: string;
  quote: string; // 시드 explicit 지시 발화의 grade_evidence
  speaker: string | null; // Turn 화자 — AI 추정 병기 필수
  meeting_id: string;
  youtube_id: string;
  t: number; // 재생 시작 초 (rep_sid start_sec - 3)
}

export interface AgendaLatest {
  date: string;
  speaker: string | null;
  rel_label: string;
  meeting_id: string;
  youtube_id: string;
  t: number;
}

export interface AgendaThread {
  id: string;
  title: string; // 명사형 의제문 — AI 산출이므로 AiLabel 대상
  stage: ThreadStage;
  field_ids: string[]; // 미매치면 ["etc"]
  node_dates: string[]; // 기간 창 필터·집계는 클라이언트 계산
  seed: AgendaSeed;
  latest: AgendaLatest;
}

export interface AgendaBriefItem {
  text: string;
  thread_ids: string[]; // 근거 스레드 — 항목당 1개 이상 보장
}

export interface AgendaIndex {
  generated_at: string;
  ref_date: string; // 기간 창 기준일 = 최신 회의 날짜
  fields: { id: string; label: string; thread_count: number }[];
  threads: AgendaThread[];
  briefs: { window_days: number; items: AgendaBriefItem[] }[];
}

// 검색 색인 — SPEC.md §4.3
export interface SearchDoc {
  sid: string;
  text: string;
  speaker_name: string;
  meeting_id: string;
  meeting_title: string;
  date: string;
  start_sec: number;
}

// index/meetings.json 항목 (경량 메타)
export interface MeetingIndexItem {
  id: string;
  kind: MeetingKind;
  title: string;
  date: string;
  youtube_id: string;
  duration_sec: number;
  statement_count: number;
  pipeline_status: PipelineStatus;
}
