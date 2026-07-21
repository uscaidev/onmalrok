"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import AiNotice from "@/components/AiNotice";
import PlayLink from "@/components/PlayLink";
import QuoteText from "@/components/QuoteText";
import { formatDate, formatSec, kindLabel } from "@/lib/format";
import type { BriefingItem, MinistryBriefing } from "@/lib/briefing";
import type { MeetingKind } from "@/lib/types";
import styles from "./Briefing.module.css";

// 2단 구성(SPEC.md §0): 좌 발췌 목록(체크로 포함/제외 + 구간 재생 검증) /
// 우 복사 미리보기(체크된 항목만 개조식 실시간 반영 = 복사될 텍스트 그대로).
// 조치계획 칸은 만들지 않는다 (§1-5 — 그건 사용자의 일).
export default function BriefingClient({
  meetingId,
  title,
  date,
  kind,
  briefings,
}: {
  meetingId: string;
  title: string;
  date: string;
  kind: MeetingKind;
  briefings: MinistryBriefing[];
}) {
  const [selected, setSelected] = useState(briefings[0]?.ministry ?? null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const current = briefings.find((b) => b.ministry === selected) ?? null;

  const key = (section: string, item: BriefingItem) => `${section}:${item.sid}`;
  const toggle = (k: string) =>
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const pickMinistry = (m: string) => {
    setSelected(m);
    setExcluded(new Set()); // 부처 전환 시 선택 초기화
  };

  const directives = current?.directives.filter((d) => !excluded.has(key("d", d))) ?? [];
  const answers = current?.answers.filter((a) => !excluded.has(key("a", a))) ?? [];

  const copyText = useMemo(() => {
    if (!current) return "";
    const lines: string[] = [
      `${title} (${formatDate(date)} ${kindLabel(kind)}) — ${current.ministry} 관련 발췌`,
      "",
    ];
    if (directives.length > 0) {
      lines.push("□ 지시사항 (대통령)");
      for (const d of directives) lines.push(` ○ ${d.text} (${formatSec(d.start_sec)})`);
      lines.push("");
    }
    if (answers.length > 0) {
      lines.push(`□ 답변사항 (${current.ministry})`);
      for (const a of answers)
        lines.push(` ○ ${a.speaker ? `[${a.speaker}] ` : ""}${a.text} (${formatSec(a.start_sec)})`);
      lines.push("");
    }
    lines.push(
      "※ 온말록 AI 추출 초안 — 자동자막 기반으로 오류가 있을 수 있어 원문 대조가 필요합니다.",
      `원문: https://onmalrok.vercel.app/watch/${meetingId}`
    );
    return lines.join("\n");
  }, [current, directives, answers, meetingId, title, date, kind]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* 클립보드 미지원 브라우저 — 무시 */
    }
  };

  const renderItem = (section: "d" | "a", item: BriefingItem) => {
    const k = key(section, item);
    const included = !excluded.has(k);
    return (
      <li key={k} className={`${styles.item} ${included ? "" : styles.itemOff}`}>
        <label className={styles.itemCheck}>
          <input
            type="checkbox"
            checked={included}
            onChange={() => toggle(k)}
            aria-label="복사에 포함"
          />
        </label>
        <div className={styles.itemBody}>
          {section === "a" && item.speaker && (
            <p className={styles.speaker}>
              {item.speaker}
              {item.speaker_inferred && <span className={styles.inferred}> 화자 AI 추정</span>}
            </p>
          )}
          <blockquote className={styles.quote}>
            <QuoteText text={item.text} raw={item.text_raw} corrected={item.corrected} />
          </blockquote>
          <div className={styles.itemMeta}>
            <span className={styles.basis}>{item.basis}</span>
            <PlayLink sid={item.sid} meetingId={meetingId} startSec={item.start_sec} />
          </div>
        </div>
      </li>
    );
  };

  return (
    <main className={styles.main}>
      <nav className={styles.crumb}>
        <Link href={`/watch/${meetingId}`}>← 회의 시청</Link>
      </nav>
      <h1 className={styles.title}>{title}</h1>
      <p className={styles.meta}>
        {formatDate(date)} · {kindLabel(kind)} · 부처 브리핑
      </p>
      <p className={styles.warn}>
        AI 추출 초안 · 원문 대조 필수 — 자동자막 기반 발췌로 오인식이 있을 수 있습니다. 왼쪽에서
        구간 재생으로 확인하고, 잘못 뽑힌 항목은 체크를 해제하면 복사에서 빠집니다.
      </p>

      {briefings.length === 0 ? (
        <p className={styles.empty}>이 회의에서 부처를 특정할 수 있는 발언 기록이 없습니다.</p>
      ) : (
        <>
          <div className={styles.chips}>
            {briefings.map((b) => (
              <button
                key={b.ministry}
                type="button"
                className={`${styles.chip} ${b.ministry === selected ? styles.chipActive : ""}`}
                onClick={() => pickMinistry(b.ministry)}
                aria-pressed={b.ministry === selected}
              >
                {b.ministry}
                <span className={styles.chipCount}>{b.directives.length + b.answers.length}</span>
              </button>
            ))}
          </div>

          {current && (
            <div className={styles.panes}>
              <section className={styles.listPane} aria-label="발췌 목록">
                {current.directives.length > 0 && (
                  <>
                    <h2 className={styles.sectionTitle}>□ 지시사항 (대통령)</h2>
                    <ul className={styles.list}>
                      {current.directives.map((d) => renderItem("d", d))}
                    </ul>
                  </>
                )}
                {current.answers.length > 0 && (
                  <>
                    <h2 className={styles.sectionTitle}>□ 답변사항 ({current.ministry})</h2>
                    <ul className={styles.list}>{current.answers.map((a) => renderItem("a", a))}</ul>
                  </>
                )}
              </section>

              <section className={styles.previewPane} aria-label="복사 미리보기">
                <div className={styles.previewHead}>
                  <span className={styles.previewLabel}>
                    복사 미리보기 · {directives.length + answers.length}항목
                  </span>
                  <button type="button" className={styles.copyBtn} onClick={copy}>
                    {copied ? "복사됨 ✓" : "📋 전체 복사"}
                  </button>
                </div>
                <pre className={styles.preview}>{copyText}</pre>
              </section>
            </div>
          )}
        </>
      )}
      <AiNotice />
    </main>
  );
}
