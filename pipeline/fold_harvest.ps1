# Weekly fold of the harvest cache into the dataset. ONE COMMAND for the
# in-session step the harvest task never does: re-derive the rosters
# artifact from the whole cache, run the documented chain in order,
# rebuild the dataset and the pages, run every gate, then write the
# before/after report to review before committing. A chain step's nonzero
# exit stops it (every later step reads that step's output). The gates all
# run whatever one returns: a fold that moves several pins lists every
# failing gate and its FAIL lines at the end, after the report (which
# shows what moved) and the backup, and exits 1. It NEVER commits - review
# notes/findings/<date>-fold-report.md, then commit.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File pipeline/fold_harvest.ps1
#
# Run it from PowerShell, not Git Bash: test_cohort_families decodes its
# child's stdout as UTF-8 and a Git-Bash-spawned console emits cp1252
# (CLAUDE.md "Environment traps"). Logs: pipeline/out/fetch_logs/fold-<date>.log.
# Cadence: weekly (the corpus grows ~350 battles a day; a daily fold is
# churn, a weekly one is a meaningful step - VALIDATION.md).
#
# The fold is OFFLINE: every step reads the cache or an artifact derived
# from it. The seal step copies the working rosters artifacts to the fold
# copies every later step reads and writes the fold's record
# (out/rosters_fold.json, committed); the artifacts themselves stay local
# (rosters_io, LOCAL FILES, ONE COMMITTED RECORD) and the last step copies
# them and the cache to the harvest backup (backup_harvest.py). The
# observed-evidence artifact (weapon_usage_v2.json: the prevalence strip,
# the killer-party cohorts and the observed families) is derived from the
# full fold copy (every population) by derive_usage.py, after
# build_dataset (weapon keys are filtered against the catalogue). Display
# only, never a scoring input.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
# a harvest pass ending mid-fold replaces the rosters artifact the fold's
# tables are derived from: refuse to start while one runs
. (Join-Path $root "pipeline\harvest_guard.ps1")
Assert-NoHarvest "fold"
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

# a gate: logged like a step, but a failure is recorded with the gate's
# FAIL lines and the fold goes on to the next gate
$failed = @()
function Gate($label, $exe, $argv) {
    $t0 = Get-Date
    "--- $label ($(Get-Date -Format s))" | Out-File $log -Encoding utf8 -Append
    $out = @(& $exe @argv 2>&1 | ForEach-Object { "$_" })
    $rc = $LASTEXITCODE
    $out | Out-File $log -Encoding utf8 -Append
    $secs = [int]((Get-Date) - $t0).TotalSeconds
    $last = [string]($out | Where-Object { $_ -match '\S' } | Select-Object -Last 1)
    "{0,-34} exit {1,-3} {2,5}s  {3}" -f $label, $rc, $secs, $last.Substring(0, [Math]::Min(90, $last.Length))
    if ($rc -ne 0) {
        $lines = @($out | Where-Object { $_ -match '^\s*\[?FAIL\b' } | ForEach-Object { $_.Trim() })
        if (-not $lines.Count) { $lines = @($last) }
        $script:failed += ,@($label, $rc, $lines)
    }
}

# 1. the chain, in the documented order (CLAUDE.md "After a harvest")
Step "rosters from cache"     "py" @("-3", "-u", "pipeline/sample_parties.py", "--pages", "0")
Step "seal the fold"          "py" @("-3", "-u", "pipeline/rosters_io.py", "seal")
Step "audit_style_rosters"    "py" @("-3", "-u", "pipeline/audit_style_rosters.py")
Step "derive_style_bands"     "py" @("-3", "-u", "pipeline/derive_style_bands.py")
Step "derive_portal_rows"     "py" @("-3", "-u", "pipeline/derive_portal_rows.py", "--apply")
Step "derive_party_styles"    "py" @("-3", "-u", "pipeline/derive_party_styles.py")
Step "derive_meta_prior"      "py" @("-3", "-u", "pipeline/derive_meta_prior.py")
Step "derive_portal_prior"    "py" @("-3", "-u", "pipeline/derive_portal_prior.py")
Step "derive_role_counts"     "py" @("-3", "-u", "pipeline/derive_role_counts.py")
Step "derive_skeletons"       "py" @("-3", "-u", "pipeline/derive_skeletons.py")
Step "build_dataset"          "py" @("-3", "-u", "pipeline/build_dataset.py")
Step "v4h holdout cases"      "py" @("-3", "-u", "tests/tier2_blindtest.py", "v4h", "--n", "500", "--export-cases", "pipeline/out/v4h_holdout.json")
Step "derive_usage"           "py" @("-3", "-u", "pipeline/derive_usage.py")
Step "build_cohort_families"  "py" @("-3", "-u", "pipeline/build_cohort_families.py")
Step "build_portal_stats"     "py" @("-3", "-u", "pipeline/build_portal_stats.py")
Step "dashboard build"        "py" @("-3", "-u", "dashboard/build.py")

