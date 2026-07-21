"""05 agenda: 의제 구간 분할 (SPEC-PIPELINE.md §4 #05, §2.2).

korea.kr 공식 안건 앵커(official=true)는 후속 과제로 두고, 현재는 화제 전환점
LLM 분할(official=false)만 사용한다 — §4의 "매핑 안 되는 구간" 경로를 전면 적용.
판단 근거: 빠른 3층 구조 완성이 우선이고 official 앵커는 추가만 하면 되는 구조.
"""
from . import llm
from .util import numbered_sentences, parse_json_response, sanitize_starts, seq_of


def build_agenda(meeting: dict) -> None:
    stmts = meeting["statements"]
    total = len(stmts)
    mid = meeting["id"]
    by_seq = {seq_of(s["sid"]): s for s in stmts}

    prompt = llm.load_prompt("agenda").replace("{sentences}", numbered_sentences(stmts))
    raw = llm.complete(prompt, stage="agenda", max_tokens=6000)
    items = parse_json_response(raw)["agenda"]

    by_start = {}
    for a in items:
        if isinstance(a.get("start"), int):
            by_start[a["start"]] = a
    starts = sanitize_starts(list(by_start.keys()), total)

    agenda = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else total
        title = str(by_start.get(start, {}).get("title") or f"구간 {i + 1}").strip()[:40]
        agenda.append({
            "aid": f"{mid}@a{i + 1}",
            "title": title,
            "start_sec": by_seq[start]["start_sec"],
            "sid_range": [f"{mid}#{start}", f"{mid}#{end}"],
            "official": False,
        })

    # 문장 → 의제 역참조
    idx = 0
    for s in stmts:
        seq = seq_of(s["sid"])
        while idx + 1 < len(agenda) and seq >= seq_of(agenda[idx + 1]["sid_range"][0]):
            idx += 1
        s["agenda_id"] = agenda[idx]["aid"]

    # 턴 → 의제 (턴 대표 문장이 속한 구간)
    for t in meeting.get("turns", []):
        rep_seq = seq_of(t["rep_sid"])
        t["agenda_id"] = next(
            (a["aid"] for a in agenda
             if seq_of(a["sid_range"][0]) <= rep_seq <= seq_of(a["sid_range"][1])),
            agenda[0]["aid"],
        )

    meeting["agenda"] = agenda
