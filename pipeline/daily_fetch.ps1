# Daily killboard fetch — CACHE ONLY (owner directive 2026-08-27:
# accumulate group-fight evidence daily; analyze + commit deliberately).
#
# What this does:  grow the local battle caches (gitignored) with fresh
#                  GROUP fights from api.albionbb.com, politely.
# What this NEVER does: rebuild committed artifacts, run analysis, touch
#                  scoring, or commit anything. The weekly cadence
#                  (pipeline/README.md) re-analyzes offline (--pages 0)
#                  and commits with the full gate list.
#
# GROUP-FIGHT GUARANTEE (owner 2026-08-27: "not smallscale like corrupted
# 1v1"): the battles endpoint aggregates kills into battles and is only
# ever queried with a total-player floor — sample_battles here at
# minPlayers=10 (group fights; the repo default 6 remains for manual
# runs), sample_rosters hardcoded at minPlayers=40 + a kill-density gate.
# A 1v1/2v2 (corrupted dungeon, mists duel) is a 2-4 player battle and
# can never enter either sweep. Analysis additionally buckets by actual
# fight size, so nothing small can contaminate party-size statistics.
#
# The samplers rewrite their committed analysis artifacts at the end of a
# fetch run; this script restores those to their pre-run bytes so the
# working tree stays clean and analysis stays a deliberate, reviewed step.
#
# Registered as Windows Task Scheduler job "AlbionCompForge Daily Fetch"
# (see pipeline/README.md). Re-register after moving the repo:
#   schtasks /create /tn "AlbionCompForge Daily Fetch" /sc DAILY /st 09:30 /f `
#     /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"<repo>\pipeline\daily_fetch.ps1\""

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $repo "pipeline\out\fetch_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "daily_fetch.log"
# rotate: keep the log under ~1 MB
if ((Test-Path $log) -and (Get-Item $log).Length -gt 1MB) {
    Move-Item -Force $log "$log.1"
}
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $log "==== daily fetch $stamp ===="

# preserve committed analysis artifacts (fetch-only discipline)
$preserve = @("pipeline\out\weapon_usage_v2.json",
              "pipeline\out\roster_mixes.json")
$saved = @{}
foreach ($rel in $preserve) {
    $p = Join-Path $repo $rel
    if (Test-Path $p) {
        $tmp = [System.IO.Path]::GetTempFileName()
        Copy-Item -Force $p $tmp
        $saved[$p] = $tmp
    }
}

Set-Location $repo
# cmd-level redirection writes raw bytes — avoids PS 5.1's UTF-16 *>> logs
cmd /c "py -3 -u pipeline\sample_battles.py --min-players 10 --battles 120 >> `"$log`" 2>&1"
Add-Content $log "sample_battles exit: $LASTEXITCODE"
cmd /c "py -3 -u pipeline\sample_rosters.py --pages 15 >> `"$log`" 2>&1"
Add-Content $log "sample_rosters exit: $LASTEXITCODE"

foreach ($p in $saved.Keys) {
    Copy-Item -Force $saved[$p] $p
    Remove-Item -Force $saved[$p]
}
Add-Content $log "artifacts restored; caches grown: battles=$((Get-ChildItem (Join-Path $repo 'pipeline\out\battles_cache') -ErrorAction SilentlyContinue).Count) rosters=$((Get-ChildItem (Join-Path $repo 'pipeline\out\roster_cache') -ErrorAction SilentlyContinue).Count)"
