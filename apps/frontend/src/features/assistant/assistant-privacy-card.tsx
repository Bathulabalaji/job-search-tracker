import { Sparkles } from "lucide-react"
import { toast } from "sonner"

import { useChatConfig, useQuotaUsage, useSetAssistantOptOut } from "@/api/chat"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"

/** What the assistant sends where, today's allowances, and the switch that turns it all off. */
export function AssistantPrivacyCard() {
  const config = useChatConfig()
  const usage = useQuotaUsage()
  const setOptOut = useSetAssistantOptOut()
  // Hidden on servers without an assistant: nothing to explain or switch.
  if (!config.data || (!config.data.enabled && !config.data.assistant_opt_out)) return null
  const off = config.data.assistant_opt_out === true

  const toggle = () =>
    setOptOut.mutate(!off, {
      onSuccess: () => toast.success(off ? "AI assistant turned on" : "AI assistant turned off"),
      onError: () => toast.error("Could not change that setting. Try again."),
    })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" aria-hidden />
          AI assistant
        </CardTitle>
        <CardDescription>
          When it is on, your questions, the parts of your pipeline it looks up, and the redacted
          text of resumes you upload are sent to the AI providers that answer them (Groq and
          Google). Job searches send only the search words. Uploaded PDFs are stored privately.
          Government IDs, bank details and similar numbers are removed before anything is sent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {off ? (
          <p className="text-sm text-muted-foreground" role="status">
            The assistant is off for your account: no chat, resume comparison, job recommendations
            or resume indexing. Everything else in the app works as before.
          </p>
        ) : usage.data && usage.data.length > 0 ? (
          <ul className="space-y-3" aria-label="Today's allowances">
            {usage.data.map((q) => (
              <li key={q.name} className="space-y-1">
                <div className="flex items-baseline justify-between text-sm">
                  <span>{q.label}</span>
                  <span className="font-mono text-muted-foreground">
                    {q.used}/{q.limit}
                  </span>
                </div>
                <Progress value={q.limit ? (q.used / q.limit) * 100 : 0} aria-label={q.label} />
              </li>
            ))}
          </ul>
        ) : null}
        <Button
          variant={off ? "default" : "outline"}
          onClick={toggle}
          disabled={setOptOut.isPending}
        >
          {off ? "Turn the assistant on" : "Turn the assistant off"}
        </Button>
      </CardContent>
    </Card>
  )
}
