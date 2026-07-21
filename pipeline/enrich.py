"""04~06 오케스트레이터: 교정 완료 회의에 Turn·Agenda·Summary를 채운다.

- 회의 단위 병렬(각 회의 내부는 04→05→06 순차 — 단계 간 의존)
- 단계별 stages 기록으로 실패 시 해당 단계부터 재시도 (§8)
- 실패 단계가 있으면 pipeline_status=partial, 전 단계 완료 시 done (§7)
"""
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .agenda import build_agenda
from .state import load_state, now_kst, save_state
from .summarize import build_summary
from .turns import build_turns
from .util import load_meeting, save_meeting
from .validate import validate_meeting

STAGES = [("turns", build_turns), ("agenda", build_agenda), ("summarize", build_summary)]


def pending_records(state: dict) -> list[dict]:
    return [
        rec for rec in state["videos"].values()
        if rec["status"] == "processed" and rec.get("meeting_id")
        and rec["stages"].get("correct") == "done"
        and not all(rec["stages"].get(name) == "done" for name, _ in STAGES)
    ]


def enrich_meeting(rec: dict) -> tuple[str, bool]:
    """한 회의의 04→05→06. (meeting_id, 전체 성공 여부) 반환."""
    mid = rec["meeting_id"]
    meeting = load_meeting(mid)
    if meeting is None:
        return mid, False
    ok = True
    for name, fn in STAGES:
        if rec["stages"].get(name) == "done":
            continue
        try:
            fn(meeting)
            rec["stages"][name] = "done"
        except Exception as e:
            ok = False
            print(f"[enrich] {mid} {name} 실패: {e}", flush=True)
            break  # 이후 단계는 이 단계에 의존 — 다음 실행에서 여기부터 재시도

    errors = validate_meeting(meeting)
    if errors:
        ok = False
        print(f"[enrich] {mid} 검증 실패: {'; '.join(errors)}", flush=True)
    meeting["pipeline_status"] = "done" if ok else "partial"
    if ok:
        rec["enriched_at"] = now_kst()
    save_meeting(meeting)
    return mid, ok


def run(state: dict, limit: int = 0, workers: int = 1) -> None:
    if not llm.available():
        n = len(pending_records(state))
        if n:
            print(f"[enrich] API 키 없음 — 04~06 건너뜀 (대기 {n}건)")
        return
    targets = sorted(pending_records(state), key=lambda r: r["meeting_id"])
    if limit:
        targets = targets[:limit]
    if not targets:
        return
    done = 0
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        for i, (mid, ok) in enumerate(pool.map(enrich_meeting, targets), 1):
            done += ok
            save_state(state)
            print(f"[enrich] ({i}/{len(targets)}) {mid} {'완료' if ok else 'partial'}", flush=True)
    print(f"[enrich] {done}/{len(targets)} 회의 3층 구조 완성", flush=True)


def main() -> None:
    import argparse
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--meeting", type=str, default=None)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()
    state = load_state()
    if args.meeting:
        rec = next((r for r in state["videos"].values() if r.get("meeting_id") == args.meeting), None)
        if rec is None:
            print("해당 회의 없음")
            return
        try:
            enrich_meeting(rec)
        finally:
            save_state(state)
        return
    run(state, limit=args.limit, workers=args.workers)
    save_state(state)


if __name__ == "__main__":
    main()
