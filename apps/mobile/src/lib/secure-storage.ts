import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"

/**
 * Keychain (iOS) / Keystore (Android) backed storage for the session token.
 * The web build (used only for development previews) falls back to localStorage.
 */
export const secureStorage = {
  async get(key: string): Promise<string | null> {
    try {
      if (Platform.OS === "web") return window.localStorage.getItem(key)
      return await SecureStore.getItemAsync(key)
    } catch {
      return null
    }
  },
  async set(key: string, value: string): Promise<void> {
    if (Platform.OS === "web") window.localStorage.setItem(key, value)
    else await SecureStore.setItemAsync(key, value)
  },
  async remove(key: string): Promise<void> {
    try {
      if (Platform.OS === "web") window.localStorage.removeItem(key)
      else await SecureStore.deleteItemAsync(key)
    } catch {
      // Nothing to delete is fine.
    }
  },
}
