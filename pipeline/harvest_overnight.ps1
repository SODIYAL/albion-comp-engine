# Overnight killboard harvest (owner 2026-09-04: "make this an overnight
# task"). Runs the two sample_parties.py passes back to back — the 25-player
# floor (ZvZ) and the 8-player floor (small scale) — each walking the full
# reachable discovery list (40 pages x 20 battles) and skipping what the
# per-battle cache already holds, so a nightly run fetches only the fights
# that appeared since the last one. Network step, never part of a build.
#
# It does NOT rebuild the dataset or commit: the harvest lands in
# pipeline/out/party_cache/ (gitignored) and pipeline/out/party_rosters.json;
# rebuilding, the gate list and the audit stay a reviewed, in-session step
# (pipeline/README.md, CLAUDE.md "Kits are what winners wear").
#
# Registered as a Windows scheduled task (daily 03:00, current user, 6 h
# limit, runs late if the machine was asleep) from PowerShell:
#   $a = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\VS Projects\Bion\pipeline\harvest_overnight.ps1"'
#   $t = New-ScheduledTaskTrigger -Daily -At 3am
#   $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 6) -StartWhenAvailable
#   Register-ScheduledTask -TaskName "CompForge overnight harvest" -Action $a -Trigger $t -Settings $s -Force
# (schtasks.exe chokes on the space in the repo path.) Remove with:
#   Unregister-ScheduledTask -TaskName "CompForge overnight harvest" -Confirm:$false
# Logs: pipeline/out/fetch_logs/harvest-<date>.log (gitignored).

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $root "pipeline\out\fetch_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "harvest-$stamp.log"
Set-Location $root

"=== overnight harvest $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8 -Append
foreach ($floor in @(25, 8)) {
    "--- pass: min-players $floor, up to 800 battles ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    & py -3 -u pipeline/sample_parties.py --battles 800 --min-players $floor --server us 2>&1 |
        Out-File $log -Encoding utf8 -Append
    "--- pass exit $LASTEXITCODE ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
}
$n = (Get-ChildItem (Join-Path $root "pipeline\out\party_cache") -File).Count
"=== done: cache holds $n battles ($(Get-Date -Format s)) ===" | Out-File $log -Encoding utf8 -Append
