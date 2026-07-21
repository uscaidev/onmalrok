import HomeBrowser from "./HomeBrowser";
import { getKeywords, getMeetingIndex, getTopSpeakers } from "@/lib/data";

export default async function HomePage() {
  const [meetings, keywords, speakers] = await Promise.all([
    getMeetingIndex(),
    getKeywords(),
    getTopSpeakers(),
  ]);
  const topKeywords = Object.entries(keywords)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([k]) => k);

  return (
    <HomeBrowser
      meetings={meetings}
      keywords={topKeywords}
      speakers={speakers.map((s) => s.name)}
    />
  );
}
