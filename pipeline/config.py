"""파이프라인 공통 설정 (SPEC-PIPELINE.md §1)."""
import re
from datetime import timedelta, timezone
from pathlib import Path

# KTV 국민방송
CHANNEL_ID = "UCIMOytYIzaUpoAM2bpT4JZQ"
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

# 대상 판별: 제목에 국무회의 또는 업무보고 포함 (SPEC-PIPELINE.md §3.1)
TITLE_PATTERN = re.compile(r"국무회의|업무보고")

KST = timezone(timedelta(hours=9), "KST")

# 최초 감지 후 이 기간 내 자막 미생성 시 captions_missing (§3.3)
CAPTION_EXPIRY_DAYS = 7

# 본회의 판별용 최소 재생시간 — 제목 정규식만으로는 홍보 쇼츠·발언 클립이 섞이므로
# 폴링 시 실제 재생시간으로 제외한다(상태 excluded). 판단 근거: 실제 회의는 최단 27분.
MIN_MEETING_DURATION_SEC = 1200

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATE_FILE = DATA_DIR / "state" / "videos.json"
MEETINGS_DIR = DATA_DIR / "meetings"
RAW_SUBS_DIR = ROOT / "pipeline" / "raw" / "subs"


def classify_kind(title: str) -> str:
    """제목으로 회의 종류 판별. 국무회의 표기가 있으면 cabinet, 아니면 report."""
    return "cabinet" if "국무회의" in title else "report"


def kind_code(kind: str) -> str:
    return "cab" if kind == "cabinet" else "rpt"
