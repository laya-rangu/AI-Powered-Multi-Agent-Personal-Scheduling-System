import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

function PriorityMixContent({ priorityChartData }) {
  return (
    <div className="grid gap-4 sm:grid-cols-[0.95fr_1.05fr]">
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={priorityChartData}
              dataKey="value"
              nameKey="name"
              innerRadius={52}
              outerRadius={88}
              paddingAngle={4}
            >
              {priorityChartData.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                borderRadius: '16px',
                borderColor: '#e5d8c8',
                boxShadow: '0 18px 40px rgba(60, 54, 48, 0.12)',
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-3">
        {priorityChartData.map((entry) => (
          <div key={entry.name} className="flex items-center justify-between rounded-[1rem] bg-[var(--sand)]/60 px-3 py-3">
            <div className="flex items-center gap-3">
              <span
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: entry.fill }}
              />
              <span className="font-medium capitalize text-[var(--ink)]">{entry.name}</span>
            </div>
            <span className="font-semibold text-[var(--muted)]">{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default PriorityMixContent
