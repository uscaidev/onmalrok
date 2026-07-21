import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SiteHeader from "@/components/SiteHeader";
import { buildBriefing } from "@/lib/briefing";
import { getMeeting, getMeetingIndex, getTaskMap, getTasks } from "@/lib/data";
import BriefingClient from "./BriefingClient";

export async function generateStaticParams() {
  const index = await getMeetingIndex();
  return index.map((m) => ({ id: m.id }));
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const meeting = await getMeeting(params.id);
  return { title: meeting ? `부처 브리핑 · ${meeting.title}` : "부처 브리핑" };
}

export default async function BriefingPage({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);
  if (!meeting) notFound();
  const [tasks, map] = await Promise.all([getTasks(), getTaskMap()]);
  const briefings = buildBriefing(meeting, tasks, map);

  return (
    <>
      <SiteHeader />
      <BriefingClient
        meetingId={meeting.id}
        title={meeting.title}
        date={meeting.date}
        kind={meeting.kind}
        briefings={briefings}
      />
    </>
  );
}
