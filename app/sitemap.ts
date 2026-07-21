import type { MetadataRoute } from "next";
import { getMeetingIndex, getTasks } from "@/lib/data";
import { SITE_URL } from "@/lib/site";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [meetings, tasks] = await Promise.all([getMeetingIndex(), getTasks()]);
  return [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/tasks`, changeFrequency: "daily", priority: 0.9 },
    ...tasks.map((t) => ({
      url: `${SITE_URL}/tasks/${t.no}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...meetings.flatMap((m) => [
      {
        url: `${SITE_URL}/watch/${m.id}`,
        lastModified: new Date(m.date),
        changeFrequency: "monthly" as const,
        priority: 0.7,
      },
      {
        url: `${SITE_URL}/briefing/${m.id}`,
        lastModified: new Date(m.date),
        changeFrequency: "monthly" as const,
        priority: 0.5,
      },
    ]),
  ];
}
