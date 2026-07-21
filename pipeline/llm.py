"""LLM 공통 계층 (SPEC-PIPELINE.md §6).

- 모델: claude-sonnet 계열 고정
- 프로바이더 2종: ANTHROPIC_API_KEY가 있으면 Message Batches API(스펙 기본, 50% 할인),
  없고 OPENROUTER_API_KEY가 있으면 OpenRouter 동기 호출로 동일 모델 사용(할인 없음)
- 호출마다 pipeline/usage.json에 (단계, 토큰, 비용 추정) 누적
- 키가 전혀 없으면 provider() == None — 호출부는 해당 단계를 건너뛴다
"""
import json
import os
import threading
import time
from datetime import datetime

import requests

from .config import KST, ROOT

MODEL = "claude-sonnet-5"
OPENROUTER_MODEL = "anthropic/claude-sonnet-5"
OPENAI_MODEL = "gpt-5-mini"   # 스펙 §6(claude-sonnet 고정)의 예외 — 사용자가 OpenAI 키 선택
# Anthropic Message Batches 단가 (표준가 $3/$15의 50%)
BATCH_USD_PER_MTOK_INPUT = 1.5
BATCH_USD_PER_MTOK_OUTPUT = 7.5
# OpenRouter 단가 (2026-07 기준 $2/$10)
OPENROUTER_USD_PER_MTOK_INPUT = 2.0
OPENROUTER_USD_PER_MTOK_OUTPUT = 10.0
# OpenAI gpt-5-mini 단가
OPENAI_USD_PER_MTOK_INPUT = 0.25
OPENAI_USD_PER_MTOK_OUTPUT = 2.0

USAGE_FILE = ROOT / "pipeline" / "usage.json"
PROMPTS_DIR = ROOT / "pipeline" / "prompts"


def _get_key(name: str) -> str | None:
    """환경변수 우선, 없으면 Windows 사용자 환경변수(레지스트리)에서 읽는다.

    (셸 시작 이후 등록된 변수는 자식 프로세스에 전파되지 않으므로 로컬 실행 대비)
    """
    key = os.environ.get(name)
    if not key:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                key = winreg.QueryValueEx(h, name)[0]
        except (OSError, ImportError):   # ImportError: Linux(Actions)엔 winreg 없음
            return None
    # 저장 형태 방어: 따옴표·공백 등이 섞여 있으면 sk- 토큰만 추출
    key = key.strip().strip('"').strip("'")
    if " " in key:
        for token in key.split():
            if token.startswith("sk-"):
                key = token
                break
    return key or None


def _openrouter_key() -> str | None:
    key = _get_key("OPENROUTER_API_KEY")
    return key if key and key.startswith("sk-or-") else None  # 형식 불량 키 배제


def _openai_key() -> str | None:
    key = _get_key("OPENAI_API_KEY")
    return key if key and key.startswith("sk-") else None


def provider() -> str | None:
    if _get_key("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _openrouter_key():
        return "openrouter"
    if _openai_key():
        return "openai"
    return None


def available() -> bool:
    return provider() is not None


def active_model() -> str:
    return {"anthropic": MODEL, "openrouter": OPENROUTER_MODEL,
            "openai": OPENAI_MODEL}.get(provider() or "", "")


def get_client():
    import anthropic
    return anthropic.Anthropic(api_key=_get_key("ANTHROPIC_API_KEY"))


def complete(prompt: str, stage: str, max_tokens: int = 8000) -> str:
    """동기 호출 (429/5xx 3회 재시도). 응답 텍스트 반환 + 사용량 기록."""
    prov = provider()
    if prov == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        key = _openai_key()
        body = {
            "model": OPENAI_MODEL,
            "max_completion_tokens": max_tokens + 4000,  # 추론 토큰 여유분 포함
            "reasoning_effort": "minimal",   # 교정은 기계적 작업 — 추론 토큰 소진 방지
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        key = _openrouter_key()
        body = {
            "model": OPENROUTER_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    for attempt in range(3):
        res = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                            json=body, timeout=300)
        if res.status_code in (429, 500, 502, 503, 529):
            time.sleep(10 * (attempt + 1))
            continue
        res.raise_for_status()
        data = res.json()
        usage = data.get("usage", {})
        record_usage(stage, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                     provider_name=prov)
        return data["choices"][0]["message"]["content"]
    raise RuntimeError(f"{prov} 호출 3회 실패 (마지막 status {res.status_code})")


def load_prompt(name: str) -> str:
    """프롬프트는 /pipeline/prompts/*.md로 버전 관리 — 코드 하드코딩 금지 (§6)."""
    with open(PROMPTS_DIR / f"{name}.md", encoding="utf-8") as f:
        return f.read()


_usage_lock = threading.Lock()


def record_usage(stage: str, input_tokens: int, output_tokens: int, calls: int = 1,
                 provider_name: str = "anthropic") -> None:
    """월 단위 사용량 누적 (스레드 안전)."""
    if provider_name == "openrouter":
        in_price, out_price = OPENROUTER_USD_PER_MTOK_INPUT, OPENROUTER_USD_PER_MTOK_OUTPUT
    elif provider_name == "openai":
        in_price, out_price = OPENAI_USD_PER_MTOK_INPUT, OPENAI_USD_PER_MTOK_OUTPUT
    else:
        in_price, out_price = BATCH_USD_PER_MTOK_INPUT, BATCH_USD_PER_MTOK_OUTPUT
    month = datetime.now(KST).strftime("%Y-%m")
    with _usage_lock:
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
            + input_tokens / 1e6 * in_price
            + output_tokens / 1e6 * out_price,
            4,
        )
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(usage, f, ensure_ascii=False, indent=2)
            f.write("\n")
