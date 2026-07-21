import SiteHeader from "@/components/SiteHeader";
import HomeBrowser from "./HomeBrowser";
import HomeHero from "./HomeHero";
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
  const statementCount = meetings.reduce((sum, m) => sum + m.statement_count, 0);

  return (
    <>
      <SiteHeader />
      <HomeHero
        latest={meetings[0] ?? null}
        meetingCount={meetings.length}
        statementCount={statementCount}
        keywords={topKeywords}
      />
      <HomeBrowser
        meetings={meetings}
        keywords={topKeywords}
        speakers={speakers.map((s) => s.name)}
      />
    </>
  );
}
