import { NativeTabs } from "expo-router/native-tabs"

import { useTheme } from "@/theme/theme"

/** Real platform tab bars: UITabBar on iOS (liquid glass where available), Material on Android. */
export default function TabsLayout() {
  const { colors } = useTheme()
  return (
    <NativeTabs
      backgroundColor={colors.surface}
      indicatorColor={colors.primarySoft}
      tintColor={colors.primary}
      iconColor={{ default: colors.muted, selected: colors.primary }}
      labelStyle={{ default: { color: colors.muted }, selected: { color: colors.primary } }}
    >
      <NativeTabs.Trigger name="today">
        <NativeTabs.Trigger.Label>Today</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: "calendar", selected: "calendar" }} md="today" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="pipeline">
        <NativeTabs.Trigger.Label>Pipeline</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="rectangle.split.3x1" md="view_kanban" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="analytics">
        <NativeTabs.Trigger.Label>Analytics</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="chart.bar" md="bar_chart" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="daily-log">
        <NativeTabs.Trigger.Label>Log</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="checklist" md="checklist" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="more">
        <NativeTabs.Trigger.Label>More</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="ellipsis.circle" md="more_horiz" />
      </NativeTabs.Trigger>
    </NativeTabs>
  )
}
