"""백필: 과거 국무회의·업무보고 본회의 영상을 discovered로 등록 (Phase 1 완료 기준).

RSS는 최신 15개만 주므로 과거분은 채널 검색 + 공식 재생목록(yt-dlp flat)으로 수집한다.
채널 검색에는 과거 정부 영상·홍보 쇼츠·대변인 브리핑이 섞여 나오므로
(1) 제목의 방송일 표기 파싱 (2) 기준일 이후 (3) 재생시간 하한으로 본회의 풀영상만 거른다.
등록만 하고 자막 폴링·가공은 run_all이 수행한다.

사용: python -m pipeline.backfill [--max 150] [--since 2025-06-01] [--min-duration 1200]
"""
import argparse
import re
import sys
from datetime import datetime

import yt_dlp

from .config import CHANNEL_ID, KST, TITLE_PATTERN, classify_kind
from .state import load_state, register_video, save_state

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 콘솔(cp949) 대응

QUERIES = ["국무회의", "업무보고"]
# KTV 공식 "2026년 정부 업무보고" 재생목록
PLAYLISTS = ["PLQ1C5YbGRe_KBw6yVm6NQYs-csc9vSwkw"]

# 본회의 풀영상 제목의 방송일 표기: "(26.7.16.)" 또는 "(2026년 7월 16일 ...)"
DATE_SHORT = re.compile(r"\((\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})")
DATE_LONG = re.compile(r"\((\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")


def parse_title_date(title: str) -> datetime | None:
    if m := DATE_SHORT.search(title):
        return datetime(2000 + int(m[1]), int(m[2]), int(m[3]), tzinfo=KST)
    if m := DATE_LONG.search(title):
        return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=KST)
    return None


def flat_entries(url: str, limit: int) -> list[dict]:
    opts = {
        "extract_flat": True,
        "playlist_items": f"1:{limit}",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return list(info.get("entries") or [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=150, help="소스당 최대 후보 수")
    ap.add_argument("--since", type=str, default="2025-06-01", help="이 날짜(KST) 이후만")
    ap.add_argument("--min-duration", type=int, default=1200,
                    help="본회의 판별용 최소 재생시간(초) — 쇼츠·브리핑·발언 클립 제외")
    args = ap.parse_args()
    since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=KST)

    sources = [f"https://www.youtube.com/channel/{CHANNEL_ID}/search?query={q}" for q in QUERIES]
    sources += [f"https://www.youtube.com/playlist?list={p}" for p in PLAYLISTS]

    state = load_state()
    registered = 0
    for url in sources:
        for e in flat_entries(url, args.max):
            vid, title = e.get("id"), e.get("title") or ""
            if not vid or len(vid) != 11:  # 검색 결과에 섞이는 재생목록 항목 제외
                continue
            if not TITLE_PATTERN.search(title):
                continue
            if (e.get("duration") or 0) < args.min_duration:
                continue
            d = parse_title_date(title)
            if d is None or d < since:
                continue
            if register_video(state, vid, title, classify_kind(title),
                              published_at=d.isoformat(timespec="seconds"), source="backfill"):
                registered += 1
                print(f"[backfill] 등록: {vid} {d.date()} {title[:60]}")
    save_state(state)
    print(f"[backfill] 신규 등록 {registered}건 — 자막 수집은 run_all 실행 시 진행")


if __name__ == "__main__":
    main()
