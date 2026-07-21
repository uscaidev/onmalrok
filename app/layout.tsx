import type { Metadata } from "next";
import "@/styles/tokens.css";
import "./globals.css";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: { default: "온말록 — 국무회의·국민업무보고 아카이브", template: "%s · 온말록" },
  description:
    "국무회의·국민업무보고 영상을 자막 문장 단위로 검색하고 원문 구간을 바로 재생하는 아카이브",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Noto+Serif+KR:wght@400;600&display=swap"
          rel="stylesheet"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>
        {children}
        <footer className={styles.footer}>
          요약·화자 구분·연결 관계는 AI가 생성한 것으로 오류가 있을 수 있습니다. 원문 확인을
          권장합니다. 영상 출처: KTV 국민방송 · 텍스트 출처: korea.kr·유튜브 자동 자막
          <br />
          문의사항:{" "}
          <a
            className={styles.footerLink}
            href="https://github.com/uscaidev"
            target="_blank"
            rel="noopener noreferrer"
          >
            github.com/uscaidev
          </a>
        </footer>
      </body>
    </html>
  );
}
