import Link from "next/link";
import type { MeetingIndexItem } from "@/lib/types";
import { formatDate, kindLabel } from "@/lib/format";
import styles from "./HomeHero.module.css";

// 시초 화면 — 대형 타이포 + 최신 반영 배지 + 히어로 검색바 + 스탯.
// 관계·네트워크 시각 장식은 §9-1(그래프 시각화 금지)에 따라 두지 않는다.
export default function HomeHero({
  latest,
  meetingCount,
  statementCount,
  keywords,
}: {
  latest: MeetingIndexItem | null;
  meetingCount: number;
  statementCount: number;
  keywords: string[];
}) {
  return (
    <section className={styles.hero}>
      <p className={styles.eyebrow}>KTV 국무회의·국민업무보고 아카이브</p>
      {latest && (
        <Link href={`/watch/${latest.id}`} className={styles.latest}>
          <span className={styles.latestDot} aria-hidden />
          최신 반영 · {kindLabel(latest.kind)} {formatDate(latest.date)}
        </Link>
      )}
      <h1 className={styles.headline}>
        모든 발언을,
        <br />
        원문 그대로.
      </h1>
      <p className={styles.sub}>
        회의 영상을 문장 단위로 검색하고, 해당 구간을 바로 재생합니다.
      </p>
      <form className={styles.searchForm} action="/search" role="search">
        <input
          className={styles.searchInput}
          type="search"
          name="q"
          placeholder="지시·발언·안건 검색"
          aria-label="발언 검색"
        />
        <button className={styles.searchBtn} type="submit">
          검색
        </button>
      </form>
      <div className={styles.tags}>
        {keywords.map((kw) => (
          <Link key={kw} href={`/search?q=${encodeURIComponent(kw)}`} className={styles.tag}>
            #{kw}
          </Link>
        ))}
      </div>
      <p className={styles.stats}>
        회의 {meetingCount.toLocaleString()}건 · 발언 {statementCount.toLocaleString()}문장
      </p>
    </section>
  );
}
