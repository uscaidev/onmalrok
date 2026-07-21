import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AiNotice from "@/components/AiNotice";
import GradeBadge from "@/components/GradeBadge";
import PlayLink from "@/components/PlayLink";
import QuoteText from "@/components/QuoteText";
import { getMeeting, getTaskMap, getTasks, getThreadsByIds } from "@/lib/data";
import { formatDate, kindLabel } from "@/lib/format";
import { SITE_URL } from "@/lib/site";
import type { Meeting, ThreadStage } from "@/lib/types";
import styles from "./TaskDetail.module.css";

export async function generateStaticParams() {
  const tasks = await getTasks();
  return tasks.map((t) => ({ no: String(t.no) }));
}

export async function generateMetadata({ params }: { params: { no: string } }): Promise<Metadata> {
  const [tasks, map] = await Promise.all([getTasks(), getTaskMap()]);
  const task = tasks.find((t) => String(t.no) === params.no);
  if (!task) return { title: "국정과제" };
  const refs = map.find((e) => e.task_no === task.no)?.turn_refs ?? [];
  const last = refs.length > 0 ? refs[refs.length - 1].date : null;
  // AEO: "이 과제 어떻게 되고 있나" 질문에 바로 답하는 사실형 요약
  const mention = last
    ? `국무회의·업무보고 언급 ${refs.length}건(마지막 ${formatDate(last).replace(/\.$/, "")})`
    : "국무회의·업무보고 언급 0회";
  return {
    title: `국정과제 ${task.no}. ${task.title} — 발언 기록`,
    description: `주관 ${task.ministries.join("·")} · ${task.goal} · ${mention}. 대통령 발언·부처 보고 인용과 원문 구간 재생 제공.`,
  };
}

// §6.3 준용 상태 어휘 (평가 어휘 금지 — §1-5)
const STAGE_LABEL: Record<ThreadStage, string> = {
  order: "지시",
  plan: "계획 보고",
  progress: "경과 보고",
  result: "이행 결과 보고",
  followup_pending: "후속 대기",
};

export default async function TaskPage({ params }: { params: { no: string } }) {
  const no = Number(params.no);
  const [tasks, map] = await Promise.all([getTasks(), getTaskMap()]);
  const task = tasks.find((t) => t.no === no);
  if (!task) notFound();
  const entry = map.find((e) => e.task_no === no);
  const refs = entry?.turn_refs ?? [];
  const threads = await getThreadsByIds(entry?.thread_ids ?? []);

  // 타임라인 해석: ref(tid) → 회의·턴·대표 문장 (종착점은 원문 구간 재생 — §1-2)
  const meetingIds = [...new Set([...refs.map((r) => r.meeting_id), ...threads.map((t) => t.nodes[t.nodes.length - 1].meeting_id)])];
  const meetings = new Map<string, Meeting>();
  for (const id of meetingIds) {
    const m = await getMeeting(id);
    if (m) meetings.set(id, m);
  }
  const timeline = refs
    .map((ref) => {
      const meeting = meetings.get(ref.meeting_id);
      const turn = meeting?.turns.find((t) => t.tid === ref.tid);
      const stmt = turn && meeting?.statements.find((s) => s.sid === turn.rep_sid);
      if (!meeting || !turn || !stmt) return null;
      return { ref, meeting, turn, stmt };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null)
    .sort((a, b) => (a.ref.date < b.ref.date ? -1 : 1)); // 시간축은 과거→미래만 (§1-3)

  const hasAiInferred = refs.some((r) => r.grade === "ai_inferred");

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "국정과제", item: `${SITE_URL}/tasks` },
      { "@type": "ListItem", position: 2, name: task.goal },
      {
        "@type": "ListItem",
        position: 3,
        name: `${task.no}. ${task.title}`,
        item: `${SITE_URL}/tasks/${task.no}`,
      },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <main className={styles.main}>
        <nav className={styles.crumb}>
          <Link href="/tasks">국정과제</Link> · {task.goal} · {task.strategy}
        </nav>
        <h1 className={styles.title}>
          <span className={styles.no}>{task.no}</span>
          {task.title}
        </h1>
        <p className={styles.meta}>
          주관 {task.ministries.join(" · ")} ·{" "}
          <a className={styles.srcLink} href={task.source} target="_blank" rel="noopener noreferrer">
            공식 과제 자료 ↗
          </a>
        </p>
        <p className={styles.status}>
          관련 발언 {refs.length}건
          {threads.length > 0 && ` · 지시 스레드 ${threads.length}개`}
          {timeline.length > 0 && ` · 마지막 언급 ${formatDate(timeline[timeline.length - 1].ref.date)}`}
        </p>

        {threads.length > 0 && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>지시 스레드</h2>
            {threads.map((th) => {
              const lastNode = th.nodes[th.nodes.length - 1];
              const m = meetings.get(lastNode.meeting_id);
              const stmt = m?.statements.find((s) => s.sid === lastNode.rep_sid);
              return (
                <div key={th.id} className={styles.threadCard}>
                  <div className={styles.threadHead}>
                    <span className={styles.threadTitle}>{th.title}</span>
                    <span className={styles.threadStage}>
                      {STAGE_LABEL[th.stage]} · 기록 {th.nodes.length}건 · {formatDate(lastNode.date)}
                    </span>
                  </div>
                  {stmt && (
                    <PlayLink sid={stmt.sid} meetingId={lastNode.meeting_id} startSec={stmt.start_sec} />
                  )}
                </div>
              );
            })}
          </section>
        )}

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>발언 기록</h2>
          {timeline.length === 0 ? (
            <p className={styles.empty}>
              이 과제가 국무회의·업무보고 발언에서 언급된 기록이 아직 없습니다. 기록이 확인되면
              자동으로 추가됩니다.
            </p>
          ) : (
            <ol className={styles.timeline}>
              {timeline.map(({ ref, meeting, turn, stmt }) => (
                <li key={ref.tid} className={styles.item}>
                  <div className={styles.itemHead}>
                    <span className={styles.itemDate}>{formatDate(ref.date)}</span>
                    <span className={styles.itemMeeting}>
                      {kindLabel(meeting.kind)}
                      {turn.speaker && (
                        <>
                          {" · "}
                          <span className={styles.speaker}>{turn.speaker.name}</span>
                          {turn.speaker.inferred && !turn.speaker.verified && (
                            <span className={styles.inferred}> 화자 AI 추정</span>
                          )}
                        </>
                      )}
                    </span>
                    <GradeBadge grade={ref.grade} />
                  </div>
                  <blockquote className={styles.quote}>
                    <QuoteText text={stmt.text} raw={stmt.text_raw} corrected={stmt.corrected} />
                  </blockquote>
                  {ref.grade_evidence && (
                    <p className={styles.evidence}>근거: {ref.grade_evidence}</p>
                  )}
                  <PlayLink sid={stmt.sid} meetingId={meeting.id} startSec={stmt.start_sec} />
                </li>
              ))}
            </ol>
          )}
        </section>

        {hasAiInferred && <AiNotice />}
      </main>
    </>
  );
}
