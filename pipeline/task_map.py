"""11 task_map: 국정과제 매핑 (SPEC-PIPELINE.md §2.4, §4 #11).

- 판정은 Turn 단위 3단: ①과제명·"국정과제 N번" 직접 언급 → explicit
  ②과제 키워드 2개 이상 일치 → topic ③1개 일치 후보쌍 LLM 판정 → ai_inferred
- 과제 키워드는 tasks.json에서 LLM으로 생성해 tasks/keywords.json에 캐시(1회성)
- thread_ids는 결정적 파생(LLM 없음): 스레드 노드 tid가 과제 turn_refs에 있거나
  스레드 topic_tags가 과제 키워드와 2개 이상 겹치면 연결 — 매 실행 전체 재계산
- 전 123과제 entries 유지(빈 배열 포함) — "언급 0회"도 기록이다
"""
import re
import sys
from datetime import datetime

from . import llm
from .config import DATA_DIR, KST
from .state import load_state, save_state
from .util import load_json, load_meeting, parse_json_response, save_json, seq_of

TASKS_DIR = DATA_DIR / "tasks"
TASKS_FILE = TASKS_DIR / "tasks.json"
KEYWORDS_FILE = TASKS_DIR / "keywords.json"
MAP_FILE = TASKS_DIR / "map.json"
THREADS_DIR = DATA_DIR / "threads"

KEYWORD_BATCH = 45          # 키워드 생성 호출당 과제 수
MAX_JUDGE_PAIRS = 80        # 회의당 LLM 판정 후보쌍 총 상한
JUDGE_CHUNK = 30            # 판정 호출당 쌍 수 (토큰 상한 대비 분할)
MAX_DIRECT_PER_TURN = 3     # 턴 하나가 직접 매칭(explicit/topic)될 수 있는 과제 수 상한
NUM_PATTERN = re.compile(r"국정과제\s*(\d{1,3})\s*번")


def full_turn_text(meeting: dict, turn: dict) -> str:
    """매칭용 턴 전문 — threads.turn_text의 700자 상한은 LLM 입력용이라 매칭엔 쓰지 않는다."""
    a, b = seq_of(turn["sid_range"][0]), seq_of(turn["sid_range"][1])
    return " ".join(s["text"] for s in meeting["statements"] if a <= seq_of(s["sid"]) <= b)


