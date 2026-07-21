"""07 threads: 회의 간 지시→보고 연결 (SPEC-PIPELINE.md §4 #07, §2.3 / SPEC.md §8.2 3단 판정).

- 신규 스레드 생성: 대통령 화자 Turn의 명령형 지시에서만 (LLM 추출)
- 연결 3단 판정 (Turn 단위): ①룰 정규식 → explicit ②topic_tags 2개 이상 → topic
  ③후보쌍(태그 1개 일치) LLM 판정 → ai_inferred(reviewed=false)
- ThreadNode는 §2.3의 turn 참조 형태: {tid, rep_sid, meeting_id, date, role, ...}
"""
import re
import sys
from datetime import datetime

from . import llm
from .config import DATA_DIR, KST
from .state import load_state, save_state
from .util import load_json, load_meeting, parse_json_response, save_json, save_meeting, seq_of

THREADS_DIR = DATA_DIR / "threads"
RULE_PATTERN = re.compile(r"지난\s*(회의|[0-9]+월)|지시하신|말씀하신|당부하신|주문하신")
MAX_TURN_CHARS = 700       # LLM 입력용 턴 텍스트 상한
MAX_JUDGE_PAIRS = 30       # 판정 호출당 후보쌍 상한
ROLE_STAGE = {"order": "order", "report": "plan", "interim": "progress", "result": "result"}


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def turn_text(meeting: dict, turn: dict) -> str:
    a, b = seq_of(turn["sid_range"][0]), seq_of(turn["sid_range"][1])
    text = " ".join(s["text"] for s in meeting["statements"] if a <= seq_of(s["sid"]) <= b)
    return text[:MAX_TURN_CHARS]


def is_president(turn: dict) -> bool:
    name = (turn.get("speaker") or {}).get("name") or ""
    return "대통령" in name and "권한대행" not in name and "대변인" not in name


def _load_threads() -> dict[str, dict]:
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    return {p.stem: load_json(p, None) for p in THREADS_DIR.glob("*.json")}


def _add_ref(meeting: dict, rep_sid: str, thread_id: str, grade: str) -> None:
    stmt = next((s for s in meeting["statements"] if s["sid"] == rep_sid), None)
    if stmt is not None and not any(r["thread_id"] == thread_id for r in stmt["thread_refs"]):
        stmt["thread_refs"].append({"thread_id": thread_id, "grade": grade})


def _add_node(thread: dict, node: dict) -> bool:
    if any(n["tid"] == node["tid"] for n in thread["nodes"]):
        return False
    thread["nodes"].append(node)
    thread["nodes"].sort(key=lambda n: n["date"])
    thread["stage"] = ROLE_STAGE.get(thread["nodes"][-1]["role"], thread["stage"])
    thread["updated_at"] = _now()
    return True


def _slugify(slug: str, taken: set) -> str:
    slug = re.sub(r"[^a-z0-9-]", "", slug.lower().replace(" ", "-")) or "thread"
    base, n = slug, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    return slug


def extract_orders(meeting: dict, threads: dict) -> set:
    """대통령 턴에서 지시 추출 → 신규 스레드. 이번 회의에서 생성된 thread id 집합 반환."""
    pres = [t for t in meeting["turns"] if is_president(t)]
    if not pres:
        return set()
    listing = "\n\n".join(f"[{t['tid']}] {turn_text(meeting, t)}" for t in pres)
    prompt = llm.load_prompt("threads_orders").replace("{turns}", listing)
    orders = parse_json_response(llm.complete(prompt, stage="threads", max_tokens=4000))["orders"]

    created = set()
    tids = {t["tid"] for t in pres}
    for o in orders:
        tid = o.get("tid")
        if tid not in tids or not o.get("title"):
            continue
        slug = _slugify(str(o.get("slug") or o["title"]), set(threads))
        rep = o.get("rep")
        turn = next(t for t in meeting["turns"] if t["tid"] == tid)
        a, b = seq_of(turn["sid_range"][0]), seq_of(turn["sid_range"][1])
        rep_sid = f"{meeting['id']}#{rep}" if isinstance(rep, int) and a <= rep <= b else turn["rep_sid"]
        threads[slug] = {
            "id": slug,
            "title": str(o["title"])[:30],
            "topic_tags": [str(t) for t in (o.get("tags") or [])][:6],
            "stage": "order",
            "nodes": [{
                "tid": tid, "rep_sid": rep_sid, "meeting_id": meeting["id"],
                "date": meeting["date"], "role": "order", "grade": "explicit",
                "grade_evidence": str(o.get("evidence") or "")[:60],
                "reviewed": True, "rel_label": "지시",
            }],
            "followup": None,
            "updated_at": _now(),
        }
        _add_ref(meeting, rep_sid, slug, "explicit")
        created.add(slug)
    return created


