"""04 turns: 화자 턴 분할 + 화자 추정 + 대표 문장 (SPEC-PIPELINE.md §4 #04, §2.2).

- LLM이 턴 시작점·화자·대표 문장을 판정 (회의당 1회 통독)
- 화자는 inferred=true 고정, 확신 낮으면 null (§4)
- 전 문장이 정확히 하나의 Turn에 속하도록 후처리로 보정 (§7)
"""
from . import llm
from .util import load_json, numbered_sentences, parse_json_response, sanitize_starts, seq_of


def build_turns(meeting: dict) -> None:
    stmts = meeting["statements"]
    total = len(stmts)
    mid = meeting["id"]

    prompt = llm.load_prompt("turns").replace("{sentences}", numbered_sentences(stmts))
    raw = llm.complete(prompt, stage="turns", max_tokens=16000)
    items = parse_json_response(raw)["turns"]

    by_start = {}
    for t in items:
        if isinstance(t.get("start"), int):
            by_start[t["start"]] = t
    starts = sanitize_starts(list(by_start.keys()), total)

    # 동일 화자 연속 턴 병합 (과분할 방어)
    merged = []
    for start in starts:
        speaker = by_start.get(start, {}).get("speaker")
        if merged and speaker is not None and merged[-1][1] == speaker:
            continue
        merged.append((start, speaker))
    starts = [s for s, _ in merged]

    turns = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else total
        info = by_start.get(start, {})
        speaker = info.get("speaker")
        rep = info.get("rep")
        if not isinstance(rep, int) or not (start <= rep <= end):
            rep = start
        turns.append({
            "tid": f"{mid}@t{i + 1}",
            "speaker": ({"name": speaker, "inferred": True, "verified": False}
                        if isinstance(speaker, str) and speaker.strip() else None),
            "sid_range": [f"{mid}#{start}", f"{mid}#{end}"],
            "agenda_id": None,   # 05 agenda에서 채움
            "rep_sid": f"{mid}#{rep}",
        })

    # 문장 → 턴 역참조
    idx = 0
    for s in stmts:
        seq = seq_of(s["sid"])
        while idx + 1 < len(turns) and seq >= seq_of(turns[idx + 1]["sid_range"][0]):
            idx += 1
        s["turn_id"] = turns[idx]["tid"]

    meeting["turns"] = turns
    meeting["stats"]["turn_count"] = len(turns)
