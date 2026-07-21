"use client";

import { useState } from "react";
import Link from "next/link";
import type { MeetingIndexItem, MeetingKind } from "@/lib/types";
import MeetingCard from "@/components/MeetingCard";
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
