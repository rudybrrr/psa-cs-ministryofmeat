const stats = [
  { label: "Launches tracked", value: "—" },
  { label: "Avg. time to first page", value: "—" },
  { label: "Checklist completion rate", value: "—" },
]

export function StatsSection() {
  return (
    <section className="border-b border-border bg-card/50" aria-label="Product metrics">
      <dl className="mx-auto grid max-w-5xl grid-cols-1 gap-6 px-4 py-10 sm:grid-cols-3 sm:px-6">
        {stats.map((stat) => (
          <div key={stat.label}>
            <dt className="text-sm text-muted-foreground">{stat.label}</dt>
            <dd className="mt-1 text-3xl font-bold tracking-tight text-muted-foreground">
              {stat.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
