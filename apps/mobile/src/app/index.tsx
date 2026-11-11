import { Redirect } from "expo-router"

import { useAuth } from "@/features/auth/auth-context"

/** "/" has no screen of its own: send people to wherever they belong. */
export default function Index() {
  const { state } = useAuth()
  return <Redirect href={state.status === "authenticated" ? "/today" : "/login"} />
}
