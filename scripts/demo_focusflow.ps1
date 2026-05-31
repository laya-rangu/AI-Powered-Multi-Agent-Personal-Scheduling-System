param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$DemoDate = (Get-Date -Format "yyyy-MM-dd")
)

$ErrorActionPreference = "Stop"

function Invoke-FocusFlowApi {
    param(
        [ValidateSet("GET", "POST", "PATCH", "DELETE")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $uri = "{0}{1}" -f $ApiBaseUrl.TrimEnd("/"), $Path
    $requestArgs = @{
        Method      = $Method
        Uri         = $uri
        ErrorAction = "Stop"
    }

    if ($null -ne $Body) {
        $requestArgs["ContentType"] = "application/json"
        $requestArgs["Body"] = ($Body | ConvertTo-Json -Depth 8)
    }

    try {
        Invoke-RestMethod @requestArgs
    }
    catch {
        $response = $_.Exception.Response
        if ($null -ne $response) {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            $message = $reader.ReadToEnd()
            throw "API request failed for $Method $uri`n$message"
        }

        throw
    }
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "== $Title ==" -ForegroundColor Cyan
}

function As-List {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }

    $items = @($Value)
    if ($items.Count -eq 1 -and $items[0] -is [System.Array]) {
        return @($items[0])
    }

    return $items
}

$demoPrefix = "FocusFlow demo"
$goalTitle = "$demoPrefix weekly momentum"
$goalTaskTitle = "$demoPrefix completed application"
$calendarTitles = @(
    "$demoPrefix morning class block",
    "$demoPrefix networking call"
)
Write-Section "Checking API"
$root = Invoke-FocusFlowApi -Method GET -Path "/"
Write-Host ("Connected to {0} v{1}" -f $root.name, $root.version) -ForegroundColor Green

Write-Section "Cleaning old demo tasks"
$tasks = As-List (Invoke-FocusFlowApi -Method GET -Path "/tasks")
$tasksToDelete = @(
    $tasks | Where-Object {
        $_.title -eq $goalTaskTitle -or
        $_.title -like "$demoPrefix deep work block*" -or
        $_.title -like "$demoPrefix recruiter follow-up*" -or
        $_.title -like "$demoPrefix interview prep*"
    }
)

foreach ($task in $tasksToDelete) {
    Invoke-FocusFlowApi -Method DELETE -Path "/tasks/$($task.id)" | Out-Null
}
Write-Host ("Removed {0} old demo task(s)." -f $tasksToDelete.Count)

Write-Section "Cleaning old demo goals"
$goals = As-List (Invoke-FocusFlowApi -Method GET -Path "/goals")
$goalsToDelete = @($goals | Where-Object { $_.title -eq $goalTitle })
foreach ($goal in $goalsToDelete) {
    Invoke-FocusFlowApi -Method DELETE -Path "/goals/$($goal.id)" | Out-Null
}
Write-Host ("Removed {0} old demo goal(s)." -f $goalsToDelete.Count)

Write-Section "Creating a goal and showing progress tracking"
$startDate = [datetime]::Parse($DemoDate)
$endDate = $startDate.AddDays(7).ToString("yyyy-MM-dd")
$goal = Invoke-FocusFlowApi -Method POST -Path "/goals" -Body @{
    title        = $goalTitle
    goal_type    = "weekly"
    target_value = 3
    current_value = 0
    unit         = "applications"
    start_date   = $DemoDate
    end_date     = $endDate
    status       = "active"
}

$goalTask = Invoke-FocusFlowApi -Method POST -Path "/tasks" -Body @{
    title               = $goalTaskTitle
    priority            = "high"
    estimated_minutes   = 45
    goal_id             = $goal.id
    goal_progress_value = 1
}

Invoke-FocusFlowApi -Method PATCH -Path "/tasks/$($goalTask.id)" -Body @{
    status = "completed"
} | Out-Null

$goalProgress = As-List (Invoke-FocusFlowApi -Method GET -Path "/goals/progress")
$demoGoalProgress = $goalProgress | Where-Object { $_.id -eq $goal.id } | Select-Object -First 1
Write-Host ("Goal progress: {0}/{1} {2} ({3}%)" -f $demoGoalProgress.current_value, $demoGoalProgress.target_value, $demoGoalProgress.unit, $demoGoalProgress.progress_percentage) -ForegroundColor Green

Write-Section "Creating calendar blocks"
$existingEvents = As-List (Invoke-FocusFlowApi -Method GET -Path "/calendar/events?date=$DemoDate")
$eventsToCreate = @(
    @{
        title      = $calendarTitles[0]
        start_time = "$DemoDate" + "T10:00:00"
        end_time   = "$DemoDate" + "T11:00:00"
        source     = "mock"
    },
    @{
        title      = $calendarTitles[1]
        start_time = "$DemoDate" + "T15:30:00"
        end_time   = "$DemoDate" + "T16:00:00"
        source     = "mock"
    }
)

$createdEvents = 0
foreach ($event in $eventsToCreate) {
    $alreadyExists = $existingEvents | Where-Object {
        $_.title -eq $event.title -and $_.start_time -eq $event.start_time
    }
    if (-not $alreadyExists) {
        Invoke-FocusFlowApi -Method POST -Path "/calendar/events" -Body $event | Out-Null
        $createdEvents += 1
    }
}
Write-Host ("Calendar demo blocks created: {0}" -f $createdEvents) -ForegroundColor Green

Write-Section "Running the full assistant workflow"
$assistantMessage = "$demoPrefix deep work block in 90 minutes; $demoPrefix recruiter follow-up in 30 minutes; $demoPrefix interview prep in 60 minutes."
$assistantResult = Invoke-FocusFlowApi -Method POST -Path "/assistant/daily-plan" -Body @{
    date    = $DemoDate
    message = $assistantMessage
}

Write-Host ("Plan status: {0}" -f $assistantResult.daily_plan.status) -ForegroundColor Green
Write-Host ("Task extraction source: {0}" -f $assistantResult.source)
Write-Host ("Fallback used: {0}" -f $assistantResult.used_fallback)

Write-Section "Plan summary"
foreach ($item in $assistantResult.daily_plan.items) {
    $label = if ($null -ne $item.task_title) { $item.task_title } else { $item.reason }
    Write-Host ("[{0}-{1}] {2} ({3} min)" -f $item.start_time.Substring(11, 5), $item.end_time.Substring(11, 5), $label, $item.duration_minutes)
}

if ($assistantResult.daily_plan.unscheduled_tasks.Count -gt 0) {
    Write-Host ""
    Write-Host "Unscheduled tasks:" -ForegroundColor Yellow
    foreach ($task in $assistantResult.daily_plan.unscheduled_tasks) {
        Write-Host ("- {0}: {1} min remaining" -f $task.title, $task.remaining_minutes)
    }
}

Write-Section "Dashboard and logs"
$dashboard = Invoke-FocusFlowApi -Method GET -Path "/dashboard/today"
$logs = As-List (Invoke-FocusFlowApi -Method GET -Path "/agent-logs?date=$DemoDate")

Write-Host ("Unread notifications: {0}" -f $dashboard.unread_notifications_count)
Write-Host ("Pending tasks: {0}" -f $dashboard.pending_tasks_count)
Write-Host ("Agent log entries for ${DemoDate}: {0}" -f $logs.Count)

Write-Host ""
Write-Host "Recent agent logs:" -ForegroundColor Cyan
foreach ($log in $logs | Select-Object -First 5) {
    Write-Host ("- [{0}] {1}: {2}" -f $log.status, $log.agent_name, $log.output_summary)
}

Write-Host ""
Write-Host "Demo complete." -ForegroundColor Green
Write-Host ("Frontend:  http://127.0.0.1:5173")
Write-Host ("Swagger:   {0}/docs" -f $ApiBaseUrl.TrimEnd("/"))
Write-Host ("Plan date: {0}" -f $DemoDate)
