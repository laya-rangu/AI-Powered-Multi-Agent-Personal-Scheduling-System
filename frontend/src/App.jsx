import {
  lazy,
  startTransition,
  Suspense,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useState,
} from 'react'
import {
  AlertCircle,
  Bell,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  LayoutDashboard,
  LoaderCircle,
  RefreshCcw,
  Send,
  Sparkles,
  Target,
} from 'lucide-react'
import {
  createCalendarEvent,
  createGoal,
  createTask,
  generateDailyPlan,
  getAgentLogs,
  getApiBaseUrl,
  getCalendarEvents,
  getDashboardToday,
  getDailyPlan,
  getGoalProgress,
  getGoals,
  getNotifications,
  getTasks,
  runAssistantPlan,
  updateNotification,
  updateTask,
} from './api'

const GoalRadarContent = lazy(() => import('./components/GoalRadarContent.jsx'))
const PriorityMixContent = lazy(() => import('./components/PriorityMixContent.jsx'))

const priorityPalette = {
  urgent: '#d84f3f',
  high: '#f0953c',
  medium: '#2d7e7b',
  low: '#6e8e5b',
}

const priorityRank = {
  urgent: 0,
  high: 1,
  medium: 2,
  low: 3,
}

const statusTone = {
  success: 'text-emerald-700 bg-emerald-100',
  warning: 'text-amber-700 bg-amber-100',
  error: 'text-rose-700 bg-rose-100',
}

function formatDateInput(date) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')

  return `${year}-${month}-${day}`
}

function todayString() {
  return formatDateInput(new Date())
}

function buildGoalRange(goalType) {
  const start = new Date()
  const end = new Date(start)

  if (goalType === 'weekly') {
    end.setDate(start.getDate() + 7)
  } else if (goalType === 'monthly') {
    end.setMonth(start.getMonth() + 1)
  } else {
    end.setFullYear(start.getFullYear() + 1)
  }

  return {
    start_date: formatDateInput(start),
    end_date: formatDateInput(end),
  }
}

function sortTasksForDisplay(left, right) {
  if (left.status !== right.status) {
    return left.status === 'completed' ? 1 : -1
  }

  const priorityDifference =
    (priorityRank[left.priority] ?? Number.MAX_SAFE_INTEGER) -
    (priorityRank[right.priority] ?? Number.MAX_SAFE_INTEGER)

  if (priorityDifference !== 0) {
    return priorityDifference
  }

  return (right.created_at ?? '').localeCompare(left.created_at ?? '')
}

function sortNotificationsForDisplay(left, right) {
  if (left.status !== right.status) {
    return left.status === 'unread' ? -1 : 1
  }

  return (right.created_at ?? '').localeCompare(left.created_at ?? '')
}

