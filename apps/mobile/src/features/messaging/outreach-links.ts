/** Links that hand a finished draft to the user's own mail app, Gmail or LinkedIn.
 *
 * Nothing is sent from here. A `mailto:` link cannot attach a file or choose the sending
 * account; Gmail's compose link can choose the account (authuser). LinkedIn has no link that
 * pre-fills a message, so the text is copied and the person's profile (or a search) is opened.
 */
import { Linking } from "react-native";

/** Some mail clients drop a mailto: link longer than about 2,000 characters. */
export const MAILTO_SAFE_LENGTH = 1900;

export interface Draft {
  to: string | null;
  subject: string | null;
  body: string;
  from?: string | null;
}

const crlf = (text: string): string => text.replace(/\r?\n/g, "\r\n");
const enc = (text: string): string => encodeURIComponent(crlf(text));
const encAddress = (to: string): string =>
  encodeURIComponent(to).replace(/%40/g, "@");

export function mailtoLink({ to, subject, body }: Draft): string {
  const params = [
    subject ? `subject=${enc(subject)}` : "",
    `body=${enc(body)}`,
  ];
  return `mailto:${to ? encAddress(to) : ""}?${params.filter(Boolean).join("&")}`;
}

export function gmailLink({ to, subject, body, from }: Draft): string {
  const params = [
    "view=cm",
    "fs=1",
    to ? `to=${encAddress(to)}` : "",
    subject ? `su=${enc(subject)}` : "",
    `body=${enc(body)}`,
    from ? `authuser=${encodeURIComponent(from)}` : "",
  ];
  return `https://mail.google.com/mail/?${params.filter(Boolean).join("&")}`;
}

export function tooLongForMailto(draft: Draft): boolean {
  return mailtoLink(draft).length > MAILTO_SAFE_LENGTH;
}

function safeHttp(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:"
      ? parsed.href
      : null;
  } catch {
    return null;
  }
}

/** Where to open for a LinkedIn message: the person's profile, or a search for them. */
export function linkedinTarget(
  contact: { name: string; linkedin_url: string | null } | null,
  company: string,
): { url: string; isSearch: boolean } {
  const profile = safeHttp(contact?.linkedin_url);
  if (profile) return { url: profile, isSearch: false };
  const keywords = [contact?.name, company].filter(Boolean).join(" ");
  return {
    url: `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(keywords)}`,
    isSearch: true,
  };
}

/** Placeholders like [[something specific you discussed]] still waiting for the user. */
export function gapsIn(text: string): string[] {
  return [...text.matchAll(/\[\[([^[\]\n]+)\]\]/g)].map((m) => m[1] ?? "");
}

export function fillGap(text: string, label: string, value: string): string {
  return text.split(`[[${label}]]`).join(value);
}

/** Hand a link to the OS (a mail app for mailto:, the LinkedIn app for its links). */
export async function launch(url: string): Promise<boolean> {
  try {
    await Linking.openURL(url);
    return true;
  } catch {
    return false;
  }
}
