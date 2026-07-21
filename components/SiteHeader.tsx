import Link from "next/link";
import styles from "./SiteHeader.module.css";

export default function SiteHeader({ query }: { query?: string }) {
  return (
    <header className={styles.header}>
      {/* 마크는 네이밍 확정 후 재설계 — 임시 텍스트 로고 */}
      <Link href="/" className={styles.logo}>
        <span className={styles.name}>Open Policy</span>
      </Link>
      <form className={styles.searchForm} action="/search" role="search">
        <input
          className={styles.searchInput}
          type="search"
          name="q"
          defaultValue={query ?? ""}
          placeholder="발언 검색"
          aria-label="발언 검색"
        />
        <button className={styles.searchBtn} type="submit" aria-label="검색">
          🔍
        </button>
      </form>
    </header>
  );
}
