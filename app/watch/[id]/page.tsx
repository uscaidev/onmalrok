import { Suspense } from "react";
import { notFound } from "next/navigation";
import SiteHeader from "@/components/SiteHeader";
import { getMeeting, getMeetingIndex } from "@/lib/data";
import WatchClient from "./WatchClient";

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
      <Suspense>
        <WatchClient meeting={meeting} />
      </Suspense>
    </>
  );
}
