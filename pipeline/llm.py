"""LLM 공통 계층 (SPEC-PIPELINE.md §6).

- 모델: claude-sonnet 계열 고정, Message Batches API 전용(실시간 처리 금지, 50% 할인)
- 호출마다 pipeline/usage.json에 (단계, 토큰, 비용 추정) 누적
- API 키가 없으면 available() == False — 호출부는 해당 단계를 건너뛴다
"""
import json
import os
from datetime import datetime

from .config import KST, ROOT

MODEL = "claude-sonnet-5"
# Message Batches 단가 (표준가 $3/$15의 50%). 프로모션 기간엔 실제 청구액이 더 낮다.
BATCH_USD_PER_MTOK_INPUT = 1.5
BATCH_USD_PER_MTOK_OUTPUT = 7.5

USAGE_FILE = ROOT / "pipeline" / "usage.json"
PROMPTS_DIR = ROOT / "pipeline" / "prompts"


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_client():
    import anthropic
    return anthropic.Anthropic()


def load_prompt(name: str) -> str:
    """프롬프트는 /pipeline/prompts/*.md로 버전 관리 — 코드 하드코딩 금지 (§6)."""
    with open(PROMPTS_DIR / f"{name}.md", encoding="utf-8") as f:
        return f.read()


def record_usage(stage: str, input_tokens: int, output_tokens: int, calls: int = 1) -> None:
    """월 단위 사용량 누적."""
    month = datetime.now(KST).strftime("%Y-%m")
    usage = {}
    if USAGE_FILE.exists():
        with open(USAGE_FILE, encoding="utf-8") as f:
            usage = json.load(f)
    entry = usage.setdefault(month, {}).setdefault(
        stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    )
    entry["calls"] += calls
    entry["input_tokens"] += input_tokens
    entry["output_tokens"] += output_tokens
    entry["cost_usd"] = round(
        entry["cost_usd"]
        + input_tokens / 1e6 * BATCH_USD_PER_MTOK_INPUT
        + output_tokens / 1e6 * BATCH_USD_PER_MTOK_OUTPUT,
        4,
    )
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False, indent=2)
        f.write("\n")
