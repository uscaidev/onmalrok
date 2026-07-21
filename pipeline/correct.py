"""03 correct: 자동자막 오인식 교정 + 용어집 축적 (SPEC-PIPELINE.md §4 #02, §5).

동작 (매 실행, run_all에서 호출):
  1. 이전 실행에서 제출한 배치 수거 → 교정 적용 + 용어집 후보 축적
  2. 미교정 회의(50문장 단위 청크)를 Message Batches API로 제출 → batch id 저장

- 오인식 교정만. 의미 변경·요약·생략 금지 (프롬프트 + 적용 시 가드레일로 이중 방어)
- text_raw는 절대 건드리지 않는다. diff 없으면 corrected=false 유지
- 멱등: stages.correct == "done"인 회의는 건너뜀. 재보강(§5.3)은 별도 workflow가 담당
- 실패 청크는 3회까지 재제출, 이후 해당 회의만 partial (§6·§8)
"""
import difflib
import json
import re

from . import llm
from .config import DATA_DIR, MEETINGS_DIR
from .state import now_kst
from .validate import validate_meeting

CHUNK_SIZE = 50          # 배치 50문장/호출 (§4)
MAX_RETRIES = 3          # §6
MAX_LEN_RATIO = 1.6      # 교정문이 원문 대비 이 비율을 벗어나면 의미 변경 의심 → 기각
GLOSSARY_FILE = DATA_DIR / "glossary.json"
CANDIDATES_FILE = DATA_DIR / "state" / "glossary_candidates.json"
BATCHES_FILE = DATA_DIR / "state" / "batches.json"
GLOSSARY_PROMPT_LIMIT = 200   # 프롬프트에 주입할 최대 용어 수 (토큰 상한)

OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "i": {"type": "integer"},
                        "text": {"type": "string"},
                    },
                    "required": ["i", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["corrections"],
        "additionalProperties": False,
    },
}


def _load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def _save_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load_meeting(meeting_id: str) -> dict | None:
    path = MEETINGS_DIR / f"{meeting_id}.json"
    return _load_json(path, None)


def _save_meeting(meeting: dict) -> None:
    _save_json(MEETINGS_DIR / f"{meeting['id']}.json", meeting)


# ---------------------------------------------------------------- 프롬프트

def build_prompt(statements: list[dict]) -> str:
    glossary = _load_json(GLOSSARY_FILE, {})
    top = sorted(glossary.items())[:GLOSSARY_PROMPT_LIMIT]
    glossary_text = "\n".join(f'- "{k}" → "{v}"' for k, v in top) or "(아직 없음)"
    sentences = "\n".join(
        f"{int(s['sid'].split('#')[1])}. {s['text_raw']}" for s in statements
    )
    return llm.load_prompt("correct").replace("{glossary}", glossary_text).replace(
        "{sentences}", sentences
    )


# ---------------------------------------------------------------- 교정 적용

def apply_corrections(meeting: dict, corrections: list[dict]) -> int:
    """교정을 검증 후 반영. 반영된 문장 수 반환."""
    by_seq = {int(s["sid"].split("#")[1]): s for s in meeting["statements"]}
    applied = 0
    for corr in corrections:
        stmt = by_seq.get(corr.get("i"))
        text = (corr.get("text") or "").strip()
        if stmt is None or not text or text == stmt["text_raw"]:
            continue
        ratio = len(text) / max(len(stmt["text_raw"]), 1)
        if not (1 / MAX_LEN_RATIO <= ratio <= MAX_LEN_RATIO):
            continue  # 길이 급변 = 요약/부연 의심 → 기각 (원문 유지)
        collect_glossary_candidates(stmt["text_raw"], text)
        stmt["text"] = text
        stmt["corrected"] = True
        applied += 1
    return applied


# ---------------------------------------------------------------- 용어집 (§5.2)

def collect_glossary_candidates(raw: str, corrected: str) -> None:
    """단어 단위 diff에서 치환쌍을 추출해 후보에 누적. 빈도 2회 이상이면 용어집 승격."""
    pairs = extract_pairs(raw, corrected)
    if not pairs:
        return
    candidates = _load_json(CANDIDATES_FILE, {})
    glossary = _load_json(GLOSSARY_FILE, {})
    changed = False
    for wrong, right in pairs:
        key = f"{wrong}→{right}"
        candidates[key] = candidates.get(key, 0) + 1
        if candidates[key] >= 2 and glossary.get(wrong) != right:
            glossary[wrong] = right
            changed = True
    _save_json(CANDIDATES_FILE, candidates)
    if changed:
        _save_json(GLOSSARY_FILE, dict(sorted(glossary.items())))


def extract_pairs(raw: str, corrected: str) -> list[tuple[str, str]]:
    """어절 단위 치환쌍. 한글 미포함·과도하게 긴 쌍은 제외."""
    a, b = raw.split(), corrected.split()
    pairs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if op != "replace":
            continue
        wrong, right = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if wrong == right or len(wrong) > 20 or len(right) > 20:
            continue
        if not (re.search(r"[가-힣]", wrong) and re.search(r"[가-힣]", right)):
            continue
        pairs.append((wrong, right))
    return pairs


