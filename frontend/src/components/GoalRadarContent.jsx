import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

function GoalRadarContent({ goalProgress }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={goalProgress}>
            <CartesianGrid strokeDasharray="4 8" stroke="rgba(60, 54, 48, 0.08)" />
            <XAxis dataKey="title" tick={{ fontSize: 12 }} stroke="#7a6f67" />
            <YAxis tick={{ fontSize: 12 }} stroke="#7a6f67" />
            <Tooltip
              contentStyle={{
                borderRadius: '16px',
                borderColor: '#e5d8c8',
                boxShadow: '0 18px 40px rgba(60, 54, 48, 0.12)',
              }}
            />
            <Bar dataKey="progress_percentage" radius={[10, 10, 0, 0]} fill="#d9764a" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-3">
        {goalProgress.map((goal) => (
          <div key={goal.id} className="rounded-[1.2rem] border border-[var(--line)] bg-white/80 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-[var(--ink)]">{goal.title}</p>
                <p className="text-sm text-[var(--muted)]">
                  {goal.current_value}/{goal.target_value} {goal.unit}
                </p>
              </div>
              <span className="rounded-full bg-[var(--sand)] px-3 py-1 text-sm font-semibold text-[var(--ink)]">
                {goal.progress_percentage}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default GoalRadarContent
