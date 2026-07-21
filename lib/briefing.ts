// 부처 브리핑 파생 계산 (SPEC.md §0 — 2026-07-21 방향 확정).
// 파이프라인 산출물이 아니라 빌드 시 결정적 파생: LLM 없음, 항목마다 근거를 남긴다.
import type { GovTask, Meeting, TaskMapEntry } from "./types";

/** tasks.json 축약 부처명 → 발언·직함에 등장하는 표기 별칭 (짧은 표기 자체도 매칭에 쓴다) */
const MINISTRY_ALIASES: Record<string, string[]> = {
  감사원: ["감사원"],
  개인정보위: ["개인정보보호위원회", "개인정보위"],
  경찰청: ["경찰청"],
  공정위: ["공정거래위원회", "공정위"],
  과기정통부: ["과학기술정보통신부", "과기정통부", "과기부"],
  교육부: ["교육부"],
  국방부: ["국방부"],
  국조실: ["국무조정실", "국조실"],
  국토부: ["국토교통부", "국토부"],
  권익위: ["국민권익위원회", "권익위"],
  금융위: ["금융위원회", "금융위"],
  기획처: ["기획예산처", "기획처"],
  기후부: ["기후에너지환경부", "기후에너지부", "기후부"],
  노동부: ["고용노동부", "노동부"],
  농식품부: ["농림축산식품부", "농식품부"],
  동포청: ["재외동포청", "동포청"],
  문체부: ["문화체육관광부", "문체부"],
  방미통위: ["방송미디어통신위원회", "방미통위"],
  방사청: ["방위사업청", "방사청"],
  법무부: ["법무부"],
  보훈부: ["국가보훈부", "보훈부"],
  복지부: ["보건복지부", "복지부"],
  산업부: ["산업통상자원부", "산업통상부", "산업부"],
  성평등부: ["성평등가족부", "성평등부"],
  외교부: ["외교부"],
  인권위: ["국가인권위원회", "인권위"],
  인사처: ["인사혁신처", "인사처"],
  재경부: ["재정경제부", "재경부"],
  중기부: ["중소벤처기업부", "중기부"],
  통일부: ["통일부"],
  해수부: ["해양수산부", "해수부"],
  행복청: ["행정중심복합도시건설청", "행복청"],
  행안부: ["행정안전부", "행안부"],
};

export interface BriefingItem {
  sid: string; // 대표 문장 (인용·재생 기준)
  text: string;
  text_raw: string;
  corrected: boolean;
  start_sec: number;
  speaker: string | null;
  speaker_inferred: boolean;
  basis: string; // 판정 근거 — "호명" | "과제 N 소관" | "부처 화자"
}

export interface MinistryBriefing {
  ministry: string; // 축약 표기 (tasks.json 기준)
  directives: BriefingItem[]; // 지시사항 — 대통령 턴
  answers: BriefingItem[]; // 답변사항 — 해당 부처 화자 턴
}

const ns = (s: string) => s.replace(/\s+/g, "");

/** tasks.json의 "국조실 등" 같은 변형을 축약 표기로 정규화 */
function normalizeMinistry(m: string): string {
  return m.replace(/\s*등$/, "").trim();
}

function isPresident(name: string | undefined | null): boolean {
  return !!name && name.includes("대통령") && !name.includes("권한대행") && !name.includes("대변인");
}

export function buildBriefing(
  meeting: Meeting,
  tasks: GovTask[],
  map: TaskMapEntry[]
): MinistryBriefing[] {
  const stmtBySid = new Map(meeting.statements.map((s) => [s.sid, s]));
  const seq = (sid: string) => Number(sid.split("#")[1]);

  // 이 회의에서 과제 매핑된 턴: tid → 소관 부처 집합(과제 번호 포함)
  const taskByNo = new Map(tasks.map((t) => [t.no, t]));
  const tidTasks = new Map<string, { no: number; ministries: string[] }[]>();
  for (const entry of map) {
    for (const ref of entry.turn_refs) {
      if (ref.meeting_id !== meeting.id) continue;
      const task = taskByNo.get(entry.task_no);
      if (!task) continue;
      const list = tidTasks.get(ref.tid) ?? [];
      list.push({ no: task.no, ministries: task.ministries.map(normalizeMinistry) });
      tidTasks.set(ref.tid, list);
    }
  }

  const result = new Map<string, MinistryBriefing>();
  const get = (m: string): MinistryBriefing => {
    if (!result.has(m)) result.set(m, { ministry: m, directives: [], answers: [] });
    return result.get(m)!;
  };

  const toItem = (turn: Meeting["turns"][number], basis: string): BriefingItem | null => {
    const stmt = stmtBySid.get(turn.rep_sid);
    if (!stmt) return null;
    return {
      sid: stmt.sid,
      text: stmt.text,
      text_raw: stmt.text_raw,
      corrected: stmt.corrected,
      start_sec: stmt.start_sec,
      speaker: turn.speaker?.name ?? null,
      speaker_inferred: turn.speaker?.inferred ?? false,
      basis,
    };
  };

  for (const turn of meeting.turns ?? []) {
    const name = turn.speaker?.name ?? "";

    // 답변사항: 화자 직함에 부처 별칭이 들어 있는 턴 (사회자·대통령 제외)
    if (name && !isPresident(name) && name !== "사회자") {
      const nameNs = ns(name);
      for (const [ministry, aliases] of Object.entries(MINISTRY_ALIASES)) {
        if (aliases.some((a) => nameNs.includes(ns(a)))) {
          const item = toItem(turn, "부처 화자");
          if (item) get(ministry).answers.push(item);
          break; // 한 화자는 한 부처
        }
      }
      continue;
    }

    // 지시사항: 대통령 턴 — ① 발언 내 부처 호명 ② 과제 매핑 소관 부처
    if (isPresident(name)) {
      const a = seq(turn.sid_range[0]);
      const b = seq(turn.sid_range[1]);
      const textNs = ns(
        meeting.statements
          .filter((s) => seq(s.sid) >= a && seq(s.sid) <= b)
          .map((s) => s.text)
          .join(" ")
      );
      const matched = new Map<string, string>(); // ministry → basis
      for (const [ministry, aliases] of Object.entries(MINISTRY_ALIASES)) {
        if (aliases.some((al) => al.length >= 3 && textNs.includes(ns(al)))) {
          matched.set(ministry, "호명");
        }
      }
      for (const t of tidTasks.get(turn.tid) ?? []) {
        for (const m of t.ministries) {
          if (!matched.has(m)) matched.set(m, `과제 ${t.no} 소관`);
        }
      }
      for (const [ministry, basis] of matched) {
        const item = toItem(turn, basis);
        if (item) get(ministry).directives.push(item);
      }
    }
  }

  return [...result.values()]
    .filter((b) => b.directives.length > 0 || b.answers.length > 0)
    .sort(
      (x, y) =>
        y.directives.length + y.answers.length - (x.directives.length + x.answers.length) ||
        x.ministry.localeCompare(y.ministry, "ko")
    );
}
