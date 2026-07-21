"""08 build_index: 검색 샤드·keywords·회의 목록·오픈데이터 덤프 (SPEC-PIPELINE.md §4 #08).

트랙 B의 임시 scripts/build-index.mjs와 동일한 산출 형식(§4.3)을 유지하며 대체한다.
public/search-index 사본과 meta.json도 동일하게 생성.
"""
import re
import sys
from collections import Counter
from datetime import datetime

from .config import DATA_DIR, KST, MEETINGS_DIR, ROOT

INDEX_DIR = DATA_DIR / "index"
THREADS_DIR = DATA_DIR / "threads"
PUBLIC_SEARCH_DIR = ROOT / "public" / "search-index"
SHARD_SIZE = 10   # 회의 10개 단위 (SPEC.md §4.3)

# 인기 키워드 추출용: 조사·어미가 붙지 않은 2~6자 한글 토큰의 문장 빈도
TOKEN = re.compile(r"[가-힣]{2,6}")
STOPWORDS = set("""
그리고 그래서 그런데 그러면 하지만 또한 지금 오늘 여러 이런 저런 그런 어떤 모든 매우 정말
있습니다 있는 있고 있어서 없는 합니다 하는 하고 해서 위해 통해 대해 관련 경우 부분 정도
말씀 생각 여러분 국민 정부 대통령 총리 장관 회의 국무회의 업무보고 보고 논의 검토 추진
드리겠습니다 하겠습니다 바랍니다 주시기 부탁 감사 안녕 이제 우리 저희 함께 가장 특히 계속
사실 문제 상황 내용 필요 중요 다음 이번 지난 올해 내년 현재 지역 사업 정책 예산 지원 강화
""".split())


def load_json(path):
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, obj, minify=False):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if minify:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")


def extract_keywords(docs: list[dict], top_n: int = 40) -> dict:
    """문장 단위 등장 빈도 상위 키워드 (짧은 명사형 토큰만)."""
    counter = Counter()
    for d in docs:
        seen = set()
        for tok in TOKEN.findall(d["text"]):
            if tok in STOPWORDS or tok in seen:
                continue
            if re.search(r"(하다|해요|니다|세요|지요|는데|어요|았다|었다|은데)$", tok):
                continue
            seen.add(tok)
            counter[tok] += 1
    return dict(counter.most_common(top_n))


def run() -> None:
    meetings = sorted(
        (load_json(p) for p in MEETINGS_DIR.glob("*.json")),
        key=lambda m: m["date"], reverse=True,
    )
    threads = [load_json(p) for p in sorted(THREADS_DIR.glob("*.json"))] if THREADS_DIR.exists() else []

    meetings_index = [{
        "id": m["id"], "kind": m["kind"], "title": m["title"], "date": m["date"],
        "youtube_id": m["youtube_id"], "duration_sec": m["duration_sec"],
        "statement_count": m["stats"]["statement_count"],
        "pipeline_status": m["pipeline_status"],
    } for m in meetings]

    docs = []
    for m in meetings:
        speaker_by_turn = {t["tid"]: ((t.get("speaker") or {}).get("name") or "")
                           for t in m.get("turns", [])}
        for s in m["statements"]:
            docs.append({
                "sid": s["sid"], "text": s["text"],
                "speaker_name": speaker_by_turn.get(s.get("turn_id"), ""),
                "meeting_id": m["id"], "meeting_title": m["title"],
                "date": m["date"], "start_sec": s["start_sec"],
            })

    dump_json(INDEX_DIR / "meetings.json", meetings_index)
    shard_count = max(1, -(-len(meetings) // SHARD_SIZE))
    per_shard = -(-len(docs) // shard_count)
    shards = [docs[n * per_shard:(n + 1) * per_shard] for n in range(shard_count)]
    for n, shard in enumerate(shards):
        dump_json(INDEX_DIR / f"search-{n}.json", shard, minify=True)
        dump_json(PUBLIC_SEARCH_DIR / f"search-{n}.json", shard, minify=True)
    dump_json(PUBLIC_SEARCH_DIR / "meta.json", {"shards": shard_count, "docs": len(docs)})
    dump_json(INDEX_DIR / "keywords.json", extract_keywords(docs))

    dump_json(DATA_DIR / "dump" / "latest.json", {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "license": "CC BY 4.0",
        "attribution": "영상 출처: KTV 국민방송 · 텍스트 출처: korea.kr·유튜브 자동 자막",
        "notice": "요약·화자 구분·연결 관계는 AI가 생성한 것으로 오류가 있을 수 있습니다.",
        "meetings": meetings,
        "threads": threads,
    }, minify=True)

    print(f"[build_index] 회의 {len(meetings)} · 문장 {len(docs):,} · 샤드 {shard_count}"
          f" · 스레드 {len(threads)}", flush=True)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run()


if __name__ == "__main__":
    main()
