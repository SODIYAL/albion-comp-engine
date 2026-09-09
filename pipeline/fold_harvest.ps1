# Weekly fold of the harvest cache into the dataset (owner 2026-09-09:
# "set it up"). ONE COMMAND for the in-session step the harvest task never
# does: re-derive the rosters artifact from the whole cache, run the
# documented chain in order, rebuild the dataset and the pages, run every
# gate, then write the before/after report the owner reads before
# committing. It stops at the first nonzero exit and NEVER commits -
# review notes/findings/<date>-fold-report.md, then commit.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File pipeline/fold_harvest.ps1
#
# Run it from PowerShell, not Git Bash: test_cohort_families decodes its
# child's stdout as UTF-8 and a Git-Bash-spawned console emits cp1252
# (CLAUDE.md "Environment traps"). Logs: pipeline/out/fetch_logs/fold-<date>.log.
# Cadence: weekly (the corpus grows ~350 battles a day; a daily fold is
# churn, a weekly one is a meaningful step - VALIDATION.md 2026-09-09).

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir = Join-Path $root "pipeline\out\fetch_logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$log = Join-Path $logDir "fold-$stamp.log"
Set-Location $root
"=== fold $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8

function Step($label, $exe, $argv) {
    $t0 = Get-Date
    "--- $label ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    & $exe @argv 2>&1 | Out-File $log -Encoding utf8 -Append
    $rc = $LASTEXITCODE
    $secs = [int]((Get-Date) - $t0).TotalSeconds
    $last = [string](Get-Content $log | Where-Object { $_ -match '\S' } | Select-Object -Last 1)
    "{0,-34} exit {1,-3} {2,5}s  {3}" -f $label, $rc, $secs, $last.Substring(0, [Math]::Min(90, $last.Length))
    if ($rc -ne 0) {
        Write-Host "STOPPED at $label (exit $rc) - see $log"
        exit $rc
    }
}

# 1. the chain, in the documented order (CLAUDE.md "After a harvest")
Step "rosters from cache"     "py" @("-3", "-u", "pipeline/sample_parties.py", "--pages", "0")
Step "audit_style_rosters"    "py" @("-3", "-u", "pipeline/audit_style_rosters.py")
Step "derive_style_bands"     "py" @("-3", "-u", "pipeline/derive_style_bands.py")
Step "derive_party_styles"    "py" @("-3", "-u", "pipeline/derive_party_styles.py")
Step "derive_meta_prior"      "py" @("-3", "-u", "pipeline/derive_meta_prior.py")
Step "build_dataset"          "py" @("-3", "-u", "pipeline/build_dataset.py")
Step "build_cohort_families"  "py" @("-3", "-u", "pipeline/build_cohort_families.py")
Step "dashboard build"        "py" @("-3", "-u", "dashboard/build.py")

# 2. every gate (CLAUDE.md "Tests"; exit 0 = pass)
Step "test_golden"            "py" @("-3", "-u", "tests/test_golden.py")
Step "test_forge"             "py" @("-3", "-u", "tests/test_forge.py")
Step "test_builds"            "py" @("-3", "-u", "tests/test_builds.py")
Step "test_interactions"      "py" @("-3", "-u", "tests/test_interactions.py")
Step "test_provenance"        "py" @("-3", "-u", "tests/test_provenance.py")
Step "test_patch_history"     "py" @("-3", "-u", "tests/test_patch_history.py")
Step "test_js_parity"         "py" @("-3", "-u", "tests/test_js_parity.py")
Step "test_dashboard_layout"  "py" @("-3", "-u", "tests/test_dashboard_layout.py")
Step "test_cohort_families"   "py" @("-3", "-u", "tests/test_cohort_families.py")
Step "test_roles"             "py" @("-3", "-u", "tests/test_roles.py")
Step "test_validation_modes"  "py" @("-3", "-u", "tests/test_validation_modes.py")
Step "tier2_blindtest v4"     "py" @("-3", "-u", "tests/tier2_blindtest.py", "v4")
Step "test_loadout_codec"     "node" @("tests/test_loadout_codec.js")
Step "test_display_math"      "node" @("tests/test_display_math.js")
Step "test_live_party"        "node" @("tests/test_live_party.js")

# 3. the before/after report against the previous fold (HEAD)
Step "compare_fold"           "py" @("-3", "-u", "pipeline/compare_fold.py")

"=== fold complete $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8 -Append
Write-Host ""
Write-Host "All steps green. Review notes/findings/$stamp-fold-report.md, then commit"
Write-Host "the artifacts (git status) with the report; nothing has been committed."
