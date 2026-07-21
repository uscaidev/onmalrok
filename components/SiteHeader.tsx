import Link from "next/link";
import styles from "./SiteHeader.module.css";

export default function SiteHeader({ query }: { query?: string }) {
  return (
    <header className={styles.header}>
      <Link href="/" className={styles.logo}>
        <span className={styles.name}>온말록</span>
        <span className={styles.dot} aria-hidden>
          .
        </span>
      </Link>
      <nav className={styles.nav}>
        <Link href="/tasks" className={styles.navLink}>
          국정과제
        </Link>
      </nav>
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
