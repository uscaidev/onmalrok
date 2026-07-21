"""12 agenda_view: 홈 "지금 활발한 의제" 인덱스 (SPEC-PIPELINE.md §2.5, §4 #12).

- 결정적 부분(분야 매칭·seed/latest 조인·node_dates)은 코드로 — 멱등
- 흐름 브리프(briefs)만 LLM. 실패·키 없음 시 기존 agenda.json의 briefs 유지
- 미분류(etc) 스레드에 대해 fields.json 키워드 추가 제안(proposals) 기록 — 적용은 사람 PR
"""
import sys
from datetime import date, datetime

from . import llm
from .config import DATA_DIR, KST, MEETINGS_DIR
from .util import load_json, parse_json_response, save_json

THREADS_DIR = DATA_DIR / "threads"
FIELDS_FILE = DATA_DIR / "fields.json"
AGENDA_FILE = DATA_DIR / "index" / "agenda.json"
WINDOWS = (28, 90, 180)
MAX_FIELDS_PER_THREAD = 2
SEED_QUOTE_MAX = 70
PLAY_LEAD_SEC = 3   # rep_sid가 인접 문장으로 어긋나는 사례 대비 (§2.5)


def _speaker_of(meeting: dict, tid: str) -> str | None:
    turn = next((t for t in meeting.get("turns", []) if t["tid"] == tid), None)
    return (turn.get("speaker") or {}).get("name") if turn else None


def _start_sec(meeting: dict, rep_sid: str) -> int:
    stmt = next((s for s in meeting["statements"] if s["sid"] == rep_sid), None)
    return max(0, int(stmt["start_sec"]) - PLAY_LEAD_SEC) if stmt else 0


def _node_view(node: dict, meetings: dict) -> dict | None:
    m = meetings.get(node["meeting_id"])
    if m is None:
        return None
    return {
        "date": node["date"],
        "speaker": _speaker_of(m, node["tid"]),
        "rel_label": node.get("rel_label") or "",
        "meeting_id": m["id"],
        "youtube_id": m["youtube_id"],
        "t": _start_sec(m, node["rep_sid"]),
    }


def match_fields(thread: dict, fields: list[dict]) -> list[str]:
    """topic_tags + title 키워드 포함 검사 (결정적). 미매치 → ["etc"]."""
    text = " ".join(thread.get("topic_tags", [])) + " " + thread["title"]
    hits = [f["id"] for f in fields if any(kw in text for kw in f["keywords"])]
    return hits[:MAX_FIELDS_PER_THREAD] or ["etc"]


def build_threads(threads: list[dict], meetings: dict, fields: list[dict]) -> list[dict]:
    out = []
    for th in threads:
        nodes = sorted(th["nodes"], key=lambda n: n["date"])
        if not nodes:
            continue
        seed_node = next((n for n in nodes if n.get("grade") == "explicit"), nodes[0])
        seed = _node_view(seed_node, meetings)
        latest = _node_view(nodes[-1], meetings)
        if seed is None or latest is None:
            continue
        seed = {**seed, "quote": (seed_node.get("grade_evidence") or "")[:SEED_QUOTE_MAX]}
        seed.pop("rel_label", None)
        out.append({
            "id": th["id"], "title": th["title"], "stage": th.get("stage", "order"),
            "field_ids": match_fields(th, fields),
            "node_dates": [n["date"] for n in nodes],
            "seed": seed, "latest": latest,
        })
    return out


def _window_threads(entries: list[dict], ref: date, days: int) -> list[dict]:
    active = []
    for e in entries:
        cnt = sum(1 for d in e["node_dates"]
                  if (ref - date.fromisoformat(d)).days <= days)
        if cnt:
            first = date.fromisoformat(e["node_dates"][0])
            active.append({**e, "_count": cnt, "_new": (ref - first).days <= days})
    active.sort(key=lambda e: e["_count"], reverse=True)
    return active


def build_briefs(entries: list[dict], ref: date, prev: list[dict]) -> list[dict]:
    """기간별 흐름 브리프 — LLM. 키 없음·실패 시 기존 briefs 유지 (§8 무너지지 않는 실패)."""
    if not llm.available():
        print("[agenda_view] LLM 키 없음 — briefs 기존값 유지", flush=True)
        return prev
    briefs = []
    prev_by_days = {b["window_days"]: b for b in prev}
    for days in WINDOWS:
        active = _window_threads(entries, ref, days)
        listing = "\n".join(
            f"- [{e['id']}] {e['title']} · 발언 {e['_count']}건"
            f"{' · 이 기간 신규' if e['_new'] else ''} · 마지막 {e['node_dates'][-1]}"
            for e in active[:40]
        )
        prompt = (llm.load_prompt("agenda_brief")
                  .replace("{window}", f"최근 {days}일 ({ref.isoformat()} 기준)")
                  .replace("{threads}", listing or "(활동 스레드 없음)"))
        try:
            items = parse_json_response(
                llm.complete(prompt, stage="agenda_view", max_tokens=2000))["items"]
            valid_ids = {e["id"] for e in active}
            items = [
                {"text": str(i["text"])[:200],
                 "thread_ids": [t for t in i.get("thread_ids", []) if t in valid_ids]}
                for i in items if i.get("text")
            ]
            items = [i for i in items if i["thread_ids"]][:5]   # 근거 없는 항목 제거 (§2.5)
            briefs.append({"window_days": days, "items": items})
        except Exception as e:
            print(f"[agenda_view] {days}일 브리프 실패: {e}", flush=True)
            briefs.append(prev_by_days.get(days, {"window_days": days, "items": []}))
    return briefs


