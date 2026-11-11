# Jobs Tracker: mobile app (iOS and Android)

A native app built with Expo (React Native) that talks to the same FastAPI backend and database as the website. Every page is here: Today, Pipeline, Opportunity detail, Analytics, Daily log, Prep, Contacts & Resumes and Account.

## How it works

| Topic | Design |
|---|---|
| Navigation | Expo Router. Real platform tab bars (UITabBar / Material) for Today, Pipeline, Analytics, Log and More. |
| Data | The same TanStack Query hooks as the website (`src/api`), with optimistic updates for stage moves, follow-ups and prep. |
| Sign-in | Email and password, or Google. The backend returns an opaque session token (it never reaches a browser). It is kept in the Keychain (iOS) or Keystore (Android) via `expo-secure-store` and sent as `Authorization: Bearer`. |
| Why no cookies or CSRF | Those protect browser cookies. A bearer token is attached explicitly by the app, so another website cannot ride on it. The backend only returns a token when the request says `X-Client-Type: mobile`. |
| Sessions | Same server-side sessions as the web: 30-day lifetime, 7-day idle timeout, revoked on sign-out, password change and reset. |
| Pipeline | Swipe between stage columns. Tap **Move** (or long-press a card) to change stage. A phone-friendly replacement for drag and drop. |
| Forms | react-hook-form + zod, in bottom sheets that lift above the keyboard. |
| Charts | `react-native-svg`, with text summaries for screen readers. |
| Theme | Dark by default, with System and Light in Account. |
| Reminders | Optional (Account → Reminders). Local notifications at 9:00 AM on days you have follow-ups due, e.g. "2 follow-ups to do: Acme, Globex". Overdue ones roll into the next 9:00. They are scheduled on the phone from your pending follow-ups, refreshed whenever the app opens or follow-ups change, and cleared on sign-out. No push server or credentials needed. |
| Tablets | Content is a centred column (max 720pt) instead of stretching edge to edge. |

## Run it

```bash
cd apps/mobile
cp .env.example .env        # then edit it
npm install
npm start                   # opens the Expo dev server
```

Then press `i` (iOS simulator, needs Xcode) or `a` (Android emulator, needs Android Studio), or scan the QR code with **Expo Go** on a phone.

- **Physical phone:** `localhost` is the phone itself. Set `EXPO_PUBLIC_API_BASE_URL` to your computer's LAN address (`http://192.168.x.x:8000/api/v1`) and start the backend with `--host 0.0.0.0`, or point at your deployed API.
- **Google sign-in does not work in Expo Go.** It needs a development build (see below). Email sign-in and reminders work everywhere.

## Google sign-in setup

Phones use their own OAuth clients, not the web one.

1. In Google Cloud Console, **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - **iOS**: bundle ID `com.jobstracker.app`.
   - **Android**: package name `com.jobstracker.app` and the **SHA-1** of your signing key (`eas credentials` shows it).
2. Mobile `.env` / EAS environment:
   - `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`
   - `EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID`
3. **Backend** (Render) environment: `GOOGLE_EXTRA_CLIENT_IDS=<ios id>,<android id>`. The server checks that every Google token was issued to one of your clients and carries a server-issued nonce.

## Build and publish (EAS)

No local Xcode or Android Studio is required.

```bash
npm i -g eas-cli && eas login
eas init                                    # links the project to your Expo account
eas env:create --name EXPO_PUBLIC_API_BASE_URL --value https://<service>.onrender.com/api/v1 --environment production
# repeat for EXPO_PUBLIC_WEB_URL and the two Google client IDs

eas build --profile development --platform all   # dev client (needed for Google sign-in)
eas build --profile preview --platform android   # installable APK for testing
eas build --profile production --platform all    # store builds
eas submit --platform ios                         # App Store Connect (Apple Developer account, $99/yr)
eas submit --platform android                     # Google Play (one-off $25 fee)
```

Replace the bundle ID / package name in `app.config.ts` if `com.jobstracker.app` is not yours.

## Checks

```bash
npm run typecheck     # TypeScript (strict)
npm test              # Jest: API client, auth/session, password policy, components
npx expo export --platform ios --platform android   # proves both native bundles compile
```

## Known limits

- Email links (verify email, reset password) open the **website** in the browser; you then sign in in the app. Opening them straight in the app needs universal links, which need a domain association file.
- Reminders are scheduled while the app runs, so they only cover follow-ups the app has seen (two weeks ahead). Follow-ups added on the website appear after the app is next opened. True server push (works with the app closed for days) is not built.
- The app was verified by type-checking, unit tests, native bundle compilation and a web rendering of every screen. It has **not** been run on a physical device or simulator: check native tab bars, Google sign-in and haptics on real hardware before release.
