/** 초 → "mm:ss" 또는 "h:mm:ss" (유튜브 표기) */
export function formatSec(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}

/** "2026-07-16" → "2026. 7. 16." */
export function formatDate(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return `${y}. ${m}. ${d}.`;
}

export function kindLabel(kind: "cabinet" | "report"): string {
  return kind === "cabinet" ? "국무회의" : "업무보고";
}

/** pipeline_status별 노출 배지 (SPEC.md §8 — 숨기지 않고 노출). done은 배지 없음 */
export function statusLabel(status: string): string | null {
  if (status === "done") return null;
  if (status === "waiting_captions") return "자막 대기";
  return "처리 대기"; // partial | failed | 그 외
}
