import type { ConfigContext, ExpoConfig } from "expo/config"

/**
 * Google sign-in on a phone uses OAuth client IDs of type "iOS" and "Android" (not the web one).
 * The iOS client needs its reversed ID registered as a URL scheme, so the config is dynamic.
 */
const IOS_BUNDLE_ID = "com.jobstracker.app"
const ANDROID_PACKAGE = "com.jobstracker.app"

const googleIosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? ""
const reversedIosScheme = googleIosClientId
  ? `com.googleusercontent.apps.${googleIosClientId.replace(".apps.googleusercontent.com", "")}`
  : null

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: "Jobs Tracker",
  slug: "jobs-tracker",
  version: "1.0.0",
  orientation: "portrait",
  icon: "./assets/images/icon.png",
  userInterfaceStyle: "automatic",
  scheme: ["jobstracker", ANDROID_PACKAGE, ...(reversedIosScheme ? [reversedIosScheme] : [])],
  ios: {
    bundleIdentifier: IOS_BUNDLE_ID,
    supportsTablet: true,
    infoPlist: { ITSAppUsesNonExemptEncryption: false },
  },
  android: {
    package: ANDROID_PACKAGE,
    adaptiveIcon: {
      backgroundColor: "#4F46E5",
      foregroundImage: "./assets/images/android-icon-foreground.png",
      monochromeImage: "./assets/images/android-icon-monochrome.png",
    },
    predictiveBackGestureEnabled: true,
  },
  web: { bundler: "metro", output: "single", favicon: "./assets/images/favicon.png" },
  plugins: [
    "expo-router",
    "expo-secure-store",
    "expo-web-browser",
    ["expo-notifications", { color: "#6D70F5" }],
    [
      "expo-splash-screen",
      {
        backgroundColor: "#060A18",
        image: "./assets/images/splash-icon.png",
        imageWidth: 140,
      },
    ],
  ],
  experiments: { typedRoutes: true, reactCompiler: true },
  extra: {
    ...config.extra,
    eas: {
      projectId: "175d717e-e802-4f25-a624-ea413d893ba8",
    },
  },
})
