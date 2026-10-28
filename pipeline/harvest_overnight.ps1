# Killboard harvest (a scheduled task, twice daily, parallel). One
# sample_parties.py pass at the 8-player floor: every fight the kill-feed
# poll recorded with 8+ seen players in the last 36 hours, finished an hour
# or more ago and not yet harvested, upgraded to its official roster
# (sample_parties.py "DISCOVERY", "WINDOW"). Network step, never part of a
# build.
#
# TWICE A DAY keeps each pass to half a day of fights; the 36-hour window
# holds a run the machine slept through, so the next run still reaches its
# fights. A fight the roster puts under the floor stays the poll's record
# and costs one request per pass whose window holds it (about one
# candidate in two at 8 seen players). The floor stays at 8 (not 15):
# fights under 15 players supply 35% of the gang band's builds at the same
# events-per-build cost as ZvZ.
#
# PARALLEL: sample_parties.py reads battles four at a time (--workers,
# default 4; the requests within a battle stay sequential). Every pass ends
# with an "official rosters" line (harvested / outside the band /
# unavailable), an "event coverage" line and a tally of request misses by
# HTTP code — 502s are the API, 429s mean lower --workers.
#
# CACHED EVENTS: a kill the poll already stored is read from its record
# (the poll holds every kill of 93% of the fights of 8+), so a pass costs
# the official roster and, for a fight the poll did not hold whole, the
# battle's own kill list; the pass prints how many it read from the cache.
#
# FAILS LOUDLY: the pass exits 1 when the poll has written nothing for 6
# hours or when more than half its roster requests failed ("pass exit 1"
# in the log); a refused request no longer reads as "0 battles to fetch".
#
# It does NOT rebuild the dataset or commit: the harvest lands in
# pipeline/out/party_cache.sqlite (gitignored), pipeline/out/party_rosters.json.gz
# (the populations the build reads) and pipeline/out/party_rosters_full.json.gz
# (every record, gitignored);
# rebuilding, the gate list and the audit stay a reviewed, in-session step
# (pipeline/README.md, CLAUDE.md "Kits are what winners wear").
#
# This harvest is the ONE killboard sampler: weapon_usage_v2.json
# (prevalence, cohorts, families) is derived from its full rosters artifact
# by pipeline/derive_usage.py at the fold.
#
# Registered as a Windows scheduled task (daily 03:00 AND 15:00, current
# user, 6 h limit, runs late if the machine was asleep, HIDDEN window) from
# PowerShell:
#   $a = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\VS Projects\Bion\pipeline\harvest_overnight.ps1"'
#   $t1 = New-ScheduledTaskTrigger -Daily -At 3am
#   $t2 = New-ScheduledTaskTrigger -Daily -At 3pm
#   $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 6) -StartWhenAvailable
#   Register-ScheduledTask -TaskName "CompForge overnight harvest" -Action $a -Trigger @($t1, $t2) -Settings $s -Force
# -WindowStyle Hidden matters: without it the run pops a console
# window on the desktop, and closing that window kills the harvest with
# 0xC000013A — three nights were lost that way before the flag was added.
# (schtasks.exe chokes on the space in the repo path.) Remove with:
#   Unregister-ScheduledTask -TaskName "CompForge overnight harvest" -Confirm:$false
# Logs: pipeline/out/fetch_logs/harvest-<date>.log (gitignored).
#
# FOCUSED NIGHT (one fight-size band, e.g. the 5v5 / 7v7 fights):
# pass a fight-size band and the pass reads that band alone, spending the
# whole budget on fights of that size —
#   powershell -NoProfile -ExecutionPolicy Bypass -File pipeline/harvest_overnight.ps1 -MinPlayers 10 -MaxPlayers 14
# (5v5 = 10 players, 7v7 = 14; floor and ceiling read the official roster,
# see sample_parties.py "FIGHT-SIZE BAND"). To make the 03:00 task do
# it for one night without touching the daily registration, add a one-shot
# task and remove it in the morning:
#   $a = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\VS Projects\Bion\pipeline\harvest_overnight.ps1" -MinPlayers 10 -MaxPlayers 14'
#   Register-ScheduledTask -TaskName "CompForge focused harvest" -Action $a -Trigger (New-ScheduledTaskTrigger -Once -At 3am) -Settings $s -Force
#   Unregister-ScheduledTask -TaskName "CompForge focused harvest" -Confirm:$false
# The cache keeps everything ever fetched and the analysis reads all of it,
# so a focused night ADDS small-fight parties to the corpus; it never
# narrows what party_rosters.json.gz is derived from.

# BACKUP: the cache is the one copy of the harvest's evidence (the kill
# feed it was polled from serves no history). After the passes the script
# writes a consistent copy to the folder -BackupDir names, else the
# COMPFORGE_BACKUP_DIR environment variable (a synced folder or a second
# drive, set once per machine), through pipeline/backup_cache.py; with
# neither set, no copy. A backup is never a build input.

param(
    [int]$MinPlayers = 0,   # >0 with MaxPlayers: one banded pass
    [int]$MaxPlayers = 0,   # 0 = no ceiling
    [int]$Battles = 10000,  # the window's candidates, newest first
    [string]$BackupDir = $env:COMPFORGE_BACKUP_DIR
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
if ($MinPlayers -le 0) { $MinPlayers = 8 }
"--- pass: players $MinPlayers-$MaxPlayers (0 = no ceiling), up to $Battles battles ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
& py -3 -u pipeline/sample_parties.py --battles $Battles --min-players $MinPlayers --max-players $MaxPlayers 2>&1 |
    Out-File $log -Encoding utf8 -Append
$passExit = $LASTEXITCODE
"--- pass exit $passExit ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
$n = & py -3 pipeline/party_store.py --count
"=== done: cache holds $n battles ($(Get-Date -Format s)) ===" | Out-File $log -Encoding utf8 -Append
if ($BackupDir) {
    "--- backup to $BackupDir ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    & py -3 -u pipeline/backup_cache.py --dest $BackupDir 2>&1 | Out-File $log -Encoding utf8 -Append
    "--- backup exit $LASTEXITCODE ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
}
# the pass's exit is the task's: a failed pass shows in the task's last result
exit $passExit
