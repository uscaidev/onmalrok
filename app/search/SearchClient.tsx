"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import MiniSearch from "minisearch";
import type { SearchDoc } from "@/lib/types";
import QuoteText from "@/components/QuoteText";
import PlayLink from "@/components/PlayLink";
import { formatDate } from "@/lib/format";
import styles from "./SearchClient.module.css";

// 색인은 번들에 넣지 않고 검색 페이지 진입 시에만 fetch한다 (샤드 총량이 커서)
async function loadDocs(): Promise<SearchDoc[]> {
  const meta: { shards: number } = await (await fetch("/search-index/meta.json")).json();
  const shards = await Promise.all(
    Array.from({ length: meta.shards }, (_, n) =>
      fetch(`/search-index/search-${n}.json`).then((r) => r.json() as Promise<SearchDoc[]>)
    )
  );
  return shards.flat();
}

export default function SearchClient() {
  const params = useSearchParams();
  const query = (params.get("q") ?? "").trim();

  const [docs, setDocs] = useState<SearchDoc[] | null>(null);
  const [mini, setMini] = useState<MiniSearch<SearchDoc> | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadDocs().then((loaded) => {
      if (cancelled) return;
      const m = new MiniSearch<SearchDoc>({
        idField: "sid",
        fields: ["text", "speaker_name"],
        storeFields: [
          "sid",
          "text",
          "speaker_name",
          "meeting_id",
          "meeting_title",
          "date",
          "start_sec",
        ],
        searchOptions: { prefix: true, boost: { text: 2 } },
      });
      m.addAll(loaded);
      setDocs(loaded);
      setMini(m);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const results = useMemo(() => {
    if (!query || !mini || !docs) return [];
    const hits = mini.search(query) as unknown as SearchDoc[];
    // MiniSearch 토큰 매칭이 조사 붙은 한국어를 놓치는 경우 부분 문자열 매칭으로 보강
    const hitSids = new Set(hits.map((h) => h.sid));
    const extra = docs.filter(
      (d) => !hitSids.has(d.sid) && (d.text.includes(query) || d.speaker_name.includes(query))
    );
    return [...hits, ...extra].slice(0, 100);
  }, [mini, docs, query]);

  const loading = query !== "" && docs === null;

  return (
    <main className={styles.main}>
      {!query && <p className={styles.count}>검색어를 입력해 주세요.</p>}
      {loading && <p className={styles.count}>발언 색인을 불러오는 중…</p>}
      {query && !loading && (
        <p className={styles.count}>
          &lsquo;{query}&rsquo; 검색 결과 {results.length}건
          {results.length === 100 && " (상위 100건 표시)"}
        </p>
      )}
      <ol className={styles.list}>
        {results.map((doc) => (
          <li key={doc.sid} className={styles.item}>
            <p className={styles.meta}>
              {doc.meeting_title} · {formatDate(doc.date)}
              {doc.speaker_name && <span className={styles.speaker}> · {doc.speaker_name}</span>}
            </p>
            <blockquote className={styles.quote}>
              <QuoteText text={doc.text} raw={doc.text} corrected={false} highlight={query} />
            </blockquote>
            <PlayLink sid={doc.sid} meetingId={doc.meeting_id} startSec={doc.start_sec} />
          </li>
        ))}
      </ol>
      {query && results.length > 0 && (
        <p className={styles.notice}>
          발언 문장은 유튜브 자동자막 기반으로 오인식이 있을 수 있습니다. 원문 구간 재생으로
          확인해 주세요.
        </p>
      )}
    </main>
  );
}
