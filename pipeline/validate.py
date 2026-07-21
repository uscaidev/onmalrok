"""산출 검증 (SPEC-PIPELINE.md §7 — Phase 1 범위: 항목 1·3·4).

Turn/Agenda 커버리지 검증(항목 2)은 Phase 3에서 층이 생기면 활성화한다.
검증 실패 시 meeting을 partial로 강등하되 처리는 계속한다(무너지지 않는 실패).
"""
VALID_GRADES = {"explicit", "topic", "ai_inferred"}


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
    return errors
