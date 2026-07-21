"""영상별 상태 머신 저장소 data/state/videos.json (SPEC-PIPELINE.md §3).

상태 전이:
  discovered → waiting_captions → captioned → processed
  waiting_captions --7일 경과--> captions_missing --(옵션) whisper--> captioned
"""
import json
import os
import tempfile
from datetime import datetime

from .config import KST, STATE_FILE

STATUSES = (
    "discovered",
    "waiting_captions",
    "captioned",
    "processed",
    "captions_missing",
    "excluded",   # 제목은 매치했으나 본회의가 아닌 클립 (재생시간 하한 미달)
)


def now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"videos": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_FILE.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, STATE_FILE)


def register_video(state: dict, youtube_id: str, title: str, kind: str,
                   published_at: str | None, source: str) -> bool:
    """미등록 영상을 discovered로 등록. 이미 있으면 False."""
    if youtube_id in state["videos"]:
        return False
    state["videos"][youtube_id] = {
        "youtube_id": youtube_id,
        "title": title,
        "kind": kind,
        "published_at": published_at,      # KST ISO, 폴링 시 upload_date로 보정
        "status": "discovered",
        "source": source,                  # rss | backfill | korea_kr | citizen
        "discovered_at": now_kst(),
        "last_checked": None,
        "retry_count": 0,
        "duration_sec": None,
        "caption_source": None,            # auto | manual | whisper
        "meeting_id": None,
        "stages": {},                      # 단계별 done 기록 (§8 재시도 기준)
        "error": None,
    }
    return True
