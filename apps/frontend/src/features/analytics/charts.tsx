import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { DailyPoint, FunnelStep, Metric, SourceResponse, WeekTrendPoint } from "@/api/types"
import { useIsMobile } from "@/hooks/use-mobile"
import { formatPercent, formatShortDate, formatWeekday, titleCase } from "@/lib/format"
import { AXIS_TICK, GRID_STROKE, SERIES_COLOR, tooltipFor } from "./chart-config"
import { TableView } from "./chart-parts"
import { TREND_METRICS } from "./trend-metrics"

const CHART_HEIGHT = 240

// ---- Applications per day ------------------------------------------------------------------

interface DayRow {
  date: string
  day: string
  applications: number
}

const dayTooltip = tooltipFor<DayRow>((row) => (
  <>
    <p className="text-muted-foreground">
      {row.day} {formatShortDate(row.date)}
    </p>
    <p>
      <span className="font-mono font-semibold">{row.applications}</span> applications
    </p>
  </>
))

export function ApplicationsPerDayChart({ daily }: { daily: DailyPoint[] }) {
  const rows: DayRow[] = daily.map((d) => ({
    date: d.date,
    day: formatWeekday(d.date),
    applications: d.applications,
  }))
  return (
    <div>
      <div style={{ height: CHART_HEIGHT }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke={GRID_STROKE} />
            <XAxis dataKey="day" tickLine={false} axisLine={false} tick={AXIS_TICK} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={AXIS_TICK} />
            <Tooltip content={dayTooltip} cursor={{ fill: "var(--muted)", opacity: 0.5 }} />
            <Bar
              dataKey="applications"
              fill={SERIES_COLOR}
              radius={[4, 4, 0, 0]}
              maxBarSize={28}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption="Applications per day this week"
        columns={["Day", "Applications"]}
        rows={rows.map((r) => [`${r.day} ${formatShortDate(r.date)}`, r.applications])}
      />
    </div>
  )
}

// ---- Weekly trend --------------------------------------------------------------------------

interface TrendRow {
  week_start: string
  label: string
  value: number
}

export function TrendChart({ trend, metric }: { trend: WeekTrendPoint[]; metric: Metric }) {
  const label = TREND_METRICS.find((m) => m.metric === metric)?.label ?? titleCase(metric)
  const rows: TrendRow[] = trend.map((t) => ({
    week_start: t.week_start,
    label: formatShortDate(t.week_start),
    value: t[metric],
  }))
  const tooltip = tooltipFor<TrendRow>((row) => (
    <>
      <p className="text-muted-foreground">Week of {formatShortDate(row.week_start)}</p>
      <p>
        <span className="font-mono font-semibold">{row.value}</span> {label.toLowerCase()}
      </p>
    </>
  ))
  return (
    <div>
      <div style={{ height: CHART_HEIGHT }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke={GRID_STROKE} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={AXIS_TICK} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={AXIS_TICK} />
            <Tooltip content={tooltip} cursor={{ stroke: "var(--border)" }} />
            <Line
              type="monotone"
              dataKey="value"
              stroke={SERIES_COLOR}
              strokeWidth={2}
              dot={{ r: 4, fill: SERIES_COLOR, stroke: "var(--card)", strokeWidth: 2 }}
              activeDot={{ r: 5, fill: SERIES_COLOR, stroke: "var(--card)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption={`${label} per week, last ${rows.length} weeks`}
        columns={["Week of", label]}
        rows={rows.map((r) => [formatShortDate(r.week_start), r.value])}
      />
    </div>
  )
}

// ---- Funnel --------------------------------------------------------------------------------

interface FunnelRow extends FunnelStep {
  text: string
}

export function FunnelChart({ funnel }: { funnel: FunnelStep[] }) {
  const compact = useIsMobile()
  const rows: FunnelRow[] = funnel.map((step) => ({
    ...step,
    text:
      step.conversion_from_previous === null
        ? String(step.count)
        : `${step.count} · ${formatPercent(step.conversion_from_previous)}`,
  }))
  const tooltip = tooltipFor<FunnelRow>((row) => (
    <>
      <p className="font-medium">{row.label}</p>
      <p>
        <span className="font-mono font-semibold">{row.count}</span> opportunities reached this step
      </p>
      {row.conversion_from_previous !== null ? (
        <p className="text-muted-foreground">
          {formatPercent(row.conversion_from_previous)} of the previous step,{" "}
          {formatPercent(row.conversion_from_start)} of all
        </p>
      ) : null}
    </>
  ))
  return (
    <div>
      <div style={{ height: CHART_HEIGHT }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: compact ? 52 : 64, bottom: 4, left: 0 }}
            barCategoryGap={8}
          >
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="label"
              width={compact ? 68 : 84}
              tickLine={false}
              axisLine={false}
              tick={AXIS_TICK}
            />
            <Tooltip content={tooltip} cursor={{ fill: "var(--muted)", opacity: 0.5 }} />
            <Bar
              dataKey="count"
              fill={SERIES_COLOR}
              radius={[0, 4, 4, 0]}
              maxBarSize={22}
              minPointSize={2}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="text"
                position="right"
                fill="var(--foreground)"
                fontSize={12}
                className="font-mono"
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption="Funnel: opportunities that reached each step"
        columns={["Step", "Reached", "% of previous step", "% of all"]}
        rows={funnel.map((s) => [
          s.label,
          s.count,
          formatPercent(s.conversion_from_previous),
          formatPercent(s.conversion_from_start),
        ])}
      />
    </div>
  )
}

// ---- Response rate by source ---------------------------------------------------------------

interface SourceRow extends SourceResponse {
  name: string
  percent: number
  text: string
}

export function ResponseBySourceChart({ sources }: { sources: SourceResponse[] }) {
  const compact = useIsMobile()
  const rows: SourceRow[] = sources
    .filter((s) => s.applied > 0)
    .map((s) => ({
      ...s,
      name: titleCase(s.source),
      percent: Math.round((s.response_rate ?? 0) * 100),
      text: `${formatPercent(s.response_rate)} (${s.responded}/${s.applied})`,
    }))
    .sort((a, b) => b.percent - a.percent)
  const tooltip = tooltipFor<SourceRow>((row) => (
    <>
      <p className="font-medium">{row.name}</p>
      <p>
        <span className="font-mono font-semibold">{row.responded}</span> of{" "}
        <span className="font-mono font-semibold">{row.applied}</span> applications got a reply
      </p>
    </>
  ))
  return (
    <div>
      <div style={{ height: Math.max(120, rows.length * 44 + 16) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: compact ? 84 : 96, bottom: 4, left: 0 }}
            barCategoryGap={10}
          >
            <XAxis type="number" hide domain={[0, 100]} />
            <YAxis
              type="category"
              dataKey="name"
              width={compact ? 68 : 84}
              tickLine={false}
              axisLine={false}
              tick={AXIS_TICK}
            />
            <Tooltip content={tooltip} cursor={{ fill: "var(--muted)", opacity: 0.5 }} />
            <Bar
              dataKey="percent"
              fill={SERIES_COLOR}
              radius={[0, 4, 4, 0]}
              maxBarSize={22}
              minPointSize={2}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="text"
                position="right"
                fill="var(--foreground)"
                fontSize={12}
                className="font-mono"
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption="Response rate by source"
        columns={["Source", "Applied", "Replied", "Response rate"]}
        rows={rows.map((r) => [r.name, r.applied, r.responded, formatPercent(r.response_rate)])}
      />
    </div>
  )
}
