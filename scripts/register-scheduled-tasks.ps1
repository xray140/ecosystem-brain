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
$tasks = @(
    @{ Name = "EcosystemBrain-OllamaServe";    Bat = "start-ollama.bat";   Trigger = { New-ScheduledTaskTrigger -AtLogOn } }
    @{ Name = "EcosystemBrain-CatalogRefresh"; Bat = "refresh-catalog.bat"; Trigger = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 9am } }
    @{ Name = "EcosystemBrain-Maintenance";    Bat = "maintenance.bat";     Trigger = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am } }
)

if ($Unregister) {
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "  [removed] $($t.Name)"
    }
    Write-Host "done."
    return
}

Write-Host "registering ecosystem-brain scheduled tasks"
Write-Host "  repo: $repo`n"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew -StartWhenAvailable
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
