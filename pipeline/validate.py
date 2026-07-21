"""산출 검증 (SPEC-PIPELINE.md §7).

검증 실패 시 meeting을 partial로 강등하되 처리는 계속한다(무너지지 않는 실패).
"""
VALID_GRADES = {"explicit", "topic", "ai_inferred"}


def _seq(sid: str) -> int:
    return int(sid.split("#")[1])


def _check_partition(blocks: list[dict], total: int, label: str) -> list[str]:
    """sid_range들이 겹치지 않고 1..total 전체를 커버하는지 (§7 항목 2)."""
    errors = []
    expected = 1
    for b in sorted(blocks, key=lambda b: _seq(b["sid_range"][0])):
        a, z = _seq(b["sid_range"][0]), _seq(b["sid_range"][1])
        if a != expected:
            errors.append(f"{label} 커버리지 공백/중복 (문장 {expected}≠{a})")
            break
        expected = z + 1
    if not errors and expected != total + 1:
        errors.append(f"{label} 끝 커버리지 부족 ({expected - 1}/{total})")
    return errors


def validate_meeting(meeting: dict) -> list[str]:
    errors = []
    sids = [s["sid"] for s in meeting["statements"]]
    if len(sids) != len(set(sids)):
        errors.append("sid 중복")
    if not sids:
        errors.append("문장 0건")
    for s in meeting["statements"]:
        if not s["text_raw"]:
            errors.append(f"{s['sid']}: text_raw 비어 있음")
        for ref in s["thread_refs"]:
            if ref.get("grade") not in VALID_GRADES:
                errors.append(f"{s['sid']}: grade 값 이상 ({ref.get('grade')})")
    if meeting["stats"]["statement_count"] != len(sids):
        errors.append("stats.statement_count 불일치")

    # 3층 구조 검증 — 층이 생성된 회의만 (§7 항목 1·2)
    total = len(sids)
    turns, agenda = meeting.get("turns") or [], meeting.get("agenda") or []
    if turns:
        errors += _check_partition(turns, total, "Turn")
        tids = {t["tid"] for t in turns}
        if any(s.get("turn_id") not in tids for s in meeting["statements"]):
            errors.append("turn_id 미참조 문장 존재")
        if meeting["stats"].get("turn_count") != len(turns):
            errors.append("stats.turn_count 불일치")
    if agenda:
        errors += _check_partition(agenda, total, "Agenda")
        aids = {a["aid"] for a in agenda}
        if any(s.get("agenda_id") not in aids for s in meeting["statements"]):
            errors.append("agenda_id 미참조 문장 존재")
        if turns and any(t.get("agenda_id") not in aids for t in turns):
            errors.append("Turn.agenda_id 미참조")
    return errors
