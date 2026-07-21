// /data JSON 접근 레이어 — 스키마가 SPEC-PIPELINE.md §2로 이관될 때 이 파일만 고치면 되도록
// 파일 경로·형식에 대한 지식을 여기에만 둔다. 서버(빌드 시) 전용.
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import type { Meeting, MeetingIndexItem } from "./types";

const dataDir = path.join(process.cwd(), "data");

export async function getMeetingIndex(): Promise<MeetingIndexItem[]> {
  const raw = await readFile(path.join(dataDir, "index", "meetings.json"), "utf8");
  return JSON.parse(raw);
}

export async function getKeywords(): Promise<Record<string, number>> {
  const raw = await readFile(path.join(dataDir, "index", "keywords.json"), "utf8");
  return JSON.parse(raw);
}

export async function getMeeting(id: string): Promise<Meeting | null> {
  // id는 라우트 파라미터 — 경로 조작 방지를 위해 파일 목록과 대조한다
  const files = await readdir(path.join(dataDir, "meetings"));
  const file = files.find((f) => f === `${id}.json`);
  if (!file) return null;
  const raw = await readFile(path.join(dataDir, "meetings", file), "utf8");
  return JSON.parse(raw);
}

export async function getAllMeetings(): Promise<Meeting[]> {
  const files = (await readdir(path.join(dataDir, "meetings"))).filter((f) => f.endsWith(".json"));
  const meetings = await Promise.all(
    files.map(async (f) => JSON.parse(await readFile(path.join(dataDir, "meetings", f), "utf8")) as Meeting)
  );
  return meetings.sort((a, b) => (a.date < b.date ? 1 : -1));
}

/** 홈 화면 "주요 발언자" 칩 — 전체 회의에서 발언 턴 수 상위 화자 (사회자 제외) */
export async function getTopSpeakers(limit = 5): Promise<{ name: string; count: number }[]> {
  const meetings = await getAllMeetings();
  const counts = new Map<string, number>();
  for (const m of meetings) {
    for (const t of m.turns ?? []) {
      if (!t.speaker || t.speaker.name === "사회자") continue;
      counts.set(t.speaker.name, (counts.get(t.speaker.name) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}
