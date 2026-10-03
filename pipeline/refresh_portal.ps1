# Refresh the Dragon Portal page from the harvest cache. ONE COMMAND for
# the display-only slice of the fold: re-derive the rosters artifact from
# the whole cache (offline), rebuild out/portal_stats.json and the pages,
# run the portal and layout gates. It stops at the first nonzero exit and
# NEVER commits.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File pipeline/refresh_portal.ps1
#
# Then commit ONLY pipeline/out/portal_stats.json, dashboard/portal.html
# and docs/portal.html. The rewritten rosters artifact stays uncommitted:
# the prior, bands, skeletons and portal rows are derived from it together
# in the weekly fold (fold_harvest.ps1), and build_dataset refuses a
# rosters artifact the committed prior was not derived from. The portal
# page sits outside the provenance chain (test_portal_stats P8-P11), so
# its artifact may run ahead of the rosters between folds.
#
# Logs: pipeline/out/fetch_logs/portal-<date>.log.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $root "pipeline\out\fetch_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "portal-$stamp.log"
Set-Location $root
"=== portal refresh $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8

function Step($label, $exe, $argv) {
    $t0 = Get-Date
    "--- $label ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    & $exe @argv 2>&1 | Out-File $log -Encoding utf8 -Append
    $rc = $LASTEXITCODE
    $secs = [int]((Get-Date) - $t0).TotalSeconds
    $last = [string](Get-Content $log | Where-Object { $_ -match '\S' } | Select-Object -Last 1)
    "{0,-26} exit {1,-3} {2,5}s  {3}" -f $label, $rc, $secs, $last.Substring(0, [Math]::Min(90, $last.Length))
    if ($rc -ne 0) {
        Write-Host "STOPPED at $label (exit $rc) - see $log"
        exit $rc
    }
}

Step "rosters from cache"    "py" @("-3", "-u", "pipeline/sample_parties.py", "--pages", "0")
Step "build_portal_stats"    "py" @("-3", "-u", "pipeline/build_portal_stats.py")
Step "dashboard build"       "py" @("-3", "-u", "dashboard/build.py")
Step "test_portal_stats"     "py" @("-3", "-u", "tests/test_portal_stats.py")
Step "test_portal_page"      "node" @("tests/test_portal_page.js")
Step "test_dashboard_layout" "py" @("-3", "-u", "tests/test_dashboard_layout.py")

"=== portal refresh complete $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8 -Append
Write-Host ""
Write-Host "Green. Commit pipeline/out/portal_stats.json, dashboard/portal.html and"
Write-Host "docs/portal.html; leave pipeline/out/party_rosters.json.gz for the fold."
