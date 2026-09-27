# Kill-feed poll (a scheduled task, every 5 minutes). One pass of
# sample_parties.py --poll-events: the newest ~1,000 kill events from the
# official gameinfo feed, grouped by battle and merged into per-battle
# cache records (source: events_poll). Cache only: it never rewrites the
# artifact, never rebuilds, never commits. Network step, never part of a
# build.
#
# WHY A POLL BESIDE THE TWICE-DAILY HARVEST. The harvest discovers fights
# through albionbb's battle list at a player floor (25 and 8), which is
# blind to the Ancient Lands portal pools of 2-3, 4-5 and 5-7 players:
# their fights are 4-14 players and the official battle record lags the
# kills. The events feed carries the killer's party and every combat
# role's equipment in the list itself, exposes only the newest thousand
# kills, and portals open on 30 / 60 / 180 minute locks, so the kills
# arrive in bursts; a poll every five minutes catches each small-bracket
# kill. Every record carries the event's KillArea, the content classifier
# the API exposes, so the first portal kill observed names the label the
# derive steps then select on (sample_parties.py "CONTENT TAG").
#
# Registered as a Windows scheduled task (every 5 minutes, current user,
# 4 minute limit, HIDDEN window) from PowerShell:
#   $a = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\VS Projects\Bion\pipeline\poll_events.ps1"'
#   $t = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
#   $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -StartWhenAvailable -MultipleInstances IgnoreNew
#   Register-ScheduledTask -TaskName "CompForge kill-feed poll" -Action $a -Trigger $t -Settings $s -Force
# Remove with:
#   Unregister-ScheduledTask -TaskName "CompForge kill-feed poll" -Confirm:$false
# Logs: pipeline/out/fetch_logs/poll-<date>.log (gitignored), one per day,
# a week kept.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $root "pipeline\out\fetch_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "poll-$stamp.log"
Get-ChildItem $logDir -Filter "poll-*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force -ErrorAction SilentlyContinue
Set-Location $root

"=== poll $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8 -Append
& py -3 -u pipeline/sample_parties.py --poll-events --server us 2>&1 |
    Out-File $log -Encoding utf8 -Append
"--- exit $LASTEXITCODE ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
