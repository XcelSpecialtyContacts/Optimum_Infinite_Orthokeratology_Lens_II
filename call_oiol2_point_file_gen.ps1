param(
    [string]$wo
)

python -m src.oiol2.main --wo $wo --plot

if ($LASTEXITCODE -ne 0) {
    Write-Host "Program failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Program succeeded"
exit 0