"""자막 폴링: discovered/waiting_captions 영상의 한국어 자막 확인·다운로드 (SPEC-PIPELINE.md §3.2·3.3).

yt-dlp 한 번의 호출로 메타데이터 취득 + 자막(vtt) 저장을 같이 수행한다.
수동 업로드 자막(ko)이 있으면 그것을, 없으면 자동 자막을 받는다.
"""
from datetime import datetime, timedelta

import yt_dlp

from .config import CAPTION_EXPIRY_DAYS, KST, MIN_MEETING_DURATION_SEC, RAW_SUBS_DIR
from .state import now_kst

POLLABLE = ("discovered", "waiting_captions")


def subtitle_path(youtube_id: str):
    return RAW_SUBS_DIR / f"{youtube_id}.ko.vtt"


def _download_info_and_subs(youtube_id: str) -> dict | None:
    RAW_SUBS_DIR.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": True,        # 수동 자막 우선
        "writeautomaticsub": True,     # 자동 자막 폴백
        "subtitleslangs": ["ko"],
        "subtitlesformat": "vtt",
        "outtmpl": str(RAW_SUBS_DIR / "%(id)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}", download=True)


def poll_video(rec: dict) -> None:
    yid = rec["youtube_id"]
    rec["last_checked"] = now_kst()
    try:
        info = _download_info_and_subs(yid)
    except yt_dlp.utils.DownloadError as e:
        rec["error"] = f"yt-dlp: {e}"
        rec["retry_count"] += 1
        if rec["status"] == "discovered":
            rec["status"] = "waiting_captions"
        print(f"[poll] {yid} 조회 실패: {e}")
        return

    # 메타데이터 보정
    if info.get("duration"):
        rec["duration_sec"] = int(info["duration"])
    if not rec.get("published_at") and info.get("upload_date"):
        d = datetime.strptime(info["upload_date"], "%Y%m%d").replace(tzinfo=KST)
        rec["published_at"] = d.isoformat(timespec="seconds")
    if not rec.get("title") and info.get("title"):
        rec["title"] = info["title"]

    # 제목 정규식만으로는 홍보 쇼츠·발언 클립이 섞임 → 재생시간으로 본회의 여부 판별
    if rec["duration_sec"] and rec["duration_sec"] < MIN_MEETING_DURATION_SEC:
        rec["status"] = "excluded"
        rec["error"] = f"재생시간 {rec['duration_sec']}초 < {MIN_MEETING_DURATION_SEC}초 — 본회의 아님"
        print(f"[poll] {yid} 제외 (재생시간 {rec['duration_sec']}초)")
        return

    if subtitle_path(yid).exists():
        has_manual = bool((info.get("subtitles") or {}).get("ko"))
        rec["caption_source"] = "manual" if has_manual else "auto"
        rec["status"] = "captioned"
        rec["error"] = None
        print(f"[poll] {yid} 자막 확보 ({rec['caption_source']})")
    else:
        rec["status"] = "waiting_captions"
        rec["retry_count"] += 1
        print(f"[poll] {yid} 자막 미생성 (재시도 {rec['retry_count']}회)")


def expire_video(rec: dict) -> bool:
    """waiting_captions가 감지 후 7일을 넘기면 captions_missing (§3.3)."""
    if rec["status"] != "waiting_captions":
        return False
    discovered = datetime.fromisoformat(rec["discovered_at"])
    if datetime.now(KST) - discovered > timedelta(days=CAPTION_EXPIRY_DAYS):
        rec["status"] = "captions_missing"
        print(f"[poll] 경고: {rec['youtube_id']} 자막 {CAPTION_EXPIRY_DAYS}일 경과 → captions_missing")
        return True
    return False


def run(state: dict) -> None:
    for rec in state["videos"].values():
        if rec["status"] in POLLABLE:
            poll_video(rec)
            expire_video(rec)