def _heuristic_role(text: str) -> tuple[str, str]:
    if re.search(r"완료|마쳤|마무리했|결과를 보고", text):
        return "result", "지시 이행 결과 보고"
    if re.search(r"계획|추진하겠|마련하겠|하겠습니다", text):
        return "report", "지시에 대한 추진 계획 보고"
    return "interim", "관련 경과 보고"


def link_meeting(meeting: dict, threads: dict, skip: set) -> int:
    """이 회의의 턴들을 기존 스레드에 연결. 추가된 노드 수 반환."""
    added = 0
    judge_pairs = []  # (pair_no, thread_id, turn, evidence_tag)

    for turn in meeting["turns"]:
        text = turn_text(meeting, turn)
        links = 0
        for th_id, th in threads.items():
            if th_id in skip or links >= 2:
                continue
            if th["nodes"] and th["nodes"][0]["meeting_id"] == meeting["id"]:
                continue
            tags = [t for t in th.get("topic_tags", []) if t]
            hits = [t for t in tags if t in text]
            if len(hits) >= 2:
                rule = RULE_PATTERN.search(text)
                role, rel = _heuristic_role(text)
                node = {
                    "tid": turn["tid"], "rep_sid": turn["rep_sid"],
                    "meeting_id": meeting["id"], "date": meeting["date"],
                    "role": role,
                    "grade": "explicit" if rule else "topic",
                    "grade_evidence": (text[max(rule.start() - 10, 0):rule.end() + 20]
                                       if rule else " · ".join(hits[:3]))[:60],
                    "reviewed": True,
                    "rel_label": rel,
                }
                if _add_node(th, node):
                    _add_ref(meeting, turn["rep_sid"], th_id, node["grade"])
                    added += 1
                    links += 1
            elif len(hits) == 1 and len(judge_pairs) < MAX_JUDGE_PAIRS:
                judge_pairs.append((len(judge_pairs) + 1, th_id, turn, hits[0]))

    # ③ LLM 판정 (후보쌍 일괄)
    if judge_pairs:
        listing = "\n\n".join(
            f"{no}. [스레드] {threads[tid]['title']} (태그: {', '.join(threads[tid]['topic_tags'])})"
            f" — 최근: {threads[tid]['nodes'][-1]['rel_label']}\n   [새 발언] {turn_text(meeting, turn)[:400]}"
            for no, tid, turn, _ in judge_pairs
        )
        prompt = llm.load_prompt("threads_judge").replace("{pairs}", listing)
        try:
            links = parse_json_response(
                llm.complete(prompt, stage="threads", max_tokens=3000))["links"]
        except Exception as e:
            print(f"[threads] {meeting['id']} 판정 실패: {e}", flush=True)
            links = []
        by_no = {no: (tid, turn) for no, tid, turn, _ in judge_pairs}
        for lk in links:
            pair = by_no.get(lk.get("pair"))
            if pair is None:
                continue
            th_id, turn = pair
            role = lk.get("role") if lk.get("role") in ("report", "interim", "result") else "interim"
            node = {
                "tid": turn["tid"], "rep_sid": turn["rep_sid"],
                "meeting_id": meeting["id"], "date": meeting["date"],
                "role": role, "grade": "ai_inferred",
                "grade_evidence": str(lk.get("evidence") or "")[:60],
                "reviewed": False,
                "rel_label": str(lk.get("rel_label") or "관련 보고")[:20],
            }
            if _add_node(threads[th_id], node):
                _add_ref(meeting, turn["rep_sid"], th_id, "ai_inferred")
                added += 1
    return added


def run(state: dict) -> None:
    if not llm.available():
        return
    recs = [
        r for r in state["videos"].values()
        if r["status"] == "processed" and r.get("meeting_id")
        and r["stages"].get("turns") == "done" and r["stages"].get("threads") != "done"
    ]
    if not recs:
        return
    threads = {k: v for k, v in _load_threads().items() if v}
    # 시간순 처리 — 과거 지시가 먼저 스레드로 존재해야 후속 연결 가능
    for rec in sorted(recs, key=lambda r: r.get("published_at") or ""):
        mid = rec["meeting_id"]
        meeting = load_meeting(mid)
        if meeting is None or not meeting.get("turns"):
            continue
        try:
            created = extract_orders(meeting, threads)
            added = link_meeting(meeting, threads, skip=created)
            rec["stages"]["threads"] = "done"
            save_meeting(meeting)
            save_state(state)
            print(f"[threads] {mid} 신규 {len(created)} / 연결 {added}", flush=True)
        except Exception as e:
            print(f"[threads] {mid} 실패: {e}", flush=True)
    for th_id, th in threads.items():
        save_json(THREADS_DIR / f"{th_id}.json", th)
    print(f"[threads] 스레드 총 {len(threads)}개", flush=True)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    state = load_state()
    run(state)
    save_state(state)


if __name__ == "__main__":
    main()
