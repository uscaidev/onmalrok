import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import SiteHeader from "@/components/SiteHeader";
import { getMeeting, getMeetingIndex } from "@/lib/data";
import { formatDate, kindLabel } from "@/lib/format";
import { SITE_URL } from "@/lib/site";
import WatchClient from "./WatchClient";
import styles from "./watchpage.module.css";

export async function generateStaticParams() {
  const index = await getMeetingIndex();
  return index.map((m) => ({ id: m.id }));
}

export async function generateMetadata({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);
  if (!meeting) return { title: "시청" };
  return {
    title: `${meeting.title} — 발언록·요약`,
    description:
      `${formatDate(meeting.date)} ${kindLabel(meeting.kind)} 발언록 전문 — 발언 ` +
      `${meeting.stats.statement_count}문장, AI 요약·챕터·원문 구간 재생. 출처: KTV 국민방송.`,
  };
}

/** 초 → ISO 8601 duration (schema.org VideoObject용) */
function isoDuration(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return `PT${h > 0 ? `${h}H` : ""}${m > 0 ? `${m}M` : ""}${s}S`;
}

export default async function WatchPage({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);
  if (!meeting) notFound();

  const videoJsonLd = {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: meeting.title,
    description: `${formatDate(meeting.date)} ${kindLabel(meeting.kind)} — 발언 ${meeting.stats.statement_count}문장 발언록과 구간 재생`,
    uploadDate: meeting.date,
    duration: isoDuration(meeting.duration_sec),
    thumbnailUrl: `https://i.ytimg.com/vi/${meeting.youtube_id}/hqdefault.jpg`,
    embedUrl: `https://www.youtube.com/embed/${meeting.youtube_id}`,
    url: `${SITE_URL}/watch/${meeting.id}`,
    creator: { "@type": "Organization", name: "KTV 국민방송" },
    inLanguage: "ko",
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(videoJsonLd) }}
      />
      <SiteHeader />
      <div className={styles.briefingBar}>
        <Link href={`/briefing/${meeting.id}`} className={styles.briefingLink}>
          📋 부처 브리핑 — 지시·답변 발췌
        </Link>
      </div>
      <Suspense>
        <WatchClient meeting={meeting} />
      </Suspense>
    </>
  );
}
