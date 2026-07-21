"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { formatDate } from "@/lib/format";
import styles from "./TasksBrowser.module.css";

export interface TaskRow {
  no: number;
  title: string;
  goal: string;
  strategy: string;
  ministries: string[];
  mentions: number;
  threads: number;
  last: string | null; // 마지막 언급 날짜
}

type Mode = "goal" | "ministry";

// 보기 전환은 단일 토글 칩 (§6.1 문법 준용) — 목표별(공식 순서) / 부처별(언급순 나래비)
export default function TasksBrowser({ rows }: { rows: TaskRow[] }) {
  const [mode, setMode] = useState<Mode>("goal");

  const goalGroups = useMemo(() => {
    const order: string[] = [];
    const groups = new Map<string, TaskRow[]>();
    for (const r of rows) {
      if (!groups.has(r.goal)) {
        order.push(r.goal);
        groups.set(r.goal, []);
      }
      groups.get(r.goal)!.push(r);
    }
    return order.map((goal) => ({ key: goal, rows: groups.get(goal)! }));
  }, [rows]);

  const ministryGroups = useMemo(() => {
    const groups = new Map<string, TaskRow[]>();
    for (const r of rows) {
      for (const m of r.ministries) {
        if (!groups.has(m)) groups.set(m, []);
        groups.get(m)!.push(r);
      }
    }
    return [...groups.entries()]
      .map(([key, list]) => ({
        key,
        rows: [...list].sort((a, b) => b.mentions - a.mentions || a.no - b.no),
        total: list.reduce((s, r) => s + r.mentions, 0),
      }))
      .sort((a, b) => b.total - a.total || a.key.localeCompare(b.key, "ko"));
  }, [rows]);

  const modeChip = (value: Mode, label: string) => (
    <button
      type="button"
      className={`${styles.chip} ${mode === value ? styles.chipActive : ""}`}
      onClick={() => setMode(value)}
      aria-pressed={mode === value}
    >
      {label}
    </button>
  );

  const groups = mode === "goal" ? goalGroups : ministryGroups;

  return (
    <>
      <div className={styles.chips}>
        {modeChip("goal", "국정목표별")}
        {modeChip("ministry", "부처별")}
      </div>
      {groups.map((g) => (
        <section key={g.key} className={styles.group}>
          <h2 className={styles.groupTitle}>
            {g.key}
            <span className={styles.groupMeta}>
              {mode === "ministry"
                ? ` 과제 ${g.rows.length}개 · 발언 ${g.rows.reduce((s, r) => s + r.mentions, 0)}건`
                : ` 과제 ${g.rows.length}개`}
            </span>
          </h2>
          <ul className={styles.list}>
            {g.rows.map((r) => (
              <li key={`${g.key}-${r.no}`}>
                <Link href={`/tasks/${r.no}`} className={styles.row}>
                  <span className={styles.no}>{r.no}</span>
                  <span className={styles.rowBody}>
                    <span className={styles.rowTitle}>{r.title}</span>
                    <span className={styles.rowSub}>
                      {r.ministries.join(" · ")}
                      {mode === "ministry" && ` · ${r.strategy}`}
                    </span>
                  </span>
                  <span className={r.mentions > 0 ? styles.rowStat : styles.rowStatZero}>
                    {r.mentions > 0 ? (
                      <>
                        발언 {r.mentions}건
                        {r.threads > 0 && ` · 스레드 ${r.threads}`}
                        {r.last && <span className={styles.rowDate}>{formatDate(r.last)}</span>}
                      </>
                    ) : (
                      "언급 0회"
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
