import Link from "next/link";
import type { MeetingIndexItem } from "@/lib/types";
import { formatDate, formatSec, kindLabel, statusLabel } from "@/lib/format";
import styles from "./MeetingCard.module.css";

export default function MeetingCard({ meeting }: { meeting: MeetingIndexItem }) {
  return (
    <Link href={`/watch/${meeting.id}`} className={styles.card}>
      <div className={styles.thumbWrap}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          className={styles.thumb}
          src={`https://i.ytimg.com/vi/${meeting.youtube_id}/mqdefault.jpg`}
          alt=""
          loading="lazy"
          width={320}
          height={180}
        />
        <span className={styles.kind}>{kindLabel(meeting.kind)}</span>
        {statusLabel(meeting.pipeline_status) && (
          <span className={styles.pending}>{statusLabel(meeting.pipeline_status)}</span>
        )}
        <span className={styles.duration}>{formatSec(meeting.duration_sec)}</span>
      </div>
      <h3 className={styles.title}>{meeting.title}</h3>
      <p className={styles.meta}>
        {formatDate(meeting.date)} · 발언 {meeting.statement_count}건
      </p>
    </Link>
  );
}
