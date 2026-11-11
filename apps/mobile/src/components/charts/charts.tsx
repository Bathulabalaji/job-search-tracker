import { useState } from "react"
import { View, type LayoutChangeEvent } from "react-native"
import Svg, { Circle, G, Line, Polyline, Rect, Text as SvgText } from "react-native-svg"

import { useTheme } from "@/theme/theme"
import { Text } from "../ui/text"

/** Measures its own width so charts always fit the screen (phones, tablets, rotation). */
function useWidth(): [number, (e: LayoutChangeEvent) => void] {
  const [width, setWidth] = useState(0)
  return [width, (e) => setWidth(Math.floor(e.nativeEvent.layout.width))]
}

interface BarDatum {
  label: string
  value: number
}

/** Vertical bars, e.g. applications per day. Includes a text summary for screen readers. */
export function BarChart({ data, height = 150, summary }: { data: BarDatum[]; height?: number; summary: string }) {
  const { colors } = useTheme()
  const [width, onLayout] = useWidth()
  const max = Math.max(1, ...data.map((d) => d.value))
  const bottom = 22
  const top = 16
  const plot = height - bottom - top
  const slot = data.length ? width / data.length : 0
  const barWidth = Math.min(28, slot * 0.6)

  return (
    <View onLayout={onLayout} accessible accessibilityLabel={summary}>
      {width > 0 ? (
        <Svg width={width} height={height}>
          <Line x1={0} x2={width} y1={top + plot} y2={top + plot} stroke={colors.border} strokeWidth={1} />
          {data.map((d, i) => {
            const h = (d.value / max) * plot
            const x = slot * i + (slot - barWidth) / 2
            return (
              <G key={d.label}>
                <Rect
                  x={x}
                  y={top + plot - h}
                  width={barWidth}
                  height={Math.max(h, d.value > 0 ? 2 : 0)}
                  rx={5}
                  fill={d.value > 0 ? colors.primary : colors.surfaceRaised}
                />
                {d.value > 0 ? (
                  <SvgText x={x + barWidth / 2} y={top + plot - h - 4} fill={colors.muted} fontSize={10} textAnchor="middle">
                    {d.value}
                  </SvgText>
                ) : null}
                <SvgText x={x + barWidth / 2} y={height - 6} fill={colors.muted} fontSize={10} textAnchor="middle">
                  {d.label}
                </SvgText>
              </G>
            )
          })}
        </Svg>
      ) : null}
    </View>
  )
}

interface Series {
  name: string
  color: string
  values: number[]
}

export function LineChart({
  labels,
  series,
  height = 160,
  summary,
}: {
  labels: string[]
  series: Series[]
  height?: number
  summary: string
}) {
  const { colors } = useTheme()
  const [width, onLayout] = useWidth()
  const max = Math.max(1, ...series.flatMap((s) => s.values))
  const padX = 16
  const top = 12
  const bottom = 22
  const plot = height - top - bottom
  const stepX = labels.length > 1 ? (width - padX * 2) / (labels.length - 1) : 0
  const point = (v: number, i: number) => [padX + stepX * i, top + plot - (v / max) * plot] as const

  return (
    <View onLayout={onLayout} accessible accessibilityLabel={summary} style={{ gap: 8 }}>
      {width > 0 ? (
        <Svg width={width} height={height}>
          {[0, 0.5, 1].map((f) => (
            <Line key={f} x1={0} x2={width} y1={top + plot * f} y2={top + plot * f} stroke={colors.border} strokeWidth={1} strokeDasharray="3 4" />
          ))}
          {series.map((s) => (
            <G key={s.name}>
              <Polyline
                points={s.values.map((v, i) => point(v, i).join(",")).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth={2.5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {s.values.map((v, i) => {
                const [cx, cy] = point(v, i)
                return <Circle key={i} cx={cx} cy={cy} r={3.5} fill={s.color} />
              })}
            </G>
          ))}
          {labels.map((label, i) => (
            <SvgText key={`${label}-${i}`} x={padX + stepX * i} y={height - 6} fill={colors.muted} fontSize={10} textAnchor="middle">
              {label}
            </SvgText>
          ))}
        </Svg>
      ) : null}
      <View style={{ flexDirection: "row", gap: 14 }}>
        {series.map((s) => (
          <View key={s.name} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: s.color }} />
            <Text variant="caption" tone="muted">
              {s.name}
            </Text>
          </View>
        ))}
      </View>
    </View>
  )
}

interface HBarDatum {
  label: string
  value: number
  /** Shown at the end of the bar, e.g. "42%". */
  display: string
  detail?: string
}

/** Horizontal bars as plain views: crisp text at any size. Used for the funnel and sources. */
export function HorizontalBars({ data, max }: { data: HBarDatum[]; max?: number }) {
  const { colors } = useTheme()
  const top = max ?? Math.max(1, ...data.map((d) => d.value))
  return (
    <View style={{ gap: 12 }}>
      {data.map((d) => (
        <View
          key={d.label}
          style={{ gap: 5 }}
          accessible
          accessibilityLabel={`${d.label}: ${d.display}${d.detail ? `, ${d.detail}` : ""}`}
        >
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Text variant="small" style={{ fontWeight: "600" }}>
              {d.label}
            </Text>
            <Text variant="small" tone="muted">
              {d.display}
              {d.detail ? `  ·  ${d.detail}` : ""}
            </Text>
          </View>
          <View style={{ height: 10, borderRadius: 5, backgroundColor: colors.surfaceRaised, overflow: "hidden" }}>
            <View
              style={{
                width: `${Math.max(d.value > 0 ? 3 : 0, Math.min(100, (d.value / top) * 100))}%`,
                height: "100%",
                borderRadius: 5,
                backgroundColor: colors.primary,
              }}
            />
          </View>
        </View>
      ))}
    </View>
  )
}
