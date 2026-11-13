import { useRouter } from "expo-router";
import { Pressable, View } from "react-native";

import { Card } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { Screen, ScreenHeader } from "@/components/ui/screen";
import { Text } from "@/components/ui/text";
import { useUser } from "@/features/auth/auth-context";
import { haptics } from "@/lib/haptics";
import { useTheme } from "@/theme/theme";

type Href = "/assistant" | "/prep" | "/contacts" | "/account";

const ITEMS: { href: Href; icon: IconName; title: string; subtitle: string }[] =
  [
    {
      href: "/assistant",
      icon: "sparkles-outline",
      title: "Assistant",
      subtitle: "Ask about your pipeline, follow-ups and progress",
    },
    {
      href: "/prep",
      icon: "book-outline",
      title: "Interview prep",
      subtitle: "Topics, confidence and progress",
    },
    {
      href: "/contacts",
      icon: "people-outline",
      title: "Contacts & Resumes",
      subtitle: "Recruiters, managers and your resume versions",
    },
    {
      href: "/account",
      icon: "person-circle-outline",
      title: "Account",
      subtitle: "Profile, password, theme and sign out",
    },
  ];

export default function MoreScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const user = useUser();
  return (
    <Screen>
      <ScreenHeader title="More" subtitle={user.email} />
      <View style={{ gap: 10 }}>
        {ITEMS.map((item) => (
          <Pressable
            key={item.href}
            accessibilityRole="button"
            accessibilityLabel={`${item.title}. ${item.subtitle}`}
            onPress={() => {
              haptics.tap();
              router.push(item.href);
            }}
          >
            {({ pressed }) => (
              <Card
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 14,
                  opacity: pressed ? 0.8 : 1,
                }}
              >
                <View
                  style={{
                    width: 42,
                    height: 42,
                    borderRadius: 12,
                    backgroundColor: colors.primarySoft,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icon name={item.icon} size={22} color="primary" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "600" }}>{item.title}</Text>
                  <Text variant="small" tone="muted">
                    {item.subtitle}
                  </Text>
                </View>
                <Icon name="chevron-forward" size={18} color="muted" />
              </Card>
            )}
          </Pressable>
        ))}
      </View>
    </Screen>
  );
}
