#Requires -Version 5.1
<#
.SYNOPSIS
  Fetches O*NET, related-occupation research files, AIOE, and key PDFs into this folder.
.DESCRIPTION
  Use curl.exe (not Invoke-WebRequest) for large O*NET zips: IWR often fails mid-stream
  ("The response ended prematurely") or hits Schannel TLS revocation issues. On Windows,
  curl uses --ssl-no-revoke to avoid CRYPT_E_NO_REVOCATION_CHECK in some environments.
#>
$ErrorActionPreference = 'Stop'
$Base = $PSScriptRoot
$Dl = Join-Path $Base 'downloads'
$Papers = Join-Path $Base 'papers'
New-Item -ItemType Directory -Path $Dl, $Papers -Force | Out-Null

$curl = 'curl.exe'
# --retry-all-errors: O*NET occasionally drops TLS mid-file (curl 56 close_notify); BLS may still 403 (use browser).
$curlBase = @('--ssl-no-revoke', '--fail', '--location', '--retry', '8', '--retry-all-errors', '--retry-delay', '3', '-A', 'Mozilla/5.0')

function Save-Curl($Uri, $OutPath) {
  Write-Host "GET $Uri" -ForegroundColor Cyan
  & $curl @curlBase -o $OutPath $Uri
  if ($LASTEXITCODE -ne 0) { throw "curl failed ($LASTEXITCODE): $Uri" }
  $n = (Get-Item $OutPath).Length
  Write-Host "  -> $(Split-Path $OutPath -Leaf)  $([math]::Round($n/1MB, 2)) MB" -ForegroundColor Green
}

# O*NET 30.2 — text bundle must be ~12–14 MB, not a few hundred KB
Save-Curl 'https://www.onetcenter.org/dl_files/database/db_30_2_text.zip' (Join-Path $Dl 'db_30_2_text.zip')
$textLen = (Get-Item (Join-Path $Dl 'db_30_2_text.zip')).Length
if ($textLen -lt 5MB) { throw "db_30_2_text.zip looks truncated ($textLen bytes). Re-run; check VPN/firewall/OneDrive." }

Save-Curl 'https://www.onetcenter.org/dl_files/database/db_30_2_excel.zip' (Join-Path $Dl 'db_30_2_excel.zip')
Save-Curl 'https://www.onetcenter.org/dl_files/Related_Occupations_Research_Dataset.zip' (Join-Path $Dl 'Related_Occupations_Research_Dataset.zip')
Save-Curl 'https://www.onetcenter.org/dl_files/Operational_Related_Occupations_Matrix.xlsx' (Join-Path $Dl 'Operational_Related_Occupations_Matrix.xlsx')
Save-Curl 'https://www.onetcenter.org/dl_files/Related_2022.pdf' (Join-Path $Papers 'ONET_Related_Occupations_2022_report.pdf')

Save-Curl 'https://github.com/AIOE-Data/AIOE/archive/refs/heads/master.zip' (Join-Path $Dl 'AIOE-Data_AIOE_master.zip')
Save-Curl 'https://www.michaelwebb.co/webb_ai.pdf' (Join-Path $Papers 'Webb_Impact_of_AI_on_Labor_Market.pdf')
Save-Curl 'https://arxiv.org/pdf/1604.08823.pdf' (Join-Path $Papers 'Arntz_Gregory_Zierahn_2016_Skills_Tasks_Automation.pdf')

# BLS: often 403 to automation; try browser if this fails
$blsTries = @(
  @('https://www.bls.gov/oes/2024/may/oesm24nat.xlsx', (Join-Path $Dl 'BLS_OEWS_oesm24nat.xlsx')),
  @('https://www.bls.gov/oes/special.requests/oesm24nat.zip', (Join-Path $Dl 'BLS_OEWS_oesm24nat.zip'))
)
foreach ($p in $blsTries) {
  $u, $out = $p[0], $p[1]
  Write-Host "GET (BLS) $u" -ForegroundColor Cyan
  # No --retry-all-errors here: 403 would waste minutes in retry loops.
  & $curl '--ssl-no-revoke', '--fail', '-L', '--retry', '2', '-A', 'Mozilla/5.0', '-o', $out, $u
  if ($LASTEXITCODE -eq 0) { Write-Host "  BLS ok: $(Split-Path $out -Leaf)" -ForegroundColor Green }
  else { Write-Host "  BLS skip (exit $LASTEXITCODE) — download in browser: https://www.bls.gov/oes/current/oes_nat.htm" -ForegroundColor Yellow }
}

# Optional: NBER w21473 landing (PDF often gated; use Deming author PDF in SOURCES.txt)
$nb = Join-Path $Papers 'Deming_Social_Skills_NBER_w21473.html'
try { & $curl @curlBase -o $nb 'https://www.nber.org/papers/w21473' 2>$null } catch { }

Write-Host "`nDone. See SOURCES.txt for manual BLS/Plan HNA/Deming links." -ForegroundColor Gray
