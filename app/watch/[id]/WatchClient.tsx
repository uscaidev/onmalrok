"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Meeting, Speaker, Statement } from "@/lib/types";
import AiLabel from "@/components/AiLabel";
import AiNotice from "@/components/AiNotice";
import PlayLink from "@/components/PlayLink";
import QuoteText from "@/components/QuoteText";
import { formatDate, formatSec, kindLabel, statusLabel } from "@/lib/format";
import styles from "./WatchClient.module.css";

declare global {
  interface Window {
    YT?: {
      Player: new (el: HTMLElement, opts: object) => YTPlayer;
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

interface YTPlayer {
  seekTo(sec: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  playVideo(): void;
  destroy(): void;
}

export default function WatchClient({ meeting }: { meeting: Meeting }) {
  const searchParams = useSearchParams();
  const startAt = Number(searchParams.get("t") ?? 0) || 0;

  const playerHostRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const panelRef = useRef<HTMLOListElement>(null);
  const [currentSec, setCurrentSec] = useState(startAt);
  const [panelQuery, setPanelQuery] = useState("");

  // YouTube IFrame Player 초기화
  useEffect(() => {
    let disposed = false;
    let poll: ReturnType<typeof setInterval> | undefined;

    const create = () => {
      if (disposed || !playerHostRef.current || !window.YT) return;
      playerRef.current = new window.YT.Player(playerHostRef.current, {
        videoId: meeting.youtube_id,
        playerVars: { start: startAt, rel: 0 },
        events: {
          onReady: () => {
            poll = setInterval(() => {
              const t = playerRef.current?.getCurrentTime?.();
              if (typeof t === "number" && !Number.isNaN(t)) setCurrentSec(t);
            }, 500);
          },
        },
      });
    };

    if (window.YT?.Player) {
      create();
    } else {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        prev?.();
        create();
      };
      if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    }

    return () => {
      disposed = true;
      if (poll) clearInterval(poll);
      playerRef.current?.destroy?.();
      playerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meeting.youtube_id]);

  const seek = (sec: number) => {
    playerRef.current?.seekTo(sec, true);
    playerRef.current?.playVideo();
    setCurrentSec(sec);
  };

  // 현재 재생 중인 문장 = start_sec가 currentSec 이하인 마지막 문장
  const activeIdx = useMemo(() => {
    let idx = -1;
    for (let i = 0; i < meeting.statements.length; i++) {
      if (meeting.statements[i].start_sec <= currentSec) idx = i;
      else break;
    }
    return idx;
  }, [meeting.statements, currentSec]);

  // 활성 문장 자동 추적 스크롤
  useEffect(() => {
    if (activeIdx < 0 || !panelRef.current) return;
    const el = panelRef.current.children[activeIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIdx]);

  const query = panelQuery.trim();
  const matchCount = query
    ? meeting.statements.filter((s) => s.text.includes(query)).length
    : 0;

  // 재생바 ◆ 마커 = thread_refs 있는 문장 위치 (§6.2)
  const markers = meeting.statements.filter((s) => s.thread_refs.length > 0);

  const bySid = useMemo(() => {
    const map = new Map<string, Statement>();
    for (const s of meeting.statements) map.set(s.sid, s);
    return map;
  }, [meeting.statements]);

  // 화자는 Turn에만 있다 — 문장의 화자 = 소속 Turn의 화자 (SPEC-PIPELINE.md §2.2)
  const speakerByTurn = useMemo(() => {
    const map = new Map<string, Speaker | null>();
    for (const t of meeting.turns) map.set(t.tid, t.speaker);
    return map;
  }, [meeting.turns]);

  const speakerOf = (s: Statement): Speaker | null =>
    s.turn_id ? speakerByTurn.get(s.turn_id) ?? null : null;

  const hasAiInferred =
    meeting.turns.some((t) => t.speaker?.inferred && !t.speaker.verified) ||
    meeting.statements.some((s) => s.thread_refs.length > 0);

  return (
    <main className={styles.layout}>
      <section className={styles.primary}>
        <div className={styles.playerBox}>
          <div ref={playerHostRef} className={styles.playerHost} />
        </div>
        {markers.length > 0 && (
          <div className={styles.markerBar} aria-label="스레드 연결 문장 위치">
            {markers.map((s) => (
              <button
                key={s.sid}
                type="button"
                className={styles.marker}
                style={{ left: `${(s.start_sec / meeting.duration_sec) * 100}%` }}
                onClick={() => seek(s.start_sec)}
                aria-label={`${formatSec(s.start_sec)} 스레드 연결 문장으로 이동`}
              >
                ◆
              </button>
            ))}
          </div>
        )}

        <h1 className={styles.title}>{meeting.title}</h1>
        <p className={styles.meta}>
          {kindLabel(meeting.kind)} · {formatDate(meeting.date)} · 발언{" "}
          {meeting.stats.statement_count}건
          {statusLabel(meeting.pipeline_status) && (
            <span className={styles.pendingBadge}>{statusLabel(meeting.pipeline_status)}</span>
          )}
        </p>

        {meeting.summary && (
          <section className={styles.summaryCard}>
            <div className={styles.summaryHead}>
              <AiLabel type="summary" />
            </div>
            {(
              meeting.summary.paragraphs ??
              // 파이프라인이 brief만 준 경우 — 요약도 원문 구간 재생으로 끝나야 한다 (§9-3)
              [{ text: meeting.summary.brief, sids: meeting.statements.slice(0, 1).map((s) => s.sid) }]
            ).map((p, i) => {
              const evidence = p.sids[0] ? bySid.get(p.sids[0]) : undefined;
              return (
                <p key={i} className={styles.summaryPara}>
                  {p.text}{" "}
                  {evidence && (
                    <PlayLink
                      sid={evidence.sid}
                      meetingId={meeting.id}
                      startSec={evidence.start_sec}
                    />
                  )}
                </p>
              );
            })}
          </section>
        )}

        {meeting.agenda.length > 0 && (
          <div className={styles.chapters}>
            {meeting.agenda.map((a) => (
              <button
                key={a.aid}
                type="button"
                className={styles.chapterChip}
                onClick={() => seek(a.start_sec)}
              >
                <span className={styles.chapterTime}>{formatSec(a.start_sec)}</span> {a.title}
              </button>
            ))}
          </div>
        )}
      </section>

      <aside className={styles.panel} aria-label="자막 패널">
        <div className={styles.panelHead}>
          <input
            className={styles.panelSearch}
            type="search"
            value={panelQuery}
            onChange={(e) => setPanelQuery(e.target.value)}
            placeholder="자막 내 검색"
            aria-label="자막 내 검색"
          />
          {query && <span className={styles.panelCount}>{matchCount}건</span>}
        </div>
        <ol ref={panelRef} className={styles.statements}>
          {meeting.statements.map((s, i) => {
            const speaker = speakerOf(s);
            return (
            <li
              key={s.sid}
              className={`${styles.statement} ${i === activeIdx ? styles.active : ""}`}
            >
              <button type="button" className={styles.statementBtn} onClick={() => seek(s.start_sec)}>
                <span className={styles.timestamp}>{formatSec(s.start_sec)}</span>
                <span className={styles.statementBody}>
                  <span className={styles.speakerLine}>
                    {speaker ? (
                      <>
                        <span className={styles.speakerName}>{speaker.name}</span>
                        {speaker.verified ? (
                          <span className={styles.verifiedBadge}>✓ 시민 검증</span>
                        ) : (
                          speaker.inferred && <AiLabel type="speaker" />
                        )}
                      </>
                    ) : (
                      <span className={styles.speakerUnknown}>화자 미상</span>
                    )}
                  </span>
                  <QuoteText
                    text={s.text}
                    raw={s.text_raw}
                    corrected={s.corrected}
                    highlight={query || undefined}
                  />
                </span>
              </button>
            </li>
            );
          })}
        </ol>
        <div className={styles.panelFoot}>
          <p className={styles.captionNotice}>
            발언 문장은 유튜브 자동자막 기반으로 오인식이 있을 수 있습니다. 원문 구간 재생으로
            확인해 주세요.
          </p>
          {hasAiInferred && <AiNotice />}
        </div>
      </aside>
    </main>
  );
}
