"""스레드 title 의제문 백필 (1회성 — SPEC-PIPELINE.md §2.5, Phase P7).

기존 스레드의 축약 title을 시드 지시 발화 기반 명사형 의제문(25자 내외)으로 갱신한다.
멱등: 재실행해도 id·노드는 불변, title만 덮어쓴다. text 원본은 스레드에 없으므로 손실 없음.

    python -m pipeline.backfill_titles [--limit N] [--dry-run]
"""
import sys

from . import llm
from .config import DATA_DIR
from .util import load_json, parse_json_response, save_json

THREADS_DIR = DATA_DIR / "threads"
BATCH = 15
TITLE_MAX = 40


def run(limit: int | None = None, dry_run: bool = False) -> None:
    if not llm.available():
        print("[backfill_titles] LLM 키 없음 — 중단")
        return
    threads = [t for t in (load_json(p, None) for p in sorted(THREADS_DIR.glob("*.json"))) if t]
    if limit:
        threads = threads[:limit]
    updated = 0
    for i in range(0, len(threads), BATCH):
        batch = threads[i:i + BATCH]
        listing = "\n".join(
            f"- id: {t['id']}\n  현재 제목: {t['title']}\n"
            f"  지시 발화: {next((n.get('grade_evidence') or '' for n in sorted(t['nodes'], key=lambda n: n['date']) if n.get('grade') == 'explicit'), '')}\n"
            f"  태그: {', '.join(t.get('topic_tags', []))}"
            for t in batch
        )
        prompt = llm.load_prompt("titles_backfill").replace("{threads}", listing)
        try:
            titles = parse_json_response(
                llm.complete(prompt, stage="backfill_titles", max_tokens=3000))["titles"]
        except Exception as e:
            print(f"[backfill_titles] 배치 {i // BATCH + 1} 실패: {e} — 건너뜀", flush=True)
            continue
        by_id = {t["id"]: t for t in batch}
        for item in titles:
            th = by_id.get(item.get("id"))
            new_title = str(item.get("title") or "").strip()[:TITLE_MAX]
            if th is None or not new_title or new_title == th["title"]:
                continue
            print(f"  {th['title']}  →  {new_title}", flush=True)
            if not dry_run:
                th["title"] = new_title
                save_json(THREADS_DIR / f"{th['id']}.json", th)
            updated += 1
    print(f"[backfill_titles] {updated}/{len(threads)} 갱신{' (dry-run)' if dry_run else ''}",
          flush=True)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    run(limit=limit, dry_run="--dry-run" in args)


if __name__ == "__main__":
    main()
