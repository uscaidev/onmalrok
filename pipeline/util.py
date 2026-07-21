"""공용 IO·파싱 헬퍼."""
import json
import re

from .config import MEETINGS_DIR


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj, minify: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if minify:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")


def load_meeting(meeting_id: str) -> dict | None:
    return load_json(MEETINGS_DIR / f"{meeting_id}.json", None)


def save_meeting(meeting: dict) -> None:
    save_json(MEETINGS_DIR / f"{meeting['id']}.json", meeting)


def parse_json_response(text: str) -> dict:
    """LLM 응답에서 JSON 객체 추출. 코드펜스·잡문 허용."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("JSON 객체 없음")
    return json.loads(text[start:end + 1])


def seq_of(sid: str) -> int:
    return int(sid.split("#")[1])


def numbered_sentences(statements: list[dict]) -> str:
    return "\n".join(f"{seq_of(s['sid'])}. {s['text']}" for s in statements)


def sanitize_starts(starts: list[int], total: int) -> list[int]:
    """분할 시작점 정리: 범위 내·중복 제거·오름차순, 1번 문장 시작 강제."""
    ok = sorted({s for s in starts if isinstance(s, int) and 1 <= s <= total})
    if not ok or ok[0] != 1:
        ok = [1] + [s for s in ok if s != 1]
    return ok
