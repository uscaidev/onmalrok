"""파이프라인 오케스트레이터 (SPEC-PIPELINE.md §3·§8).

감지 → 자막 폴링 → 가공(segment) → 검증 → 상태 저장.
회의별 try/except 격리: 한 회의의 실패가 전체 실행을 멈추지 않는다.
"""
import sys
import traceback

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 콘솔(cp949) 대응

from . import correct, discover, poll_captions, segment
from .state import load_state, save_state
from .validate import validate_meeting


def process_video(rec: dict) -> None:
    """captioned → segment → processed. 실패 시 상태 유지(다음 실행에서 재시도)."""
    vtt = poll_captions.subtitle_path(rec["youtube_id"])
    if not vtt.exists():
        raise FileNotFoundError(f"자막 파일 없음: {vtt}")
    meeting = segment.build_meeting(rec, vtt)
    errors = validate_meeting(meeting)
    if errors:
        meeting["pipeline_status"] = "partial"
        print(f"[validate] {meeting['id']} partial 강등: {'; '.join(errors)}")
    segment.write_meeting(meeting)
    rec["meeting_id"] = meeting["id"]
    rec["stages"]["segment"] = "done"
    rec["status"] = "processed"
    rec["error"] = None
    print(f"[segment] {meeting['id']} 문장 {meeting['stats']['statement_count']}건 산출"
          f" (status={meeting['pipeline_status']})")


def main() -> int:
    reprocess = "--reprocess" in sys.argv  # 자막 보유분 전체 재분할 (멱등 — §5.1)
    state = load_state()

    try:
        discover.run(state)
    except Exception:
        # 감지 실패가 기존 영상 처리까지 막지 않도록 격리 (§8)
        print("[discover] 실패 — 이번 실행은 폴링/가공만 진행")
        traceback.print_exc()
    save_state(state)

    poll_captions.run(state)
    save_state(state)

    failed = 0
    for rec in state["videos"].values():
        if rec["status"] == "captioned" or (reprocess and rec["status"] == "processed"):
            try:
                process_video(rec)
            except Exception as e:
                failed += 1
                rec["error"] = f"segment: {e}"
                traceback.print_exc()
    save_state(state)

    # 03 교정: 배치 수거 → 신규 제출 (API 키 없으면 내부에서 건너뜀)
    try:
        correct.run(state)
    except Exception:
        print("[correct] 실패 — 다음 실행에서 재시도")
        traceback.print_exc()
    save_state(state)

    counts: dict[str, int] = {}
    for rec in state["videos"].values():
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    print(f"[run_all] 상태 요약: {counts} (이번 실행 가공 실패 {failed}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
