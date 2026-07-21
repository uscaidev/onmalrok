# API 키를 Windows 사용자 환경변수에 저장하는 스크립트.
# 키는 이 PC에만 저장되며 화면에 표시되지 않는다.
#
# 사용법:  powershell -ExecutionPolicy Bypass -File scripts\set-api-key.ps1

Write-Host ""
Write-Host "붙여넣기는 창에서 '마우스 우클릭'을 사용하세요 (Ctrl+V가 안 되는 콘솔이 있음)." -ForegroundColor Cyan
$secure = Read-Host "API 키를 붙여넣고 Enter (입력은 화면에 안 보임)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$key = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

# 복사 시 섞이기 쉬운 따옴표·공백 제거
$key = $key.Trim().Trim('"').Trim("'")

if ($key.Length -eq 0) {
    Write-Host "오류: 아무것도 입력되지 않았습니다. 우클릭으로 붙여넣은 뒤 Enter를 눌러 주세요." -ForegroundColor Red
    exit 1
}
if ($key -match '\s') {
    Write-Host "오류: 키 안에 공백이 있습니다. 키 문자열만 다시 복사해서 실행해 주세요." -ForegroundColor Red
    exit 1
}

# 접두사로 서비스 판별
if ($key.StartsWith('sk-or-')) {
    $name = 'OPENROUTER_API_KEY'
} elseif ($key.StartsWith('sk-ant-')) {
    $name = 'ANTHROPIC_API_KEY'
} elseif ($key.StartsWith('sk-')) {
    $name = 'OPENAI_API_KEY'
} else {
    Write-Host "오류: 알 수 없는 키 형식입니다. (입력 길이: $($key.Length)자, sk-로 시작하지 않음)" -ForegroundColor Red
    Write-Host "  붙여넣기가 잘린 것일 수 있습니다. 키 전체를 다시 복사한 뒤 우클릭으로 붙여넣어 주세요."
    exit 1
}

[Environment]::SetEnvironmentVariable($name, $key, 'User')
Write-Host "$name 저장 완료 (길이 $($key.Length)자)" -ForegroundColor Green

# 실제 인증 확인
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    switch ($name) {
        'OPENROUTER_API_KEY' {
            $r = Invoke-RestMethod -Uri 'https://openrouter.ai/api/v1/credits' -Headers @{ Authorization = "Bearer $key" }
            $left = [math]::Round($r.data.total_credits - $r.data.total_usage, 2)
            Write-Host "인증 성공 — OpenRouter 잔액: `$$left" -ForegroundColor Green
        }
        'ANTHROPIC_API_KEY' {
            Invoke-RestMethod -Uri 'https://api.anthropic.com/v1/models' -Headers @{ 'x-api-key' = $key; 'anthropic-version' = '2023-06-01' } | Out-Null
            Write-Host "인증 성공 — Anthropic API 사용 가능" -ForegroundColor Green
        }
        'OPENAI_API_KEY' {
            Invoke-RestMethod -Uri 'https://api.openai.com/v1/models' -Headers @{ Authorization = "Bearer $key" } | Out-Null
            Write-Host "인증 성공 — OpenAI API 사용 가능" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "경고: 키는 저장됐지만 인증 확인에 실패했습니다. 키가 유효한지 확인하세요." -ForegroundColor Yellow
    Write-Host "  $($_.Exception.Message)"
}

Write-Host ""
Write-Host "완료. 파이프라인은 저장된 키를 바로 읽을 수 있습니다."
