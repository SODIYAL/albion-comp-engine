# The harvest guard, dot-sourced by fold_harvest.ps1 and refresh_portal.ps1.
# A harvest pass ends by rewriting pipeline/out/party_rosters.json.gz from
# the cache, so a fold or a portal refresh begun while a harvest runs can
# have its rosters artifact replaced under it: the derived tables then
# record a hash no file has and build_dataset refuses the tree. A harvest
# is running when a "CompForge ... harvest" scheduled task is Running, or
# when a process runs harvest_overnight.ps1 or a sample_parties.py harvest
# pass (--battles). The kill-feed poll (--poll-events) writes the cache
# only and does not count.

function Get-RunningHarvest {
    $found = @()
    $tasks = Get-ScheduledTask -TaskName "CompForge*harvest*" -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Running" }
    foreach ($t in $tasks) { $found += "scheduled task '$($t.TaskName)' is running" }
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessId -ne $PID -and
                       $_.CommandLine -match 'harvest_overnight\.ps1|sample_parties\.py\b.*--battles\b' }
    foreach ($p in $procs) { $found += "process $($p.ProcessId): $($p.CommandLine)" }
    return ,$found
}

function Assert-NoHarvest($what) {
    $running = Get-RunningHarvest
    if ($running.Count -gt 0) {
        Write-Host "REFUSED: a harvest is running, and each of its passes ends by rewriting"
        Write-Host "pipeline/out/party_rosters.json.gz; a $what begun now could have that artifact"
        Write-Host "replaced under it."
        foreach ($r in $running) { Write-Host "  $r" }
        Write-Host "Start the $what once the harvest ends (Get-ScheduledTask 'CompForge overnight harvest'"
        Write-Host "reads Ready again)."
        exit 3
    }
}
