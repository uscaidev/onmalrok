import Link from "next/link";
import { formatSec } from "@/lib/format";
import styles from "./PlayLink.module.css";

// 모든 파생 콘텐츠(요약·스레드·알림)의 마지막 요소 (§9-3).
// sid는 참조 식별자, meetingId/startSec는 호출부에서 해석해 전달한다.
export default function PlayLink({
  sid,
  meetingId,
  startSec,
}: {
  sid: string;
  meetingId: string;
  startSec: number;
}) {
  return (
    <Link
      className={styles.playLink}
      href={`/watch/${meetingId}?t=${Math.floor(startSec)}`}
      data-sid={sid}
    >
      ▶ {formatSec(startSec)} 구간 재생
    </Link>
  );
}
