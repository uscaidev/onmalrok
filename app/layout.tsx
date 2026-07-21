import type { Metadata } from "next";
import Script from "next/script";
import "@/styles/tokens.css";
import "./globals.css";
import SiteHeader from "@/components/SiteHeader";
import SiteNav from "@/components/SiteNav";
import { CONTACT_URL, SITE_NAME, SITE_URL } from "@/lib/site";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "온말록 — 국무회의·국민업무보고 아카이브", template: "%s · 온말록" },
  description:
    "국무회의·국민업무보고 영상을 자막 문장 단위로 검색하고 원문 구간을 바로 재생하는 아카이브. 123대 국정과제별 대통령 발언·부처 보고 추적.",
  // "온말톡"은 흔한 오기 — 검색 유입 흡수용으로 keywords·JSON-LD alternateName에 포함
  keywords: [
    "온말록",
    "온말톡",
    "국무회의",
    "국민업무보고",
    "국정과제",
    "대통령 발언",
    "발언록",
    "KTV",
  ],
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: SITE_URL,
    siteName: "온말록",
    title: "온말록 — 국무회의·국민업무보고 아카이브",
    description: "모든 발언을, 원문 그대로. 회의 영상을 문장 단위로 검색하고 해당 구간을 바로 재생합니다.",
  },
  twitter: {
    card: "summary_large_image",
    title: "온말록 — 국무회의·국민업무보고 아카이브",
    description: "모든 발언을, 원문 그대로. 회의 영상을 문장 단위로 검색하고 해당 구간을 바로 재생합니다.",
  },
  // 서치콘솔·서치어드바이저 확인 코드 — Vercel 환경변수로 주입 (미설정 시 태그 미출력)
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
    other: process.env.NEXT_PUBLIC_NAVER_SITE_VERIFICATION
      ? { "naver-site-verification": process.env.NEXT_PUBLIC_NAVER_SITE_VERIFICATION }
      : undefined,
  },
};

// AEO: 사이트 정체를 기계가 읽을 수 있게 (schema.org WebSite)
const WEBSITE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: SITE_NAME,
  alternateName: ["온말톡", "온말록 아카이브", "Onmalrok"],
  url: SITE_URL,
  description:
    "대한민국 국무회의·국민업무보고 영상 아카이브 — 문장 단위 발언록 검색·구간 재생, 123대 국정과제별 대통령 발언·부처 보고 추적",
  publisher: { "@type": "Organization", name: SITE_NAME, url: CONTACT_URL },
  inLanguage: "ko",
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/search?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
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
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(WEBSITE_JSONLD) }}
        />
        <SiteHeader />
        <SiteNav />
        <div className={styles.content}>
          {children}
          <footer className={styles.footer}>
            <p className={styles.tagline}>모든 발언을, 원문 그대로.</p>
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
        </div>
        {/* 네이버 애널리틱스 — wcslog.js 로드 완료 후 wcs_do() 실행 보장 */}
        <Script id="naver-analytics" strategy="afterInteractive">
          {`(function () {
            if (!window.wcs_add) window.wcs_add = {};
            window.wcs_add["wa"] = "17bcf88fe428bd0";
            var s = document.createElement("script");
            s.src = "//wcs.pstatic.net/wcslog.js";
            s.onload = function () { if (window.wcs) wcs_do(); };
            document.body.appendChild(s);
          })();`}
        </Script>
      </body>
    </html>
  );
}
