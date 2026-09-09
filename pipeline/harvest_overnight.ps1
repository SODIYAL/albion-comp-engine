# Killboard harvest (owner 2026-09-04: "make this an overnight task";
# 2026-09-09: "go for it" on twice daily + parallel). Runs the two
# sample_parties.py passes back to back — the 25-player floor (ZvZ) and the
# 8-player floor (small scale) — each walking the full reachable discovery
# list (40 pages x 20 battles) and skipping what the per-battle cache
# already holds, so a run fetches only the fights that appeared since the
# last one. Network step, never part of a build.
#
# TWICE A DAY, because the discovery list is only 800 battles deep and how
# far back that reaches depends on the floor (measured 2026-09-09, US):
# 25+ spans ~60 h, 20+ ~39 h, 15+ ~20 h, 10+ ~13.5 h, 8+ ~12.6 h. One 03:00
# pass therefore saw every ZvZ fight but missed about half of each day's
# 8-24-player fights — the 15-19 band where kite and clap_kite rosters
# live. Passes at 03:00 and 15:00 cover the day at every floor. The floor
# stays at 8 (not 15): fights under 15 players supply 35% of the gang
# band's builds at the same events-per-build cost as ZvZ.
#
# PARALLEL: sample_parties.py fetches battles four at a time (--workers,
# default 4; events within a battle stay sequential, cache files are
# byte-identical to the sequential loop's). A pass that took ~1 s per
# event now takes ~0.25 s; every pass ends with an "event coverage" line
# (sequential baseline 0.987) and a tally of request misses by HTTP code —
# 502s are the API, 429s mean lower --workers.
#
# It does NOT rebuild the dataset or commit: the harvest lands in
# pipeline/out/party_cache/ (gitignored) and pipeline/out/party_rosters.json;
# rebuilding, the gate list and the audit stay a reviewed, in-session step
# (pipeline/README.md, CLAUDE.md "Kits are what winners wear").
#
# SIBLING JOB: pipeline/daily_fetch.ps1 (09:30) grows the albionbb battle
# caches behind weapon_usage_v2.json (prevalence, cohorts, families) — a
# different API and cache; neither job subsumes the other.
#
# Registered as a Windows scheduled task (daily 03:00 AND 15:00, current
# user, 6 h limit, runs late if the machine was asleep, HIDDEN window) from
# PowerShell:
#   $a = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\VS Projects\Bion\pipeline\harvest_overnight.ps1"'
#   $t1 = New-ScheduledTaskTrigger -Daily -At 3am
#   $t2 = New-ScheduledTaskTrigger -Daily -At 3pm
#   $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 6) -StartWhenAvailable
#   Register-ScheduledTask -TaskName "CompForge overnight harvest" -Action $a -Trigger @($t1, $t2) -Settings $s -Force
# -WindowStyle Hidden matters (2026-09-08): without it the run pops a console
# window on the desktop, and closing that window kills the harvest with
# 0xC000013A — three nights were lost that way before the flag was added.
# (schtasks.exe chokes on the space in the repo path.) Remove with:
#   Unregister-ScheduledTask -TaskName "CompForge overnight harvest" -Confirm:$false
# Logs: pipeline/out/fetch_logs/harvest-<date>.log (gitignored).
#
# FOCUSED NIGHT (owner 2026-09-08: "focus on 7v7 fights and 5v5 fights"):
# pass a fight-size band and the script runs ONE pass over that band instead
# of the two floors, spending the whole budget on fights of that size —
#   powershell -NoProfile -ExecutionPolicy Bypass -File pipeline/harvest_overnight.ps1 -MinPlayers 10 -MaxPlayers 14
# (5v5 = 10 listed players, 7v7 = 14; the ceiling is a local filter on
# albionbb's totalPlayers, see sample_parties.py). To make the 03:00 task do
# it for one night without touching the daily registration, add a one-shot
# task and remove it in the morning:
#   $a = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\VS Projects\Bion\pipeline\harvest_overnight.ps1" -MinPlayers 10 -MaxPlayers 14'
#   Register-ScheduledTask -TaskName "CompForge focused harvest" -Action $a -Trigger (New-ScheduledTaskTrigger -Once -At 3am) -Settings $s -Force
#   Unregister-ScheduledTask -TaskName "CompForge focused harvest" -Confirm:$false
# The cache keeps everything ever fetched and the analysis reads all of it,
# so a focused night ADDS small-fight parties to the corpus; it never
# narrows what party_rosters.json is derived from.

param(
    [int]$MinPlayers = 0,   # >0 with MaxPlayers: one banded pass
    [int]$MaxPlayers = 0,   # 0 = no ceiling
    [int]$Battles = 800
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $root "pipeline\out\fetch_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "harvest-$stamp.log"   # both daily runs append here
# one log per day: keep a month, drop the rest
Get-ChildItem $logDir -Filter "harvest-*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force -ErrorAction SilentlyContinue
Set-Location $root

"=== overnight harvest $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8 -Append
if ($MinPlayers -gt 0 -or $MaxPlayers -gt 0) {
    if ($MinPlayers -le 0) { $MinPlayers = 8 }
    "--- focused pass: players $MinPlayers-$MaxPlayers, up to $Battles battles ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    & py -3 -u pipeline/sample_parties.py --battles $Battles --min-players $MinPlayers --max-players $MaxPlayers --server us 2>&1 |
        Out-File $log -Encoding utf8 -Append
    "--- pass exit $LASTEXITCODE ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
} else {
    foreach ($floor in @(25, 8)) {
        "--- pass: min-players $floor, up to $Battles battles ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
        & py -3 -u pipeline/sample_parties.py --battles $Battles --min-players $floor --server us 2>&1 |
            Out-File $log -Encoding utf8 -Append
        "--- pass exit $LASTEXITCODE ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    }
}
$n = (Get-ChildItem (Join-Path $root "pipeline\out\party_cache") -File).Count
"=== done: cache holds $n battles ($(Get-Date -Format s)) ===" | Out-File $log -Encoding utf8 -Append