# ---------------------------------------------------------------- 배치 수거

def collect_batches(state: dict) -> None:
    batches = _load_json(BATCHES_FILE, {"active": {}})
    if not batches["active"]:
        return
    client = llm.get_client()
    done_ids = []
    for batch_id, info in batches["active"].items():
        try:
            batch = client.messages.batches.retrieve(batch_id)
        except Exception as e:
            print(f"[correct] 배치 {batch_id} 조회 실패: {e}")
            continue
        if batch.processing_status != "ended":
            print(f"[correct] 배치 {batch_id} 처리 중 ({batch.processing_status}) — 다음 실행에서 수거")
            continue
        _apply_batch_results(client, batch_id, info, state, batches)
        done_ids.append(batch_id)
    for bid in done_ids:
        del batches["active"][bid]
    _save_json(BATCHES_FILE, batches)


def _apply_batch_results(client, batch_id: str, info: dict, state: dict, batches: dict) -> None:
    chunks = info["chunks"]  # custom_id -> {meeting_id, retries}
    in_tok = out_tok = calls = 0
    failed: list[str] = []
    meetings: dict[str, dict] = {}

    for result in client.messages.batches.results(batch_id):
        cid = result.custom_id
        meta = chunks.get(cid)
        if meta is None:
            continue
        if result.result.type != "succeeded":
            failed.append(cid)
            continue
        msg = result.result.message
        calls += 1
        in_tok += msg.usage.input_tokens
        out_tok += msg.usage.output_tokens
        mid = meta["meeting_id"]
        meeting = meetings.get(mid) or _load_meeting(mid)
        if meeting is None:
            continue
        meetings[mid] = meeting
        try:
            text = next(b.text for b in msg.content if b.type == "text")
            corrections = json.loads(text)["corrections"]
        except (StopIteration, json.JSONDecodeError, KeyError) as e:
            print(f"[correct] {cid} 응답 파싱 실패: {e}")
            failed.append(cid)
            continue
        applied = apply_corrections(meeting, corrections)
        meta["done"] = True
        print(f"[correct] {cid} 적용 {applied}건")

    llm.record_usage("correct", in_tok, out_tok, calls)

    # 실패 청크 재시도 카운트 (다음 제출 시 재포함)
    retry_pool = batches.setdefault("retry", {})
    for cid in failed:
        meta = chunks[cid]
        meta["retries"] = meta.get("retries", 0) + 1
        if meta["retries"] < MAX_RETRIES:
            retry_pool[cid] = meta
        else:
            print(f"[correct] {cid} {MAX_RETRIES}회 실패 — 해당 회의 partial 유지")

    # 회의별 완료 판정: 이 배치에서 그 회의의 모든 청크가 done이고 재시도 풀에 없으면 완료
    for mid, meeting in meetings.items():
        cids = [c for c, m in chunks.items() if m["meeting_id"] == mid]
        all_done = all(chunks[c].get("done") for c in cids)
        has_retry = any(c in retry_pool for c in cids)
        if all_done and not has_retry:
            rec = state["videos"].get(meeting["youtube_id"])
            if rec:
                rec["stages"]["correct"] = "done"
                rec["corrected_at"] = now_kst()
            meeting["pipeline_status"] = "done"
        else:
            meeting["pipeline_status"] = "partial"
        errors = validate_meeting(meeting)
        if errors:
            meeting["pipeline_status"] = "partial"
            print(f"[correct] {mid} 검증 실패 → partial: {'; '.join(errors)}")
        _save_meeting(meeting)


# ---------------------------------------------------------------- 배치 제출

def submit_pending(state: dict) -> None:
    batches = _load_json(BATCHES_FILE, {"active": {}})
    active_meetings = {
        m["meeting_id"] for info in batches["active"].values() for m in info["chunks"].values()
    }

    requests = []
    chunks: dict[str, dict] = {}

    # 재시도 풀 우선
    for cid, meta in batches.pop("retry", {}).items():
        meeting = _load_meeting(meta["meeting_id"])
        if meeting is None:
            continue
        stmts = _chunk_statements(meeting, cid)
        if stmts:
            requests.append(_build_request(cid, stmts))
            chunks[cid] = meta

    # 신규: processed && segment 완료 && correct 미완료 && 진행 중 배치에 없음
    for rec in state["videos"].values():
        mid = rec.get("meeting_id")
        if (rec["status"] != "processed" or not mid or mid in active_meetings
                or rec["stages"].get("correct") == "done"):
            continue
        meeting = _load_meeting(mid)
        if meeting is None:
            continue
        stmts = meeting["statements"]
        for start in range(0, len(stmts), CHUNK_SIZE):
            chunk = stmts[start:start + CHUNK_SIZE]
            cid = f"{mid}|{start + 1}"
            requests.append(_build_request(cid, chunk))
            chunks[cid] = {"meeting_id": mid, "retries": 0}

    if not requests:
        _save_json(BATCHES_FILE, batches)
        return

    client = llm.get_client()
    batch = client.messages.batches.create(requests=requests)
    batches["active"][batch.id] = {"stage": "correct", "created_at": now_kst(), "chunks": chunks}
    _save_json(BATCHES_FILE, batches)
    print(f"[correct] 배치 제출: {batch.id} (청크 {len(requests)}개) — 다음 실행에서 수거")