def _ns(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _window(text: str, keyword: str, radius: int = 180) -> str:
    """판정 프롬프트용: 키워드 주변 발췌. 자막 띄어쓰기가 제각각이라 문자 사이 공백을 허용해 찾는다."""
    m = re.search(r"\s*".join(map(re.escape, _ns(keyword))), text)
    if m is None:
        return text[:radius * 2]
    return text[max(m.start() - radius, 0):m.end() + radius]


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def load_tasks() -> list[dict]:
    doc = load_json(TASKS_FILE, None)
    return (doc or {}).get("tasks") or []


def ensure_keywords(tasks: list[dict]) -> dict[int, list[str]]:
    """과제별 검색 키워드. 캐시 우선, 없는 과제만 LLM 생성."""
    cache = load_json(KEYWORDS_FILE, {})
    keywords = {int(k): v for k, v in cache.get("keywords", {}).items()}
    missing = [t for t in tasks if not keywords.get(t["no"])]
    if not missing:
        return keywords
    for i in range(0, len(missing), KEYWORD_BATCH):
        chunk = missing[i:i + KEYWORD_BATCH]
        listing = "\n".join(
            f"{t['no']}. {t['title']} (전략: {t['strategy']} / 부처: {'·'.join(t['ministries'])})"
            for t in chunk
        )
        prompt = llm.load_prompt("task_keywords").replace("{tasks}", listing)
        got = parse_json_response(
            llm.complete(prompt, stage="task_map", max_tokens=6000))["keywords"]
        nos = {t["no"] for t in chunk}
        for no_str, kws in got.items():
            try:
                no = int(no_str)
            except ValueError:
                continue
            if no in nos:
                clean = [str(k).strip() for k in kws if len(str(k).strip()) >= 2]
                if clean:
                    keywords[no] = clean[:6]
    save_json(KEYWORDS_FILE, {"generated_at": _now(), "model": llm.active_model(),
                              "keywords": {str(k): v for k, v in sorted(keywords.items())}})
    return keywords


def match_turn(text: str, tasks: list[dict], keywords: dict[int, list[str]]):
    """직접 매칭 [(no, grade, evidence)]과 LLM 후보 [(no, hit_keyword)] 반환."""
    direct, candidates = [], []
    text_ns = _ns(text)
    explicit_nos = set()
    for m in NUM_PATTERN.finditer(text):
        no = int(m.group(1))
        if 1 <= no <= 123:
            explicit_nos.add(no)
    for t in tasks:
        no = t["no"]
        if len(direct) >= MAX_DIRECT_PER_TURN:
            break
        title_ns = _ns(t["title"])
        if no in explicit_nos or (len(title_ns) >= 8 and title_ns in text_ns):
            direct.append((no, "explicit", t["title"][:60]))
            continue
        # 자막 띄어쓰기가 제각각이므로 공백 무시 비교
        hits = [k for k in keywords.get(no, []) if _ns(k) in text_ns]
        # 서로 포함 관계인 변형 키워드("국민성장펀드"⊂"국민성장펀드 100조원")는 1개로 계산
        distinct = [h for h in hits if not any(h != o and h in o for o in hits)]
        if len(distinct) >= 2:
            direct.append((no, "topic", " · ".join(distinct[:3])[:60]))
        elif len(distinct) == 1:
            candidates.append((no, distinct[0]))
    return direct, candidates


def map_meeting(meeting: dict, tasks: list[dict], keywords: dict[int, list[str]]) -> list[dict]:
    """회의의 턴 전체를 판정해 ref 목록 [{task_no, tid, meeting_id, date, grade, grade_evidence}] 반환."""
    by_no = {t["no"]: t for t in tasks}
    refs, judge_pairs = [], []   # judge_pairs: (pair_no, task_no, turn, excerpt)

    for turn in meeting.get("turns") or []:
        text = full_turn_text(meeting, turn)
        direct, candidates = match_turn(text, tasks, keywords)
        for no, grade, evidence in direct:
            refs.append({"task_no": no, "tid": turn["tid"], "meeting_id": meeting["id"],
                         "date": meeting["date"], "grade": grade, "grade_evidence": evidence})
        for no, hit in candidates:
            if len(judge_pairs) < MAX_JUDGE_PAIRS:
                judge_pairs.append((len(judge_pairs) + 1, no, turn, _window(text, hit)))

    by_pair = {pno: (no, turn) for pno, no, turn, _ in judge_pairs}
    for i in range(0, len(judge_pairs), JUDGE_CHUNK):
        chunk = judge_pairs[i:i + JUDGE_CHUNK]
        listing = "\n\n".join(
            f"{pno}. [과제 {no}] {by_no[no]['title']} (주관: {'·'.join(by_no[no]['ministries'])})"
            f"\n   [발언] {excerpt}"
            for pno, no, turn, excerpt in chunk
        )
        prompt = llm.load_prompt("task_judge").replace("{pairs}", listing)
        try:
            links = parse_json_response(
                llm.complete(prompt, stage="task_map", max_tokens=3000))["links"]
        except Exception as e:
            print(f"[task_map] {meeting['id']} 판정 실패({i // JUDGE_CHUNK + 1}차): {e}", flush=True)
            continue
        for lk in links:
            pair = by_pair.get(lk.get("pair"))
            if pair is None:
                continue
            no, turn = pair
            refs.append({"task_no": no, "tid": turn["tid"], "meeting_id": meeting["id"],
                         "date": meeting["date"], "grade": "ai_inferred",
                         "grade_evidence": str(lk.get("evidence") or "")[:60]})
    return refs


def _load_map(tasks: list[dict]) -> dict[int, dict]:
    """기존 map.json → {task_no: entry}. 전 과제 entries 보장(§2.4)."""
    entries = {t["no"]: {"task_no": t["no"], "thread_ids": [], "turn_refs": []} for t in tasks}
    doc = load_json(MAP_FILE, None) or {}
    for e in doc.get("entries", []):
        if e.get("task_no") in entries:
            entries[e["task_no"]]["turn_refs"] = e.get("turn_refs") or []
    return entries


def _merge_refs(entries: dict[int, dict], refs: list[dict]) -> int:
    added = 0
    for r in refs:
        entry = entries.get(r["task_no"])
        if entry is None:
            continue
        if any(x["tid"] == r["tid"] for x in entry["turn_refs"]):
            continue
        entry["turn_refs"].append({k: r[k] for k in
                                   ("tid", "meeting_id", "date", "grade", "grade_evidence")})
        added += 1
    return added


def relink_threads(entries: dict[int, dict], keywords: dict[int, list[str]]) -> None:
    """스레드↔과제 연결 전체 재계산 (결정적 — §2.4)."""
    threads = [th for p in THREADS_DIR.glob("*.json") if (th := load_json(p, None))]
    for entry in entries.values():
        ref_tids = {r["tid"] for r in entry["turn_refs"]}
        kws_ns = {_ns(k) for k in keywords.get(entry["task_no"], [])}
        linked = []
        for th in threads:
            node_tids = {n["tid"] for n in th["nodes"]}
            tag_hits = sum(1 for t in th.get("topic_tags", []) if _ns(t) in kws_ns)
            if (node_tids & ref_tids) or tag_hits >= 2:
                linked.append(th["id"])
        entry["thread_ids"] = sorted(linked)


def _validate(entries: dict[int, dict]) -> list[str]:
    """P6 검증: 전 123과제 entries·grade enum·task_no 범위."""
    errors = []
    if sorted(entries) != list(range(1, 124)):
        errors.append(f"entries 수 이상 ({len(entries)})")
    for no, e in entries.items():
        for r in e["turn_refs"]:
            if r["grade"] not in ("explicit", "topic", "ai_inferred"):
                errors.append(f"과제 {no}: grade 값 이상 ({r['grade']})")
    return errors


def _save_map(entries: dict[int, dict]) -> None:
    for e in entries.values():
        e["turn_refs"].sort(key=lambda r: (r["date"], r["tid"]))
    save_json(MAP_FILE, {
        "generated_at": _now(),
        "entries": [entries[no] for no in sorted(entries)],
    })


def run(state: dict) -> None:
    tasks = load_tasks()
    if not tasks:
        print("[task_map] tasks.json 없음 — 건너뜀", flush=True)
        return
    if not llm.available():
        return
    keywords = ensure_keywords(tasks)
    entries = _load_map(tasks)

    recs = [
        r for r in state["videos"].values()
        if r["status"] == "processed" and r.get("meeting_id")
        and r["stages"].get("turns") == "done" and r["stages"].get("task_map") != "done"
    ]
    for rec in sorted(recs, key=lambda r: r.get("published_at") or ""):
        mid = rec["meeting_id"]
        meeting = load_meeting(mid)
        if meeting is None or not meeting.get("turns"):
            continue
        try:
            refs = map_meeting(meeting, tasks, keywords)
            added = _merge_refs(entries, refs)
            rec["stages"]["task_map"] = "done"
            save_state(state)
            print(f"[task_map] {mid} 매핑 {added}건", flush=True)
        except Exception as e:
            print(f"[task_map] {mid} 실패: {e}", flush=True)

    relink_threads(entries, keywords)
    errors = _validate(entries)
    if errors:
        print(f"[task_map] 검증 실패: {'; '.join(errors[:5])} — 저장 중단", flush=True)
        return
    _save_map(entries)
    mapped = sum(1 for e in entries.values() if e["turn_refs"] or e["thread_ids"])
    print(f"[task_map] 과제 {len(entries)}개 중 언급 보유 {mapped}개 "
          f"(언급 0회 {len(entries) - mapped}개)", flush=True)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    state = load_state()
    if "--all" in sys.argv:   # 백필: 전 회의 재판정 (map은 기존 refs에 병합)
        for rec in state["videos"].values():
            rec["stages"].pop("task_map", None)
    run(state)
    save_state(state)


if __name__ == "__main__":
    main()
