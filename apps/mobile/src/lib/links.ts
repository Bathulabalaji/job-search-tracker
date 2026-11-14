import { Linking } from "react-native";

import { toast } from "@/lib/toast-bus";

/** A web address typed without https:// ("linkedin.com/in/riya", "www.acme.com/jobs/1"). */
const BARE_ADDRESS =
  /^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?::\d+)?(?:[/?#]\S*)?$/i;

/**
 * The address as an http(s) link, or null when it is not one.
 *
 * Adds https:// when it was left off, and refuses every other scheme (javascript:, tel:, file:).
 */
export function normalizeWebUrl(
  value: string | null | undefined,
): string | null {
  const text = (value ?? "").trim();
  if (!text || /\s/.test(text)) return null;
  if (/^https?:\/\//i.test(text)) {
    try {
      const url = new URL(text);
      return url.hostname.includes(".") || url.hostname === "localhost"
        ? url.href
        : null;
    } catch {
      return null;
    }
  }
  if (/^[a-z][a-z0-9+.-]*:/i.test(text) && !/^[a-z0-9.-]+:\d+/i.test(text))
    return null;
  return BARE_ADDRESS.test(text) ? normalizeWebUrl(`https://${text}`) : null;
}

/** For a form field: empty is fine, anything else must be a web address. */
export function isOptionalWebUrl(value: string): boolean {
  return value.trim() === "" || normalizeWebUrl(value) !== null;
}

export const WEB_URL_HINT =
  "Enter a web address, like linkedin.com/in/your-name";

/** Open a saved link, telling the user when it is not one the phone can open. */
export async function openWebLink(
  url: string | null | undefined,
): Promise<void> {
  const safe = normalizeWebUrl(url);
  if (!safe) {
    toast.error("This link can't be opened", "Edit it and check the address.");
    return;
  }
  try {
    await Linking.openURL(safe);
  } catch {
    toast.error("Couldn't open the link", safe);
  }
}
