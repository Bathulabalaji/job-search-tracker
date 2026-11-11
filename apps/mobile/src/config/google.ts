import { Platform } from "react-native"

import { GOOGLE_ANDROID_CLIENT_ID, GOOGLE_IOS_CLIENT_ID } from "./env"

export const ANDROID_PACKAGE = "com.jobstracker.app"

/** iOS clients redirect to their reversed client ID; Android clients to the package name. */
export function googleRedirectUri(): string | undefined {
  if (Platform.OS === "ios" && GOOGLE_IOS_CLIENT_ID) {
    const id = GOOGLE_IOS_CLIENT_ID.replace(".apps.googleusercontent.com", "")
    return `com.googleusercontent.apps.${id}:/oauthredirect`
  }
  if (Platform.OS === "android" && GOOGLE_ANDROID_CLIENT_ID) {
    return `${ANDROID_PACKAGE}:/oauthredirect`
  }
  return undefined
}
