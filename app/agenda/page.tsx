import type { Metadata } from "next";
import SiteHeader from "@/components/SiteHeader";
import AgendaSection from "../AgendaSection";
import { getAgenda } from "@/lib/data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "지금 활발한 의제",
  description:
    "국무회의·업무보고에서 발언이 이어지고 있는 정책 의제 — 기간·분야별 활동 기록과 원문 구간 재생",
};

export default async function AgendaPage() {
  const agenda = await getAgenda();

  return (
    <>
      <SiteHeader />
      <main>
        <div className={styles.pageHead}>
          <h1 className={styles.pageTitle}>지금 활발한 의제</h1>
          <p className={styles.pageMeta}>
            대통령 지시로 시작된 스레드 {agenda?.threads.length ?? 0}개 · 기간·분야별 활동 기록 ·
            기준일 {agenda?.ref_date ?? "-"}
          </p>
        </div>
        {agenda ? (
          <AgendaSection agenda={agenda} limit={20} showTitle={false} />
        ) : (
          <p className={styles.empty}>의제 데이터가 아직 생성되지 않았습니다.</p>
        )}
      </main>
    </>
  );
}