function App() {
  const [selectedDate, setSelectedDate] = useState(todayString())
  const [dashboard, setDashboard] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [tasks, setTasks] = useState([])
  const [goals, setGoals] = useState([])
  const [goalProgress, setGoalProgress] = useState([])
  const [dailyPlan, setDailyPlan] = useState(null)
  const [agentLogs, setAgentLogs] = useState([])
  const [isRefreshing, setIsRefreshing] = useState(true)
  const [isRunningPlan, setIsRunningPlan] = useState(false)
  const [isSavingTask, setIsSavingTask] = useState(false)
  const [isSavingGoal, setIsSavingGoal] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [logFilter, setLogFilter] = useState('')
  const [assistantMessage, setAssistantMessage] = useState(
    'Finish resume updates in 1 hour, send a recruiter follow-up email in 30 minutes, and prepare interview answers for 90 minutes.',
  )
  const [quickTask, setQuickTask] = useState({
    title: '',
    estimated_minutes: 45,
    priority: 'medium',
  })
  const [quickGoal, setQuickGoal] = useState({
    title: '',
    goal_type: 'weekly',
    target_value: 5,
    unit: 'steps',
  })
  const deferredLogFilter = useDeferredValue(logFilter)

  async function refreshData(targetDate = selectedDate) {
    setIsRefreshing(true)
    setErrorMessage('')

    try {
      const results = await Promise.allSettled([
        getDashboardToday(),
        getNotifications(),
        getTasks(),
        getGoals(),
        getGoalProgress(),
        getDailyPlan(targetDate),
        getAgentLogs(targetDate),
      ])

      const [dashboardResult, notificationsResult, tasksResult, goalsResult, goalProgressResult, planResult, logsResult] = results

      const nextDashboard = dashboardResult.status === 'fulfilled' ? dashboardResult.value : null
      const nextNotifications = notificationsResult.status === 'fulfilled' ? notificationsResult.value : []
      const nextTasks = tasksResult.status === 'fulfilled' ? tasksResult.value : []
      const nextGoals = goalsResult.status === 'fulfilled' ? goalsResult.value : []
      const nextGoalProgress = goalProgressResult.status === 'fulfilled' ? goalProgressResult.value : []
      const nextPlan =
        planResult.status === 'fulfilled'
          ? planResult.value
          : null
      const nextLogs = logsResult.status === 'fulfilled' ? logsResult.value : []

      startTransition(() => {
        setDashboard(nextDashboard)
        setNotifications(nextNotifications)
        setTasks(nextTasks)
        setGoals(nextGoals)
        setGoalProgress(nextGoalProgress)
        setDailyPlan(nextPlan)
        setAgentLogs(nextLogs)
      })

      const firstUnexpectedFailure = [
        dashboardResult,
        notificationsResult,
        tasksResult,
        goalsResult,
        goalProgressResult,
        logsResult,
        ...(planResult.status === 'rejected' && planResult.reason?.status !== 404 ? [planResult] : []),
      ].find((result) => result.status === 'rejected')

      if (firstUnexpectedFailure?.status === 'rejected') {
        setErrorMessage(
          firstUnexpectedFailure.reason?.message ??
            'Some dashboard data could not be loaded. Check that the API is running.',
        )
      }
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsRefreshing(false)
    }
  }

  const refreshSelectedDate = useEffectEvent(() => {
    void refreshData(selectedDate)
  })

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      refreshSelectedDate()
    }, 0)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [selectedDate])

  async function handleAssistantPlan(event) {
    event.preventDefault()
    setIsRunningPlan(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const workflow = await runAssistantPlan(selectedDate, assistantMessage)
      startTransition(() => {
        setDailyPlan(workflow.daily_plan)
        setAgentLogs(workflow.workflow_steps.map((step, index) => ({
          id: `workflow-${index}`,
          agent_name: step.agent_name,
          action: step.node_name,
          output_summary: step.summary,
          status: step.status,
          created_at: selectedDate,
        })))
      })
      await refreshData(selectedDate)
      setSuccessMessage(
        workflow.used_fallback
          ? 'Daily plan generated with fallback extraction because Ollama was unavailable.'
          : 'Daily plan generated from your morning check-in.',
      )
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsRunningPlan(false)
    }
  }

  async function handleQuickTaskSubmit(event) {
    event.preventDefault()
    setIsSavingTask(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      await createTask({
        title: quickTask.title,
        estimated_minutes: Number(quickTask.estimated_minutes),
        priority: quickTask.priority,
      })
      setQuickTask({
        title: '',
        estimated_minutes: 45,
        priority: 'medium',
      })
      await refreshData(selectedDate)
      setSuccessMessage('Quick task added to your queue.')
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsSavingTask(false)
    }
  }

  async function handleGoalSubmit(event) {
    event.preventDefault()
    setIsSavingGoal(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const dateRange = buildGoalRange(quickGoal.goal_type)
      await createGoal({
        title: quickGoal.title,
        goal_type: quickGoal.goal_type,
        target_value: Number(quickGoal.target_value),
        current_value: 0,
        unit: quickGoal.unit,
        status: 'active',
        ...dateRange,
      })
      setQuickGoal({
        title: '',
        goal_type: 'weekly',
        target_value: 5,
        unit: 'steps',
      })
      await refreshData(selectedDate)
      setSuccessMessage('Goal created and added to progress tracking.')
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsSavingGoal(false)
    }
  }

  async function handleNotificationRead(notificationId) {
    setErrorMessage('')

    try {
      await updateNotification(notificationId, 'read')
      await refreshData(selectedDate)
    } catch (error) {
      setErrorMessage(error.message)
    }
  }

  async function handleTaskToggle(task) {
    setErrorMessage('')

    try {
      const nextStatus = task.status === 'completed' ? 'pending' : 'completed'
      await updateTask(task.id, { status: nextStatus })
      await refreshData(selectedDate)
    } catch (error) {
      setErrorMessage(error.message)
    }
  }

  async function handleGeneratePlanOnly() {
    setIsRunningPlan(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const plan = await generateDailyPlan(selectedDate)
      startTransition(() => {
        setDailyPlan(plan)
      })
      await refreshData(selectedDate)
      setSuccessMessage('Planner refreshed using your current tasks and calendar.')
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsRunningPlan(false)
    }
  }

  async function handleLoadDemoDay() {
    setIsRunningPlan(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const demoGoalTitle = 'Land three strong leads this week'
      const calendarEvents = await getCalendarEvents(selectedDate)
      const eventKeys = new Set(
        calendarEvents.map((event) => `${event.title}-${event.start_time}`),
      )

      if (!goals.some((goal) => goal.title === demoGoalTitle)) {
        await createGoal({
          title: demoGoalTitle,
          goal_type: 'weekly',
          target_value: 3,
          current_value: 0,
          unit: 'leads',
          status: 'active',
          ...buildGoalRange('weekly'),
        })
      }

      if (!eventKeys.has(`Lecture block-${selectedDate}T10:00:00`)) {
        await createCalendarEvent({
          title: 'Lecture block',
          start_time: `${selectedDate}T10:00:00`,
          end_time: `${selectedDate}T11:00:00`,
          source: 'mock',
        })
      }

      if (!eventKeys.has(`Gym reset-${selectedDate}T16:00:00`)) {
        await createCalendarEvent({
          title: 'Gym reset',
          start_time: `${selectedDate}T16:00:00`,
          end_time: `${selectedDate}T17:00:00`,
          source: 'mock',
        })
      }

      await runAssistantPlan(
        selectedDate,
        'Prepare interview answers for 90 minutes, finish two internship applications in 2 hours, and send a recruiter follow-up email in 30 minutes.',
      )
      await refreshData(selectedDate)
      setSuccessMessage('Demo day loaded or refreshed with seed data and a generated plan.')
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsRunningPlan(false)
    }
  }

  const activeNotifications = notifications.filter(
    (notification) => notification.status === 'unread',
  )
  const activeGoalCount = goals.filter((goal) => goal.status === 'active').length
  const sortedNotifications = [...notifications].sort(sortNotificationsForDisplay)
  const visibleTasks = [...tasks].sort(sortTasksForDisplay)

  const priorityChartData = Object.entries(
    tasks.reduce((accumulator, task) => {
      accumulator[task.priority] = (accumulator[task.priority] ?? 0) + 1
      return accumulator
    }, {}),
  ).map(([name, value]) => ({
    name,
    value,
    fill: priorityPalette[name] ?? '#2d7e7b',
  }))

  const filteredLogs = agentLogs.filter((log) => {
    if (!deferredLogFilter.trim()) {
      return true
    }

    const target = `${log.agent_name} ${log.output_summary}`.toLowerCase()
    return target.includes(deferredLogFilter.toLowerCase())
  })

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-[-8rem] top-[-8rem] h-72 w-72 rounded-full bg-[radial-gradient(circle,_rgba(217,118,74,0.35),_transparent_68%)] blur-2xl" />
        <div className="absolute right-[-7rem] top-20 h-80 w-80 rounded-full bg-[radial-gradient(circle,_rgba(46,126,123,0.22),_transparent_70%)] blur-2xl" />
        <div className="absolute bottom-[-10rem] left-1/3 h-96 w-96 rounded-full bg-[radial-gradient(circle,_rgba(126,167,98,0.18),_transparent_70%)] blur-3xl" />
      </div>

      <main className="relative mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="panel panel-glow animate-rise overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,var(--accent),var(--mint),var(--gold))]" />
          <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
            <div className="space-y-5">
              <div className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
                <Sparkles className="h-4 w-4 text-[var(--accent)]" />
                FocusFlow Command Deck
              </div>

              <div className="space-y-3">
                <h1 className="font-display text-4xl leading-none tracking-[-0.06em] text-[var(--ink)] sm:text-5xl lg:text-6xl">
                  Turn the morning brain-dump into a workable day.
                </h1>
                <p className="max-w-2xl text-base leading-7 text-[var(--muted)] sm:text-lg">
                  This dashboard runs the full FocusFlow pipeline: it converts your
                  check-in into tasks, reads your calendar blocks, builds a plan,
                  validates it, and keeps the reminder loop visible all day.
                </p>
              </div>

              <form className="space-y-4" onSubmit={handleAssistantPlan}>
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                  <label className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.26em] text-[var(--muted)]">
                      Morning Check-In
                    </span>
                    <textarea
                      value={assistantMessage}
                      onChange={(event) => setAssistantMessage(event.target.value)}
                      className="h-36 w-full rounded-[1.4rem] border border-[var(--line)] bg-white/90 px-4 py-4 text-sm leading-6 text-[var(--ink)] shadow-[inset_0_1px_0_rgba(255,255,255,0.75)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[rgba(217,118,74,0.18)]"
                      placeholder="List your tasks naturally, just like a real check-in."
                    />
                  </label>

                  <div className="space-y-3">
                    <label className="space-y-2">
                      <span className="text-xs font-semibold uppercase tracking-[0.26em] text-[var(--muted)]">
                        Plan Date
                      </span>
                      <input
                        type="date"
                        value={selectedDate}
                        onChange={(event) => setSelectedDate(event.target.value)}
                        className="field"
                      />
                    </label>

                    <button
                      type="submit"
                      disabled={isRunningPlan}
                      className="action-button action-primary"
                    >
                      {isRunningPlan ? (
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                      ) : (
                        <BrainCircuit className="h-4 w-4" />
                      )}
                      Run Full Assistant
                    </button>

                    <button
                      type="button"
                      onClick={handleGeneratePlanOnly}
                      disabled={isRunningPlan}
                      className="action-button action-secondary"
                    >
                      <RefreshCcw className="h-4 w-4" />
                      Regenerate Plan
                    </button>

                    <button
                      type="button"
                      onClick={handleLoadDemoDay}
                      disabled={isRunningPlan}
                      className="action-button action-ghost"
                    >
                      <Sparkles className="h-4 w-4" />
                      Load Demo Day
                    </button>
                  </div>
                </div>
              </form>

              <div className="flex flex-wrap gap-3">
                <StatusChip
                  icon={<Bell className="h-4 w-4" />}
                  label={`${activeNotifications.length} unread reminders`}
                />
                <StatusChip
                  icon={<LayoutDashboard className="h-4 w-4" />}
                  label={`${tasks.length} total tasks`}
                />
                <StatusChip
                  icon={<Target className="h-4 w-4" />}
                  label={`${goals.length} saved goals`}
                />
                <StatusChip
                  icon={<CalendarDays className="h-4 w-4" />}
                  label={`API at ${getApiBaseUrl()}`}
                />
              </div>
            </div>

            <aside className="grid gap-4 self-start">
              <MetricCard
                icon={<Bell className="h-5 w-5" />}
                title="Today's prompt"
                value={
                  dashboard?.morning_checkin_prompt
                    ? 'Waiting for check-in'
                    : 'Prompt cleared'
                }
                caption={
                  dashboard?.morning_checkin_prompt?.message ??
                  'Morning check-in already completed or marked read.'
                }
              />
              <MetricCard
                icon={<Clock3 className="h-5 w-5" />}
                title="Plan status"
                value={dailyPlan?.status ?? 'No plan yet'}
                caption={
                  dailyPlan?.validation_summary ??
                  'Run the assistant to create a schedule for the day.'
                }
              />
              <MetricCard
                icon={<BrainCircuit className="h-5 w-5" />}
                title="Workflow trace"
                value={`${agentLogs.length} entries`}
                caption="Daily, calendar, free-time, planning, and validation activity."
              />
            </aside>
          </div>
        </header>

        {(errorMessage || successMessage) && (
          <section className="grid gap-3 md:grid-cols-2">
            {errorMessage && (
              <div className="panel animate-rise border-rose-200 bg-rose-50/80 text-rose-700">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-5 w-5" />
                  <p className="text-sm font-medium">{errorMessage}</p>
                </div>
              </div>
            )}
            {successMessage && (
              <div className="panel animate-rise border-emerald-200 bg-emerald-50/80 text-emerald-700">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-5 w-5" />
                  <p className="text-sm font-medium">{successMessage}</p>
                </div>
              </div>
            )}
          </section>
        )}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatPanel
            label="Unread Notifications"
            value={dashboard?.unread_notifications_count ?? 0}
            detail="Morning reminders and other nudges"
            accent="var(--accent)"
          />
          <StatPanel
            label="Pending Tasks"
            value={dashboard?.pending_tasks_count ?? tasks.filter((task) => task.status !== 'completed').length}
            detail="Everything still waiting on your attention"
            accent="var(--teal)"
          />
          <StatPanel
            label="Plan Items Today"
            value={dailyPlan?.items?.length ?? dashboard?.today_plan?.scheduled_item_count ?? 0}
            detail="Scheduled work blocks and breaks"
            accent="var(--gold)"
          />
          <StatPanel
            label="Goals in Motion"
            value={activeGoalCount}
            detail="Weekly, monthly, and yearly targets"
            accent="var(--moss)"
          />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="grid gap-6">
            <Panel title="Today's Flow" eyebrow="Daily Plan" icon={<CalendarDays className="h-5 w-5" />}>
              {isRefreshing ? (
                <LoadingState label="Syncing plan, tasks, and reminders..." />
              ) : dailyPlan ? (
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-[0.9fr_0.1fr]">
                    <div className="space-y-3">
                      {dailyPlan.items.map((item, index) => (
                        <article
                          key={`${item.id}-${index}`}
                          className="timeline-card"
                          style={{ animationDelay: `${index * 60}ms` }}
                        >
                          <div className="timeline-marker" />
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="space-y-1">
                              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                                {item.item_type === 'break' ? 'Break' : 'Task block'}
                              </p>
                              <h3 className="font-display text-xl tracking-[-0.04em] text-[var(--ink)]">
                                {item.task_title ?? item.reason}
                              </h3>
                              <p className="text-sm text-[var(--muted)]">{item.reason}</p>
                            </div>
                            <div className="rounded-full bg-[var(--sand)] px-3 py-1 text-sm font-semibold text-[var(--ink)]">
                              {formatTime(item.start_time)} - {formatTime(item.end_time)}
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>

                    <div className="hidden md:flex justify-center">
                      <div className="h-full w-px bg-[linear-gradient(180deg,var(--accent),rgba(217,118,74,0.1))]" />
                    </div>
                  </div>

                  {dailyPlan.unscheduled_tasks.length > 0 && (
                    <div className="rounded-[1.4rem] border border-dashed border-[var(--line)] bg-[var(--sand)]/55 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                        Still waiting for time
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {dailyPlan.unscheduled_tasks.map((task) => (
                          <span
                            key={task.task_id}
                            className="rounded-full bg-white px-3 py-2 text-sm text-[var(--ink)] shadow-sm"
                          >
                            {task.title} - {task.remaining_minutes} min
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <EmptyState
                  title="No plan generated yet"
                  description="Run the assistant or refresh the planner after adding tasks."
                />
              )}
            </Panel>

            <div className="grid gap-6 lg:grid-cols-2">
              <Panel title="Task Board" eyebrow="Execution Queue" icon={<CheckCircle2 className="h-5 w-5" />}>
                <div className="space-y-3">
                  {tasks.length === 0 ? (
                    <EmptyState
                      title="No tasks yet"
                      description="Use the check-in composer or quick task form to start building your day."
                    />
                  ) : (
                    visibleTasks.slice(0, 8).map((task) => (
                      <button
                        key={task.id}
                        type="button"
                        onClick={() => handleTaskToggle(task)}
                        className="task-card"
                      >
                        <div className="flex items-start gap-3">
                          {task.status === 'completed' ? (
                            <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />
                          ) : (
                            <Circle className="mt-0.5 h-5 w-5 text-[var(--muted)]" />
                          )}
                          <div className="space-y-1 text-left">
                            <p className="font-semibold text-[var(--ink)]">{task.title}</p>
                            <p className="text-sm text-[var(--muted)]">
                              {task.estimated_minutes} min - {task.priority} - {task.status}
                            </p>
                          </div>
                        </div>
                        <span
                          className="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]"
                          style={{
                            backgroundColor: `${priorityPalette[task.priority] ?? '#2d7e7b'}1a`,
                            color: priorityPalette[task.priority] ?? '#2d7e7b',
                          }}
                        >
                          {task.priority}
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </Panel>

              <Panel title="Goal Radar" eyebrow="Progress" icon={<Target className="h-5 w-5" />}>
                {goalProgress.length === 0 ? (
                  <EmptyState
                    title="No goals on file"
                    description="Create a weekly, monthly, or yearly target to track momentum."
                  />
                ) : (
                  <Suspense fallback={<LoadingState label="Loading goal analytics..." />}>
                    <GoalRadarContent goalProgress={goalProgress} />
                  </Suspense>
                )}
              </Panel>
            </div>
          </div>

          <div className="grid gap-6 self-start">
            <Panel title="Quick Create" eyebrow="Manual Controls" icon={<Send className="h-5 w-5" />}>
              <div className="space-y-6">
                <form className="space-y-3" onSubmit={handleQuickTaskSubmit}>
                  <div className="flex items-center justify-between">
                    <h3 className="font-display text-xl text-[var(--ink)]">Task</h3>
                    {isSavingTask && <LoaderCircle className="h-4 w-4 animate-spin text-[var(--accent)]" />}
                  </div>
                  <input
                    value={quickTask.title}
                    onChange={(event) =>
                      setQuickTask((current) => ({ ...current, title: event.target.value }))
                    }
                    className="field"
                    placeholder="Outline a focused task"
                    required
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      type="number"
                      min="15"
                      max="480"
                      value={quickTask.estimated_minutes}
                      onChange={(event) =>
                        setQuickTask((current) => ({
                          ...current,
                          estimated_minutes: event.target.value,
                        }))
                      }
                      className="field"
                    />
                    <select
                      value={quickTask.priority}
                      onChange={(event) =>
                        setQuickTask((current) => ({ ...current, priority: event.target.value }))
                      }
                      className="field"
                    >
                      <option value="low">low</option>
                      <option value="medium">medium</option>
                      <option value="high">high</option>
                      <option value="urgent">urgent</option>
                    </select>
                  </div>
                  <button
                    type="submit"
                    disabled={isSavingTask}
                    className="action-button action-secondary w-full"
                  >
                    Add Quick Task
                  </button>
                </form>

                <form className="space-y-3 border-t border-[var(--line)] pt-5" onSubmit={handleGoalSubmit}>
                  <div className="flex items-center justify-between">
                    <h3 className="font-display text-xl text-[var(--ink)]">Goal</h3>
                    {isSavingGoal && <LoaderCircle className="h-4 w-4 animate-spin text-[var(--accent)]" />}
                  </div>
                  <input
                    value={quickGoal.title}
                    onChange={(event) =>
                      setQuickGoal((current) => ({ ...current, title: event.target.value }))
                    }
                    className="field"
                    placeholder="Weekly, monthly, or yearly target"
                    required
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <select
                      value={quickGoal.goal_type}
                      onChange={(event) =>
                        setQuickGoal((current) => ({ ...current, goal_type: event.target.value }))
                      }
                      className="field"
                    >
                      <option value="weekly">weekly</option>
                      <option value="monthly">monthly</option>
                      <option value="yearly">yearly</option>
                    </select>
                    <input
                      type="number"
                      min="1"
                      value={quickGoal.target_value}
                      onChange={(event) =>
                        setQuickGoal((current) => ({
                          ...current,
                          target_value: event.target.value,
                        }))
                      }
                      className="field"
                    />
                  </div>
                  <input
                    value={quickGoal.unit}
                    onChange={(event) =>
                      setQuickGoal((current) => ({ ...current, unit: event.target.value }))
                    }
                    className="field"
                    placeholder="applications, workouts, chapters"
                    required
                  />
                  <button
                    type="submit"
                    disabled={isSavingGoal}
                    className="action-button action-secondary w-full"
                  >
                    Create Goal
                  </button>
                </form>
              </div>
            </Panel>

            <Panel title="Notification Stack" eyebrow="Reminders" icon={<Bell className="h-5 w-5" />}>
              <div className="space-y-3">
                {notifications.length === 0 ? (
                  <EmptyState
                    title="No notifications"
                    description="Reminders and prompts will show up here."
                  />
                ) : (
                  sortedNotifications.map((notification) => (
                    <div key={notification.id} className="rounded-[1.2rem] border border-[var(--line)] bg-white/85 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                            {notification.notification_type.replace('_', ' ')}
                          </p>
                          <p className="font-medium text-[var(--ink)]">{notification.message}</p>
                        </div>
                        {notification.status === 'unread' ? (
                          <button
                            type="button"
                            onClick={() => handleNotificationRead(notification.id)}
                            className="rounded-full bg-[var(--ink)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white transition hover:bg-[var(--accent)]"
                          >
                            Mark read
                          </button>
                        ) : (
                          <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
                            read
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            <Panel title="Signal Mix" eyebrow="Task Priority" icon={<Sparkles className="h-5 w-5" />}>
              {priorityChartData.length === 0 ? (
                <EmptyState
                  title="No priority mix yet"
                  description="Once tasks are created, this chart will show how balanced the day is."
                />
              ) : (
                <Suspense fallback={<LoadingState label="Loading priority mix..." />}>
                  <PriorityMixContent priorityChartData={priorityChartData} />
                </Suspense>
              )}
            </Panel>
          </div>
        </section>

        <Panel title="Agent Log Feed" eyebrow="Why the plan looks like this" icon={<BrainCircuit className="h-5 w-5" />}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-[var(--muted)]">
              Filter the workflow trace to inspect planner retries, fallback extraction, or validation decisions.
            </div>
            <input
              value={logFilter}
              onChange={(event) => setLogFilter(event.target.value)}
              className="field max-w-xs"
              placeholder="Search logs..."
            />
          </div>

          {filteredLogs.length === 0 ? (
            <EmptyState
              title="No logs matched that filter"
              description="Run the assistant or clear the search box to see the full trace."
            />
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {filteredLogs.map((log, index) => (
                <article
                  key={`${log.id}-${index}`}
                  className="rounded-[1.35rem] border border-[var(--line)] bg-white/85 p-4 shadow-[0_18px_50px_rgba(60,54,48,0.08)]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                        {log.agent_name}
                      </p>
                      <p className="font-semibold text-[var(--ink)]">{log.action}</p>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusTone[log.status] ?? 'text-slate-700 bg-slate-100'}`}
                    >
                      {log.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
                    {log.output_summary}
                  </p>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </main>
    </div>
  )
}

function Panel({ title, eyebrow, icon, children }) {
  return (
    <section className="panel animate-rise">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-[var(--muted)]">
            {eyebrow}
          </p>
          <h2 className="mt-1 font-display text-3xl tracking-[-0.05em] text-[var(--ink)]">
            {title}
          </h2>
        </div>
        <div className="rounded-full bg-[var(--sand)] p-3 text-[var(--accent)]">
          {icon}
        </div>
      </div>
      {children}
    </section>
  )
}

function MetricCard({ icon, title, value, caption }) {
  return (
    <div className="rounded-[1.6rem] border border-[var(--line)] bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(246,238,228,0.82))] p-5 shadow-[0_18px_45px_rgba(60,54,48,0.08)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="rounded-full bg-[var(--sand)] p-3 text-[var(--accent)]">{icon}</div>
        <span className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
          live
        </span>
      </div>
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">{title}</p>
      <p className="mt-2 font-display text-2xl tracking-[-0.04em] text-[var(--ink)]">{value}</p>
      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{caption}</p>
    </div>
  )
}

function StatPanel({ label, value, detail, accent }) {
  return (
    <div className="panel animate-rise">
      <div
        className="mb-4 h-1.5 w-16 rounded-full"
        style={{ backgroundColor: accent }}
      />
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">{label}</p>
      <p className="mt-2 font-display text-4xl tracking-[-0.05em] text-[var(--ink)]">{value}</p>
      <p className="mt-2 text-sm text-[var(--muted)]">{detail}</p>
    </div>
  )
}

function StatusChip({ icon, label }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-white/80 px-3 py-2 text-sm font-medium text-[var(--ink)] shadow-[0_14px_28px_rgba(60,54,48,0.08)]">
      <span className="text-[var(--accent)]">{icon}</span>
      <span>{label}</span>
    </div>
  )
}

function LoadingState({ label }) {
  return (
    <div className="flex items-center gap-3 rounded-[1.2rem] border border-[var(--line)] bg-[var(--sand)]/50 px-4 py-5 text-sm text-[var(--muted)]">
      <LoaderCircle className="h-5 w-5 animate-spin text-[var(--accent)]" />
      {label}
    </div>
  )
}

function EmptyState({ title, description }) {
  return (
    <div className="rounded-[1.2rem] border border-dashed border-[var(--line)] bg-[var(--sand)]/35 px-4 py-8 text-center">
      <p className="font-display text-2xl tracking-[-0.04em] text-[var(--ink)]">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">{description}</p>
    </div>
  )
}

function formatTime(value) {
  return new Date(value).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default App
