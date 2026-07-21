import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import SiteHeader from "@/components/SiteHeader";
import { getMeeting, getMeetingIndex } from "@/lib/data";
import WatchClient from "./WatchClient";
import styles from "./watchpage.module.css";

export async function generateStaticParams() {
  const index = await getMeetingIndex();
  return index.map((m) => ({ id: m.id }));
}

export async function generateMetadata({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);
  return { title: meeting?.title ?? "시청" };
}

export default async function WatchPage({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);
  if (!meeting) notFound();

  return (
    <>
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
