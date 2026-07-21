"""02 segment: vtt → Statement[] → 최소 Meeting JSON (SPEC-PIPELINE.md §4 #02, §2.2).

- 유튜브 자동자막 vtt의 롤링 중복 큐를 제거해 (시각, 조각) 스트림으로 만든 뒤
  종결어미+구두점 기준으로 문장 분할한다. 문장 타임스탬프 = 문장이 시작한 cue의 시각.
- Phase 1 산출은 문장 층만 채운 Meeting이다(turns/agenda 빈 배열, summary null).
  Turn·Agenda 참조(turn_id/agenda_id)는 후속 Phase가 채우기 전까지 null로 둔다.
"""
import html
import json
import re
from datetime import datetime

from .config import MEETINGS_DIR, kind_code

TIMESTAMP = re.compile(
    r"(?P<h>\d+):(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d{3})\s*-->\s*"
    r"(\d+):(\d{2}):(\d{2})\.(\d{3})"
)
INLINE_TAG = re.compile(r"<[^>]+>")          # <c>, <00:00:01.319> 등 인라인 태그
NOISE_ONLY = re.compile(r"^\[[^\]]+\]$")     # [음악] [박수] 단독 라인

# 종결어미(합쇼체 중심) 또는 구두점으로 끝나면 문장 경계
SENTENCE_END = re.compile(
    r"(?:[.?!…]|(?:습니다|습니까|십시오|십니다|십니까|됩니다|됩니까|입니다|입니까|"
    r"합니다|합니까|답니다|랍니다|바랍니다|드립니다|아닙니다)[.?!…]?)$"
)
MIN_SENTENCE_CHARS = 4    # 이보다 짧으면 앞 문장에 병합
MAX_SENTENCE_CHARS = 400  # 종결어미가 안 나와도 이 길이를 넘기면 강제 분할


def _ts_to_sec(m: re.Match) -> float:
    return int(m["h"]) * 3600 + int(m["m"]) * 60 + int(m["s"]) + int(m["ms"]) / 1000


def parse_vtt(path) -> list[tuple[float, str]]:
    """vtt → [(start_sec, fragment)]. 롤링 자막의 이월(반복) 라인을 제거한다."""
    fragments = []
    prev_lines: list[str] = []
    cur_start = None
    cur_lines: list[str] = []

    def flush():
        nonlocal prev_lines, cur_lines
        if cur_start is None:
            return
        fresh = [l for l in cur_lines if l and l not in prev_lines and not NOISE_ONLY.match(l)]
        if fresh:
            fragments.append((cur_start, " ".join(fresh)))
        if cur_lines:
            prev_lines = cur_lines
        cur_lines = []

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = TIMESTAMP.search(line)
            if m:
                flush()
                cur_start = _ts_to_sec(m)
                continue
            if cur_start is None:
                continue  # 헤더(WEBVTT, Kind, Language)
            text = html.unescape(INLINE_TAG.sub("", line)).replace("\xa0", " ").strip()
            if text:
                cur_lines.append(text)
    flush()
    return fragments


def split_sentences(fragments: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """조각 스트림 → [(start_sec, sentence)]. 단어 단위로 훑으며 종결어미에서 자른다."""
    words: list[tuple[float, str]] = []
    for start, frag in fragments:
        for w in frag.split():
            words.append((start, w))

    sentences: list[tuple[float, str]] = []
    buf: list[str] = []
    buf_start = None
    for start, w in words:
        if buf_start is None:
            buf_start = start
        buf.append(w)
        text = " ".join(buf)
        if SENTENCE_END.search(w) or len(text) >= MAX_SENTENCE_CHARS:
            sentences.append((buf_start, text))
            buf, buf_start = [], None
    if buf:
        sentences.append((buf_start, " ".join(buf)))

    # 너무 짧은 문장은 앞 문장에 병합
    merged: list[tuple[float, str]] = []
    for start, text in sentences:
        if merged and len(text) < MIN_SENTENCE_CHARS:
            pstart, ptext = merged[-1]
            merged[-1] = (pstart, f"{ptext} {text}")
        else:
            merged.append((start, text))
    return merged


def make_meeting_id(rec: dict) -> str:
    d = datetime.fromisoformat(rec["published_at"])
    return f"{d.year}-{kind_code(rec['kind'])}-{d.strftime('%m%d')}-{rec['youtube_id'][:6]}"


def build_meeting(rec: dict, vtt_path) -> dict:
    meeting_id = make_meeting_id(rec)
    sentences = split_sentences(parse_vtt(vtt_path))
    statements = []
    for i, (start, text) in enumerate(sentences, start=1):
        statements.append({
            "sid": f"{meeting_id}#{i}",
            "start_sec": round(start, 3),
            "text": text,           # 교정 전이므로 원문과 동일 (Phase 2에서 갱신)
            "text_raw": text,       # 자동자막 원문 — 영구 보존
            "corrected": False,
            "turn_id": None,
            "agenda_id": None,
            "text_verified": False,
            "history": [],
            "thread_refs": [],
        })
    return {
        "id": meeting_id,
        "kind": rec["kind"],
        "title": rec["title"],
        "date": datetime.fromisoformat(rec["published_at"]).date().isoformat(),
        "youtube_id": rec["youtube_id"],
        "duration_sec": rec.get("duration_sec") or 0,
        "source": {"video": f"https://www.youtube.com/watch?v={rec['youtube_id']}"},
        "summary": None,
        "agenda": [],
        "turns": [],
        "statements": statements,
        "stats": {"statement_count": len(statements), "turn_count": 0},
        "pipeline_status": "done",
    }


def write_meeting(meeting: dict) -> None:
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = MEETINGS_DIR / f"{meeting['id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meeting, f, ensure_ascii=False, indent=2)
        f.write("\n")