def _chunk_statements(meeting: dict, cid: str) -> list[dict]:
    start = int(cid.split("|")[1])
    return meeting["statements"][start - 1:start - 1 + CHUNK_SIZE]


def _build_request(custom_id: str, statements: list[dict]) -> dict:
    return {
        "custom_id": custom_id,
        "params": {
            "model": llm.MODEL,
            "max_tokens": 8000,
            "thinking": {"type": "disabled"},
            "output_config": {"effort": "low", "format": OUTPUT_SCHEMA},
            "messages": [{"role": "user", "content": build_prompt(statements)}],
        },
    }


# ---------------------------------------------------------------- 동기 경로 (OpenRouter)

def parse_corrections(text: str) -> list[dict]:
    """응답에서 {"corrections":[...]} 추출. 코드펜스·잡문 허용."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("JSON 객체 없음")
    return json.loads(text[start:end + 1])["corrections"]


def _pending_meetings(state: dict) -> list[dict]:
    return [
        rec for rec in state["videos"].values()
        if rec["status"] == "processed" and rec.get("meeting_id")
        and rec["stages"].get("correct") != "done"
    ]


def run_sync(state: dict, limit: int, only_meeting: str | None = None) -> None:
    """OpenRouter 동기 교정. 실행당 최대 limit개 회의 (0 = 무제한)."""
    targets = _pending_meetings(state)
    if only_meeting:
        targets = [r for r in targets if r["meeting_id"] == only_meeting]
    targets.sort(key=lambda r: r["meeting_id"])
    if limit:
        targets = targets[:limit]

    for rec in targets:
        mid = rec["meeting_id"]
        meeting = _load_meeting(mid)
        if meeting is None:
            continue
        stmts = meeting["statements"]
        total_applied, failed_chunks = 0, 0
        for start in range(0, len(stmts), CHUNK_SIZE):
            chunk = stmts[start:start + CHUNK_SIZE]
            try:
                raw = llm.complete(build_prompt(chunk), stage="correct")
                corrections = parse_corrections(raw)
            except Exception as e:
                failed_chunks += 1
                print(f"[correct] {mid}|{start + 1} 실패: {e}")
                continue
            total_applied += apply_corrections(meeting, corrections)

        if failed_chunks == 0:
            rec["stages"]["correct"] = "done"
            rec["corrected_at"] = now_kst()
            meeting["pipeline_status"] = "done"     # 이전 실패로 partial이었어도 복원
        else:
            meeting["pipeline_status"] = "partial"  # 다음 실행에서 회의 전체 재시도 (멱등)
        errors = validate_meeting(meeting)
        if errors:
            meeting["pipeline_status"] = "partial"
        _save_meeting(meeting)
        print(f"[correct] {mid} 교정 {total_applied}건 적용"
              f" (실패 청크 {failed_chunks}, status={meeting['pipeline_status']})")


# ---------------------------------------------------------------- 진입점

# 동기 경로에서 실행당 처리할 최대 회의 수 (cron 1회 실행 시간 상한 방어)
SYNC_MEETINGS_PER_RUN = 10


def run(state: dict) -> None:
    prov = llm.provider()
    if prov is None:
        pending = len(_pending_meetings(state))
        if pending:
            print(f"[correct] API 키 없음 — 교정 건너뜀 (대기 회의 {pending}건)")
        return
    if prov == "anthropic":
        collect_batches(state)
        submit_pending(state)
    else:
        run_sync(state, limit=SYNC_MEETINGS_PER_RUN)


def main() -> None:
    """수동 실행: python -m pipeline.correct [--limit N] [--meeting ID]"""
    import argparse
    import sys as _sys
    from .state import load_state, save_state
    if _sys.stdout.encoding and _sys.stdout.encoding.lower() != "utf-8":
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1, help="처리할 회의 수 (0=무제한)")
    ap.add_argument("--meeting", type=str, default=None, help="특정 meeting_id만")
    args = ap.parse_args()
    if llm.provider() is None:
        print("[correct] API 키 없음")
        return
    state = load_state()
    if llm.provider() == "anthropic":
        collect_batches(state)
        submit_pending(state)
    else:
        run_sync(state, limit=args.limit, only_meeting=args.meeting)
    save_state(state)


if __name__ == "__main__":
    main()
