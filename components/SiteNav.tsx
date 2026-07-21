"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./SiteNav.module.css";

// 유튜브 미니 가이드 문법 (§6.1): 데스크톱 좌측 아이콘+라벨 세로 스택 / 모바일 하단 탭바
function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 12H3l9-9 9 9h-2" />
      <path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" />
      <path d="M9 21v-6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v6" />
    </svg>
  );
}

function AgendaIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 20l1.3-3.9A7.2 7.2 0 0 1 3 12c0-4.4 4-8 9-8s9 3.6 9 8-4 8-9 8c-1.3 0-2.6-.2-3.7-.7L3 20" />
    </svg>
  );
}

function TasksIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="0.5" fill="currentColor" />
    </svg>
  );
}

const ITEMS = [
  { href: "/", label: "홈", Icon: HomeIcon },
  { href: "/agenda", label: "의제", Icon: AgendaIcon },
  { href: "/tasks", label: "국정과제", Icon: TasksIcon },
];

export default function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="주요 메뉴">
      {ITEMS.map(({ href, label, Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`${styles.item} ${active ? styles.itemActive : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <span className={styles.icon}>
              <Icon />
            </span>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
