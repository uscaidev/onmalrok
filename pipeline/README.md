# pipeline — 유튜브 수집·자막 파이프라인 (트랙 A)

설계서: [SPEC-PIPELINE.md](../SPEC-PIPELINE.md). 산출 스키마의 SSOT는 §2.

## 실행

```bash
pip install -r pipeline/requirements.txt

python -m pipeline.run_all              # 감지 → 자막 폴링 → 가공 → 검증 (Actions가 일 3회 실행)
python -m pipeline.run_all --reprocess  # 자막 보유분 전체 재분할 (멱등)
python -m pipeline.backfill             # 과거 회의 등록 (--since 2025-06-01, --max 150)
```

## 구성 (Phase 1·2)

| 파일 | 역할 |
|------|------|
| `config.py` | 채널 ID·경로·판별 상수 |
| `state.py` | `data/state/videos.json` 상태 머신 저장소 |
| `discover.py` | KTV RSS 감지 → `discovered` 등록 (§3.1) |
| `poll_captions.py` | yt-dlp 자막 폴링·다운로드, 7일 만료 (§3.2·3.3) |
| `segment.py` | 02: vtt → 문장 분할 → 최소 Meeting JSON (§4) |
| `correct.py` | 03: 오인식 교정(Message Batches API) + 용어집 축적 (§4·§5) |
| `llm.py` | LLM 공통 계층 — 모델·단가·usage.json 누적 (§6) |
| `prompts/correct.md` | 교정 프롬프트 (코드 하드코딩 금지 — §6) |
| `validate.py` | 산출 검증 — 실패 시 partial 강등 (§7) |
| `run_all.py` | 오케스트레이터, 회의별 try/except 격리 (§8) |
| `backfill.py` | 과거 회의 채널 검색·재생목록 백필 |

원본 vtt는 `pipeline/raw/subs/{youtube_id}.ko.vtt`로 커밋해 재처리를 보장한다.

## 스펙 대비 판단 기록

- **excluded 상태 추가**: 제목 정규식(§3.1)만으로는 홍보 쇼츠·발언 클립이 매치되므로,
  폴링 시 재생시간 20분 미만을 `excluded`로 제외. 실제 본회의 최단 길이는 27분.
- **백필 필터**: 채널 검색 결과에 과거 정부 영상이 섞이므로 제목의 방송일 표기 파싱 +
  2025-06-01(현 정부 국무회의 시작) 이후 + 재생시간 하한으로 본회의만 등록.
- Phase 1의 Meeting은 문장 층만 채운다: `turns`/`agenda` 빈 배열, `turn_id`/`agenda_id`는
  null (Phase 3에서 채움), `text`는 교정 전이므로 `text_raw`와 동일 (Phase 2에서 갱신).

## 교정(03) 동작 방식

- **Message Batches API 비동기 2단계**: 실행 N에서 배치 제출 → 실행 N+1에서 수거·적용.
  일 3회 cron이므로 신규 회의는 최대 반나절 내 교정 완료. 50% 배치 할인 적용.
- 진행 중 배치는 `data/state/batches.json`에 기록(실패 청크는 3회까지 재제출 — §6).
- 적용 가드레일: 원문 대비 길이 비율 1/1.6~1.6 벗어나면 기각(요약·부연 의심), text_raw 불변.
- 용어집: 교정 diff의 어절 치환쌍이 2회 이상 관찰되면 `data/glossary.json` 승격,
  다음 교정 프롬프트에 자동 주입 (§5.2). 후보 빈도는 `data/state/glossary_candidates.json`.
- `ANTHROPIC_API_KEY` 미설정 시 교정 단계는 건너뛰고 대기 회의 수만 로그.
  키 설정(Actions secret) 후 다음 실행부터 자동으로 백필 교정이 시작된다.