# 2. every gate (CLAUDE.md "Tests"; exit 0 = pass)
Gate "test_golden"            "py" @("-3", "-u", "tests/test_golden.py")
Gate "test_forge"             "py" @("-3", "-u", "tests/test_forge.py")
Gate "test_builds"            "py" @("-3", "-u", "tests/test_builds.py")
Gate "test_interactions"      "py" @("-3", "-u", "tests/test_interactions.py")
Gate "test_provenance"        "py" @("-3", "-u", "tests/test_provenance.py")
Gate "test_patch_history"     "py" @("-3", "-u", "tests/test_patch_history.py")
Gate "test_js_parity"         "py" @("-3", "-u", "tests/test_js_parity.py")
Gate "test_dashboard_layout"  "py" @("-3", "-u", "tests/test_dashboard_layout.py")
Gate "test_cohort_families"   "py" @("-3", "-u", "tests/test_cohort_families.py")
Gate "test_usage_derive"      "py" @("-3", "-u", "tests/test_usage_derive.py")
Gate "test_meta_pairs"        "py" @("-3", "-u", "tests/test_meta_pairs.py")
Gate "test_style_bands_derive" "py" @("-3", "-u", "tests/test_style_bands_derive.py")
Gate "test_roles"             "py" @("-3", "-u", "tests/test_roles.py")
Gate "test_validation_modes"  "py" @("-3", "-u", "tests/test_validation_modes.py")
Gate "test_skeletons"         "py" @("-3", "-u", "tests/test_skeletons.py")
Gate "test_content_tag"       "py" @("-3", "-u", "tests/test_content_tag.py")
Gate "test_portal_stats"      "py" @("-3", "-u", "tests/test_portal_stats.py")
Gate "test_tone"              "py" @("-3", "-u", "tests/test_tone.py")
Gate "evidence_lint"          "py" @("-3", "-u", "pipeline/evidence_lint.py")
Gate "tier2_blindtest v4"     "py" @("-3", "-u", "tests/tier2_blindtest.py", "v4")
Gate "tier2_blindtest v4h gate" "py" @("-3", "-u", "tests/tier2_blindtest.py", "v4h", "--gate")
Gate "test_loadout_codec"     "node" @("tests/test_loadout_codec.js")
Gate "test_display_math"      "node" @("tests/test_display_math.js")
Gate "test_live_party"        "node" @("tests/test_live_party.js")
Gate "test_portal_page"       "node" @("tests/test_portal_page.js")

# 3. the before/after report against the previous fold (HEAD), a failed
# gate or not: it shows what moved
Step "compare_fold"           "py" @("-3", "-u", "pipeline/compare_fold.py")

# 4. the raw records off this disk (pipeline/harvest_backup.json names the folder)
Step "harvest backup"         "py" @("-3", "-u", "pipeline/backup_harvest.py")

if ($failed.Count) {
    "=== fold gates failed: $(($failed | ForEach-Object { $_[0] }) -join ', ') $(Get-Date -Format s) ===" |
        Out-File $log -Encoding utf8 -Append
    Write-Host ""
    Write-Host "$($failed.Count) gate(s) failed; every gate ran:"
    foreach ($f in $failed) {
        Write-Host "  $($f[0]) (exit $($f[1]))"
        foreach ($l in $f[2]) { Write-Host "      $($l.Substring(0, [Math]::Min(150, $l.Length)))" }
    }
    Write-Host "Review notes/findings/$stamp-fold-report.md (what moved) beside $log,"
    Write-Host "re-pin or fix each, rerun the failing gates. Nothing has been committed."
    exit 1
}
"=== fold complete $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8 -Append
Write-Host ""
Write-Host "All steps green. Review notes/findings/$stamp-fold-report.md, then commit"
Write-Host "the artifacts (git status) with the report, out/rosters_fold.json and"
Write-Host "out/kit_evidence.json among them; the rosters artifacts stay local (gitignored)."
Write-Host "Nothing has been committed."
