import type { Metadata } from "next";
import { getTaskMap, getTasks } from "@/lib/data";
import TasksBrowser, { type TaskRow } from "./TasksBrowser";
import styles from "./TasksBrowser.module.css";

export const metadata: Metadata = {
  title: "국정과제",
  description: "123대 국정과제별 국무회의·업무보고 발언 기록 — 언급 0회도 그대로 기록합니다",
};

export default async function TasksPage() {
  const [tasks, map] = await Promise.all([getTasks(), getTaskMap()]);
  const byNo = new Map(map.map((e) => [e.task_no, e]));

  const rows: TaskRow[] = tasks.map((t) => {
    const entry = byNo.get(t.no);
    const refs = entry?.turn_refs ?? [];
    return {
      no: t.no,
      title: t.title,
      goal: t.goal,
      strategy: t.strategy,
      ministries: t.ministries,
      mentions: refs.length,
      threads: entry?.thread_ids.length ?? 0,
      last: refs.length > 0 ? refs[refs.length - 1].date : null,
    };
  });
  const mentioned = rows.filter((r) => r.mentions > 0).length;

  return (
    <>
      <main className={styles.main}>
        <div className={styles.pageHead}>
          <h1 className={styles.pageTitle}>123대 국정과제</h1>
          <p className={styles.pageMeta}>
            국무회의·업무보고 발언 기준 · 언급 보유 {mentioned}개 · 언급 0회 {rows.length - mentioned}개
          </p>
        </div>
        <TasksBrowser rows={rows} />
      </main>
    </>
  );
}
