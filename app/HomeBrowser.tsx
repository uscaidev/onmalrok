"use client";

import { useState } from "react";
import Link from "next/link";
import type { MeetingIndexItem, MeetingKind } from "@/lib/types";
import MeetingCard from "@/components/MeetingCard";
import { formatDate, kindLabel } from "@/lib/format";
import styles from "./HomeBrowser.module.css";

type Filter = "all" | MeetingKind;

// 필터 칩은 다중 선택 아님 — 단일 토글 (§6.1)
export default function HomeBrowser({
  meetings,
  keywords,
  speakers,
}: {
  meetings: MeetingIndexItem[];
  keywords: string[];
  speakers: string[];
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const visible = filter === "all" ? meetings : meetings.filter((m) => m.kind === filter);
  const latest = meetings[0];
  const statementCount = meetings.reduce((sum, m) => sum + m.statement_count, 0);

  const kindChip = (value: Filter, label: string) => (
    <button
      type="button"
      className={`${styles.chip} ${filter === value ? styles.chipActive : ""}`}
      onClick={() => setFilter(value)}
      aria-pressed={filter === value}
    >
      {label}
    </button>
  );

  return (
    <main className={styles.main}>
      {latest && (
        <Link href={`/watch/${latest.id}`} className={styles.status}>
          <span className={styles.statusDot} aria-hidden />
          최신 반영 · {kindLabel(latest.kind)} {formatDate(latest.date)} · 회의{" "}
          {meetings.length.toLocaleString()}건 · 발언 {statementCount.toLocaleString()}문장
        </Link>
      )}
      <div className={styles.chips}>
        {kindChip("all", "전체")}
        {kindChip("cabinet", "국무회의")}
        {kindChip("report", "업무보고")}
        <span className={styles.chipDivider} aria-hidden />
        {keywords.map((kw) => (
          <Link key={kw} href={`/search?q=${encodeURIComponent(kw)}`} className={styles.chip}>
            {kw}
          </Link>
        ))}
        {speakers.map((name) => (
          <Link key={name} href={`/search?q=${encodeURIComponent(name)}`} className={styles.chip}>
            {name}
          </Link>
        ))}
      </div>
      <div className={styles.grid}>
        {visible.map((m) => (
          <MeetingCard key={m.id} meeting={m} />
        ))}
      </div>
      {visible.length === 0 && <p className={styles.empty}>해당하는 회의가 없습니다.</p>}
    </main>
  );
}
