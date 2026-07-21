"""06 summarize: 의제 단위 흐름을 따르는 전체 brief (SPEC-PIPELINE.md §4 #06).

- 5문단 이내, 각 문단 끝에 근거 문장 번호 [#n #m] 마커 (schema의 brief는 문자열이므로
  인라인 마커 방식 — 프론트가 파싱해 PlayLink 생성 가능. pipeline/README.md에 문서화)
"""
from datetime import datetime

from . import llm
from .config import KST
from .util import numbered_sentences, parse_json_response


def build_summary(meeting: dict) -> None:
    agenda_text = "\n".join(
        f"- {a['title']} (문장 {a['sid_range'][0].split('#')[1]}~{a['sid_range'][1].split('#')[1]})"
        for a in meeting.get("agenda", [])
    ) or "(의제 구간 없음)"
    prompt = (
        llm.load_prompt("summarize")
        .replace("{agenda}", agenda_text)
        .replace("{sentences}", numbered_sentences(meeting["statements"]))
    )
    raw = llm.complete(prompt, stage="summarize", max_tokens=4000)
    brief = str(parse_json_response(raw)["brief"]).strip()
    if not brief:
        raise ValueError("brief 비어 있음")
    meeting["summary"] = {
        "brief": brief,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "model": llm.active_model(),
    }
