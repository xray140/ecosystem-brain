# Register all ecosystem-brain scheduled tasks (Windows Task Scheduler).
# Idempotent: -Force re-registers cleanly, so it is safe to run repeatedly.
# Path-derived: schedules whatever clone this script lives in. Run once:
#     powershell -ExecutionPolicy Bypass -File scripts\register-scheduled-tasks.ps1
# Remove them all with: scripts\register-scheduled-tasks.ps1 -Unregister

param([switch]$Unregister)

$ErrorActionPreference = "Stop"
$scripts = $PSScriptRoot
$repo = Split-Path -Parent $scripts

# name -> (batch file, trigger). Triggers built lazily so -Unregister needs none.
#
# OllamaServe was removed in v4.7.0 and Ollama itself in v4.8.0 - memory-search
# has one local embedder now and no server to keep up. The task stays in $retired
# below because removal is not the same as never having shipped it: Verdun10 was
# still carrying a failing registration three weeks later.
$tasks = @(
    @{ Name = "EcosystemBrain-CatalogRefresh"; Bat = "refresh-catalog.bat"; Trigger = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 9am } }
    @{ Name = "EcosystemBrain-Maintenance";    Bat = "maintenance.bat";     Trigger = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am } }
)
# Registered previously and no longer shipped - removed on the next run so the
# stale task does not linger and keep reporting red.
$retired = @("EcosystemBrain-OllamaServe")

if ($Unregister) {
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "  [removed] $($t.Name)"
    }
    foreach ($name in $retired) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host "done."
    return
}

Write-Host "registering ecosystem-brain scheduled tasks"
Write-Host "  repo: $repo`n"
# Drop tasks this script used to register. Without this a retired task keeps its
# registration, keeps failing, and keeps task_doctor red - the machine has no
# other way to learn the task is gone.
$stuck = @()
foreach ($name in $retired) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        # Announce the removal only once it is real. Unregistering a task that
        # was created in an elevated shell fails with "Access denied", and
        # SilentlyContinue makes that invisible: this printed [retired] while
        # the task stayed registered and task_doctor stayed red, which is the
        # one thing the retire list exists to prevent.
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Write-Host "  [STUCK] $name - still registered (needs an elevated PowerShell)"
            $stuck += $name
        } else {
            Write-Host "  [retired] $name"
        }
    }
}
# AllowStartIfOnBatteries / DontStopIfGoingOnBatteries are NOT the defaults:
# New-ScheduledTaskSettingsSet sets both battery guards to $true, so on a laptop
# every weekly run either refused to start or was killed mid-flight. That is
# exactly what happened here — the heartbeat and the catalog refresh were
# registered on 2026-07-15 and never once completed a scheduled run
# (SCHED_S_TASK_TERMINATED / STATUS_CONTROL_C_EXIT), while the tasks showed
# "Ready" the whole time. Ready is not the same as working.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
foreach ($t in $tasks) {
    $exe = Join-Path $scripts $t.Bat
    if (-not (Test-Path $exe)) { Write-Host "  [skip] $($t.Name) - missing $($t.Bat)"; continue }
    $action = New-ScheduledTaskAction -Execute $exe
    try {
        Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger (& $t.Trigger) `
            -Settings $settings -Force -ErrorAction Stop | Out-Null
        Write-Host "  [ok] $($t.Name)  ->  $($t.Bat)"
    } catch {
        # Overwriting a task created in an elevated shell needs elevation. If it
        # already exists, that's fine; otherwise surface the real failure.
        if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
            Write-Host "  [exists] $($t.Name) - already registered (run elevated to update)"
        } else {
            Write-Host "  [FAIL] $($t.Name): $($_.Exception.Message)  (try an elevated PowerShell)"
        }
    }
}
Write-Host "`ndone. View:  Get-ScheduledTask -TaskName 'EcosystemBrain-*'"
if ($stuck.Count -gt 0) {
    Write-Host "`n[!] $($stuck.Count) retired task(s) still registered: $($stuck -join ', ')"
    Write-Host "    Re-run this script from an elevated PowerShell to remove them."
    exit 1
}
