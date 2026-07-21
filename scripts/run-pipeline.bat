@echo off
rem 파이프라인 수동 실행: 수집→교정→3층→스레드→색인 후 변경분 커밋·push.
rem 더블클릭으로 실행. 새 회의가 없으면 "변경 없음"으로 끝난다.
chcp 65001 >nul
cd /d "%~dp0.."

python -m pipeline.run_all
if errorlevel 1 (
    echo.
    echo 파이프라인 실행 중 오류가 있었습니다. 위 로그를 확인하세요.
)

git add -A
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "pipeline: manual run %date% %time:~0,5%"
    git push
    echo.
    echo 커밋·push 완료 — 1~2분 뒤 onmalrok.vercel.app 에 반영됩니다.
) else (
    echo.
    echo 변경 없음 — 새로 처리할 회의가 없습니다.
)
pause
