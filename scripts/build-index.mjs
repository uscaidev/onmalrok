// data/meetings/*.json → data/index/{meetings,search-{n},keywords}.json 생성.
// 트랙 A의 07_build_index.py가 완성되면 이 스크립트는 제거되고 파이프라인 산출물을 그대로 쓴다.
import { readdir, readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const meetingsDir = path.join(root, "data", "meetings");
const indexDir = path.join(root, "data", "index");

const SHARD_SIZE = 10; // 회의 10개 단위 샤드 (§4.3)

// keywords.json 후보 — 문장 카운트가 1 이상인 것만 남긴다
const KEYWORD_CANDIDATES = [
  "위기가구", "청년", "소상공인", "폭염", "의료비",
  "중대재해", "무더위쉼터", "채무 조정", "취약계층", "일경험",
];

const files = (await readdir(meetingsDir)).filter((f) => f.endsWith(".json"));
const meetings = [];
for (const f of files) {
  meetings.push(JSON.parse(await readFile(path.join(meetingsDir, f), "utf8")));
}
meetings.sort((a, b) => (a.date < b.date ? 1 : -1)); // 최신순

const meetingsIndex = meetings.map((m) => ({
  id: m.id,
  kind: m.kind,
  title: m.title,
  date: m.date,
  youtube_id: m.youtube_id,
  duration_sec: m.duration_sec,
  statement_count: m.stats.statement_count,
  pipeline_status: m.pipeline_status,
}));

const searchDocs = meetings.flatMap((m) => {
  // 화자는 Turn에만 있다 — turn_id 역참조 (SPEC-PIPELINE.md §2.2)
  const speakerByTurn = new Map((m.turns ?? []).map((t) => [t.tid, t.speaker?.name ?? ""]));
  return m.statements.map((s) => ({
    sid: s.sid,
    text: s.text,
    speaker_name: (s.turn_id && speakerByTurn.get(s.turn_id)) || "",
    meeting_id: m.id,
    meeting_title: m.title,
    date: m.date,
    start_sec: s.start_sec,
  }));
});

const keywords = {};
for (const kw of KEYWORD_CANDIDATES) {
  const count = searchDocs.filter((d) => d.text.includes(kw)).length;
  if (count > 0) keywords[kw] = count;
}

await mkdir(indexDir, { recursive: true });
await writeFile(path.join(indexDir, "meetings.json"), JSON.stringify(meetingsIndex, null, 2));
const shardCount = Math.max(1, Math.ceil(meetings.length / SHARD_SIZE));
const docsPerShard = Math.ceil(searchDocs.length / shardCount);
const shards = [];
for (let n = 0; n < shardCount; n++) {
  const shard = searchDocs.slice(n * docsPerShard, (n + 1) * docsPerShard);
  shards.push(shard);
  // 샤드는 용량이 커서 최소화 직렬화 (스키마는 §4.3 그대로)
  await writeFile(path.join(indexDir, `search-${n}.json`), JSON.stringify(shard));
}
await writeFile(path.join(indexDir, "keywords.json"), JSON.stringify(keywords, null, 2));

// 검색 페이지가 필요 시점에 fetch할 수 있도록 public에 사본 배치 (번들 포함 방지)
const publicSearchDir = path.join(root, "public", "search-index");
await mkdir(publicSearchDir, { recursive: true });
await writeFile(
  path.join(publicSearchDir, "meta.json"),
  JSON.stringify({ shards: shardCount, docs: searchDocs.length })
);
for (let n = 0; n < shardCount; n++) {
  await writeFile(path.join(publicSearchDir, `search-${n}.json`), JSON.stringify(shards[n]));
}

console.log(
  `index built: ${meetings.length} meetings, ${searchDocs.length} statements, ${shardCount} shard(s), ${Object.keys(keywords).length} keywords`
);
