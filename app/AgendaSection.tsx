"use client";

import { useMemo, useState } from "react";
import type { AgendaIndex, AgendaThread } from "@/lib/types";
import AiLabel from "@/components/AiLabel";
import PlayLink from "@/components/PlayLink";
import styles from "./AgendaSection.module.css";

const WINDOWS = [
  { days: 28, label: "최근 4주" },
  { days: 90, label: "3개월" },
  { days: 180, label: "6개월" },
] as const;

const STAGE_LABEL: Record<string, string> = {
  order: "지시",
  plan: "계획",
  progress: "진행",
  result: "결과",
  followup_pending: "후속 대기",
};

const DAY_MS = 86_400_000;

function windowCount(t: AgendaThread, refDate: string, days: number): number {
  const ref = new Date(refDate).getTime();
  return t.node_dates.filter((d) => (ref - new Date(d).getTime()) / DAY_MS <= days).length;
}

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${Number(m)}.${Number(d)}`;
}

// "지금 활발한 의제" 뷰 (§6.9) — 기간·분야 필터는 클라이언트 계산 (SPEC-PIPELINE.md §2.5)
export default function AgendaSection({
  agenda,
  limit = 6,
  showTitle = true,
}: {
  agenda: AgendaIndex;
  limit?: number;
  showTitle?: boolean;
}) {
  const TOP_N = limit;
  const [days, setDays] = useState<number>(WINDOWS[0].days);
  const [field, setField] = useState<string>("all");

  const brief = agenda.briefs.find((b) => b.window_days === days);
  const threadById = useMemo(
    () => new Map(agenda.threads.map((t) => [t.id, t])),
    [agenda.threads]
  );

  const active = useMemo(() => {
    return agenda.threads
      .map((t) => ({ t, count: windowCount(t, agenda.ref_date, days) }))
      .filter(({ t, count }) => count > 0 && (field === "all" || t.field_ids.includes(field)))
      .sort((a, b) => b.count - a.count);
  }, [agenda, days, field]);

  const fieldLabel = useMemo(
    () => new Map(agenda.fields.map((f) => [f.id, f.label])),
    [agenda.fields]
  );

  return (
    <section className={styles.section} aria-label="지금 활발한 의제">
      <div className={styles.head}>
        {showTitle && <h2 className={styles.title}>지금 활발한 의제</h2>}
        <div className={styles.windows} role="group" aria-label="기간 선택">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              type="button"
              className={`${styles.windowBtn} ${days === w.days ? styles.windowActive : ""}`}
              onClick={() => setDays(w.days)}
              aria-pressed={days === w.days}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.fieldChips}>
        <button
          type="button"
          className={`${styles.chip} ${field === "all" ? styles.chipActive : ""}`}
          onClick={() => setField("all")}
          aria-pressed={field === "all"}
        >
          전체 {agenda.threads.length}
        </button>
        {agenda.fields.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`${styles.chip} ${f.id === "etc" ? styles.chipEtc : ""} ${
              field === f.id ? styles.chipActive : ""
            }`}
            onClick={() => setField(f.id)}
            aria-pressed={field === f.id}
          >
            {f.label} {f.thread_count}
          </button>
        ))}
      </div>

      {brief && brief.items.length > 0 && (
        <div className={styles.brief}>
          <div className={styles.briefHead}>
            <span className={styles.briefTitle}>이 기간의 흐름</span>
            <AiLabel type="summary" />
            <span className={styles.briefMeta}>기준일 {agenda.ref_date} · 원문 대조 필요</span>
          </div>
          <ul className={styles.briefList}>
            {brief.items.map((item, i) => (
              <li key={i} className={styles.briefItem}>
                {item.text}
                <span className={styles.briefLinks}>
                  {item.thread_ids.slice(0, 3).map((id) => {
                    const t = threadById.get(id);
                    return t ? (
                      <PlayLink
                        key={id}
                        sid={`${t.seed.meeting_id}@seed`}
                        meetingId={t.seed.meeting_id}
                        startSec={t.seed.t}
                      />
                    ) : null;
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className={styles.meta}>
        {field === "all"
          ? `이 기간에 발언이 이어진 스레드 ${active.length}개 · 활동 상위 ${Math.min(TOP_N, active.length)}`
          : `${fieldLabel.get(field) ?? field} · 이 기간 활동 ${active.length}건 중 상위 ${Math.min(TOP_N, active.length)}`}
      </p>

      <ol className={styles.list}>
        {active.slice(0, TOP_N).map(({ t, count }) => (
          <li key={t.id} className={styles.row}>
            <div className={styles.rowHead}>
              <span className={styles.rowTitle}>
                {t.title} <AiLabel type="summary" />
              </span>
              <span className={styles.rowCount}>발언 {count}건</span>
            </div>
            <div className={styles.rowMeta}>
              {t.field_ids.map((id) => (
                <span key={id} className={styles.fieldTag}>
                  {fieldLabel.get(id) ?? "미분류"}
                </span>
              ))}
              <span className={styles.stageTag}>{STAGE_LABEL[t.stage] ?? t.stage}</span>
              <span className={styles.orderBadge}>{shortDate(t.seed.date)} 지시</span>
              {t.seed.quote && <q className={styles.quote}>{t.seed.quote}</q>}
              <PlayLink
                sid={`${t.seed.meeting_id}@seed`}
                meetingId={t.seed.meeting_id}
                startSec={t.seed.t}
              />
            </div>
            {/* 노드 1개면 latest == seed — 같은 재생 링크를 중복 표기하지 않는다 */}
            {t.node_dates.length > 1 && (
            <div className={styles.rowLatest}>
              최근 응답 {shortDate(t.latest.date)}
              {t.latest.speaker && (
                <>
                  {" · "}
                  <span className={styles.speaker}>{t.latest.speaker}</span> <AiLabel type="speaker" />
                </>
              )}
              {t.latest.rel_label && ` · ${t.latest.rel_label}`}
              <PlayLink
                sid={`${t.latest.meeting_id}@latest`}
                meetingId={t.latest.meeting_id}
                startSec={t.latest.t}
              />
            </div>
            )}
          </li>
        ))}
      </ol>
      {active.length === 0 && <p className={styles.empty}>이 기간에 활동한 의제가 없습니다.</p>}

      <p className={styles.notice}>
        의제문·흐름은 AI 요약 초안 · 발언자 표기는 AI 추정 · 상태 기록이며 평가가 아닙니다
      </p>
    </section>
  );
}