def build_proposals(entries: list[dict], threads_by_id: dict, table: dict) -> list[dict]:
    """미분류 스레드 → 키워드 추가 제안. fields.json의 proposals에만 기록(자동 적용 금지)."""
    etc = [e for e in entries if e["field_ids"] == ["etc"]]
    if not etc or not llm.available():
        return table.get("proposals", [])
    listing = "\n".join(
        f"- [{e['id']}] {e['title']} · 태그: {', '.join(threads_by_id[e['id']].get('topic_tags', []))}"
        for e in etc
    )
    field_desc = "\n".join(f"- {f['id']}: {f['label']}" for f in table["fields"])
    prompt = (llm.load_prompt("fields_propose")
              .replace("{fields}", field_desc).replace("{threads}", listing))
    try:
        proposals = parse_json_response(
            llm.complete(prompt, stage="agenda_view", max_tokens=2000))["proposals"]
        valid_fields = {f["id"] for f in table["fields"]}
        valid_threads = {e["id"] for e in etc}
        return [
            {"field_id": p["field_id"], "keyword": str(p["keyword"])[:20],
             "reason": str(p.get("reason") or "")[:80], "thread_id": p["thread_id"]}
            for p in proposals
            if p.get("field_id") in valid_fields and p.get("thread_id") in valid_threads
            and p.get("keyword")
        ]
    except Exception as e:
        print(f"[agenda_view] 분야 제안 실패: {e}", flush=True)
        return table.get("proposals", [])


def validate_agenda(agenda: dict, table: dict) -> list[str]:
    """SPEC-PIPELINE.md §7 항목 5."""
    errors = []
    valid_fields = {f["id"] for f in table["fields"]} | {"etc"}
    thread_ids = {t["id"] for t in agenda["threads"]}
    for t in agenda["threads"]:
        if not set(t["field_ids"]) <= valid_fields:
            errors.append(f"{t['id']}: field_ids 미정의 값 {t['field_ids']}")
        for key in ("seed", "latest"):
            if not t[key].get("youtube_id") or not (MEETINGS_DIR / f"{t[key]['meeting_id']}.json").exists():
                errors.append(f"{t['id']}: {key} 참조 회의 없음")
    for b in agenda["briefs"]:
        for i in b["items"]:
            if not i["thread_ids"] or not set(i["thread_ids"]) <= thread_ids:
                errors.append(f"브리프({b['window_days']}일): thread_ids 불량")
    return errors


def run() -> None:
    table = load_json(FIELDS_FILE, None)
    if table is None:
        print("[agenda_view] data/fields.json 없음 — 건너뜀", flush=True)
        return
    threads = [t for t in (load_json(p, None) for p in sorted(THREADS_DIR.glob("*.json"))) if t]
    meetings = {p.stem: load_json(p, None) for p in MEETINGS_DIR.glob("*.json")}
    if not threads or not meetings:
        print("[agenda_view] 스레드/회의 없음 — 건너뜀", flush=True)
        return

    ref = max(m["date"] for m in meetings.values())
    entries = build_threads(threads, meetings, table["fields"])
    prev = load_json(AGENDA_FILE, {}).get("briefs", [])
    briefs = build_briefs(entries, date.fromisoformat(ref), prev)

    field_counts = {}
    for e in entries:
        for fid in e["field_ids"]:
            field_counts[fid] = field_counts.get(fid, 0) + 1
    fields_out = [{"id": f["id"], "label": f["label"],
                   "thread_count": field_counts.get(f["id"], 0)} for f in table["fields"]]
    fields_out.append({"id": "etc", "label": "미분류",
                       "thread_count": field_counts.get("etc", 0)})

    agenda = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "ref_date": ref,
        "fields": fields_out,
        "threads": [{k: v for k, v in e.items() if not k.startswith("_")} for e in entries],
        "briefs": briefs,
    }
    errors = validate_agenda(agenda, table)
    if errors:
        print(f"[agenda_view] 검증 경고 {len(errors)}건: {'; '.join(errors[:5])}", flush=True)

    table["proposals"] = build_proposals(entries, {t["id"]: t for t in threads}, table)
    save_json(FIELDS_FILE, table)
    save_json(AGENDA_FILE, agenda)
    etc_rate = field_counts.get("etc", 0) / len(entries) * 100
    print(f"[agenda_view] 스레드 {len(entries)} · 미분류 {field_counts.get('etc', 0)}"
          f"({etc_rate:.0f}%) · 브리프 {sum(len(b['items']) for b in briefs)}항목"
          f" · 제안 {len(table['proposals'])}건", flush=True)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run()


if __name__ == "__main__":
    main()
