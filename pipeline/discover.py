"""01 감지: KTV 채널 RSS에서 국무회의·국민업무보고 영상 등록 (SPEC-PIPELINE.md §3.1).

korea.kr 보조 크롤·시민 제보 유입은 후속 Phase에서 이 모듈에 추가한다.
"""
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from .config import KST, RSS_URL, TITLE_PATTERN, classify_kind
from .state import register_video

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def fetch_rss_entries() -> list[dict]:
    """RSS 최신 15개 → [{youtube_id, title, published_at(KST ISO)}]."""
    res = requests.get(RSS_URL, timeout=30)
    res.raise_for_status()
    root = ET.fromstring(res.content)
    entries = []
    for entry in root.findall("atom:entry", NS):
        vid = entry.findtext("yt:videoId", namespaces=NS)
        title = entry.findtext("atom:title", namespaces=NS) or ""
        published = entry.findtext("atom:published", namespaces=NS)
        published_kst = None
        if published:
            published_kst = (
                datetime.fromisoformat(published).astimezone(KST).isoformat(timespec="seconds")
            )
        if vid:
            entries.append({"youtube_id": vid, "title": title, "published_at": published_kst})
    return entries


def run(state: dict) -> list[str]:
    """RSS 감지 실행. 새로 등록된 youtube_id 목록 반환."""
    new_ids = []
    for e in fetch_rss_entries():
        if not TITLE_PATTERN.search(e["title"]):
            continue
        if register_video(state, e["youtube_id"], e["title"],
                          classify_kind(e["title"]), e["published_at"], source="rss"):
            new_ids.append(e["youtube_id"])
            print(f"[discover] 신규 등록: {e['youtube_id']} {e['title']}")
    return new_ids
