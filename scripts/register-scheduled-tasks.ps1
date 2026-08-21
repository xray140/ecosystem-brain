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
# OllamaServe was removed in v4.7.0. Ollama is optional: memory-search uses it
# when it happens to be running and falls back to the offline embedder when not,
# so a logon task existed only to keep a server up for a capability that already
# degrades gracefully. It cost more than it returned - it sat red for weeks
# pointing at D:\ecosystem-tools\start-ollama.bat, a path the script had long
# since left, and that red was most of the reason Ollama looked like a problem.
# Start it yourself if you want embeddings: `ollama serve`.
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
foreach ($name in $retired) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "  [retired] $name"
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
