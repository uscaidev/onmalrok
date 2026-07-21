import Link from "next/link";
import type { Thread } from "@/lib/types";
import { formatDate } from "@/lib/format";
import GradeBadge from "./GradeBadge";
import styles from "./ThreadStrip.module.css";

// 가로 재생목록 문법 (§5.4). 현재 회의 노드 = red 보더.
// Phase 1에는 스레드 데이터가 없어 렌더 지점이 없고, Phase 3 시청 화면 통합에서 사용된다.
const ROLE_LABEL = { order: "지시", report: "계획 보고", interim: "중간 보고", result: "이행 보고" } as const;

export default function ThreadStrip({
  thread,
  currentMeetingId,
}: {
  thread: Thread;
  currentMeetingId: string;
}) {
  return (
    <section className={styles.strip} aria-label={`스레드: ${thread.title}`}>
      <header className={styles.header}>
        <Link href={`/threads/${thread.id}`} className={styles.title}>
          {thread.title}
        </Link>
        <span className={styles.count}>{thread.nodes.length}개 발언</span>
      </header>
      <ol className={styles.nodes}>
        {thread.nodes.map((node) => (
          <li
            key={node.tid}
            className={`${styles.node} ${styles[node.role]} ${
              node.meeting_id === currentMeetingId ? styles.current : ""
            }`}
          >
            <span className={styles.roleTag}>{ROLE_LABEL[node.role]}</span>
            <span className={styles.date}>{formatDate(node.date)}</span>
            <GradeBadge grade={node.grade} />
          </li>
        ))}
      </ol>
    </section>
  );
}
