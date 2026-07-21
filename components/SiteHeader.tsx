"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import styles from "./SiteHeader.module.css";

function SearchIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden
    >
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M21 21l-5.2-5.2" />
    </svg>
  );
}

function SearchForm() {
  const query = useSearchParams().get("q") ?? "";
  return (
    <form className={styles.searchForm} action="/search" role="search">
      <input
        key={query}
        className={styles.searchInput}
        type="search"
        name="q"
        defaultValue={query}
        placeholder="발언·지시·안건 검색"
        aria-label="발언 검색"
      />
      <button className={styles.searchBtn} type="submit" aria-label="검색">
        <SearchIcon />
      </button>
    </form>
  );
}

export default function SiteHeader() {
  return (
    <header className={styles.header}>
      <Link href="/" className={styles.logo}>
        <span className={styles.name}>온말록</span>
        <span className={styles.dot} aria-hidden>
          .
        </span>
      </Link>
      <Suspense>
        <SearchForm />
      </Suspense>
    </header>
  );
}
