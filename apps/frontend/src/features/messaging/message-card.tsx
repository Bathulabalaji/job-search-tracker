import { Check, MailPlus, Send } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { useMarkReplied, useSentMessages, useSuggestions } from "@/api/messaging"
import type { Opportunity } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate } from "@/lib/format"
import { MessageDialog } from "./message-dialog"

/** The opportunity page's "what should I send next?" card, plus what was already sent. */
export function MessageCard({ opportunity }: { opportunity: Opportunity }) {
  const [open, setOpen] = useState(false)
  const suggestions = useSuggestions(opportunity.id)
  const sent = useSentMessages(opportunity.id)
  const replied = useMarkReplied(opportunity.id)

  const items = suggestions.data?.suggestions ?? []
  const next = items.find((s) => s.kind === "send" && s.due)
  const stop = items.find((s) => s.kind === "stop")
  const upcoming = items.find((s) => s.kind === "wait")
  const addContact = items.find((s) => s.kind === "add_contact")

  return (
    <Card>
      <CardHeader>
        <CardTitle>Messages</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {suggestions.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="space-y-1 text-sm">
            {next ? (
              <>
                <p className="font-medium">Next: {next.title}</p>
                <p className="text-muted-foreground">{next.reason}</p>
              </>
            ) : stop ? (
              <p className="text-muted-foreground">{stop.reason}</p>
            ) : addContact ? (
              <p className="text-muted-foreground">{addContact.reason}</p>
            ) : upcoming ? (
              <>
                <p className="font-medium">Up next: {upcoming.title}</p>
                <p className="text-muted-foreground">{upcoming.reason}</p>
              </>
            ) : (
              <p className="text-muted-foreground">
                Nothing is due. You can still write a message any time.
              </p>
            )}
          </div>
        )}
        <Button
          className="w-full"
          variant={next ? "default" : "outline"}
          onClick={() => setOpen(true)}
        >
          {next ? <Send /> : <MailPlus />} {next ? "Write it" : "Write a message"}
        </Button>

        {sent.data && sent.data.length > 0 ? (
          <ul className="divide-y border-t pt-1" aria-label="Messages you sent">
            {sent.data.slice(0, 4).map((m) => (
              <li key={m.id} className="flex items-center gap-2 py-2 text-sm">
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{m.template_name ?? "Message"}</span>
                  <span className="text-xs text-muted-foreground">
                    {m.channel === "email" ? "Email" : "LinkedIn"} · {formatDate(m.sent_at)}
                  </span>
                </span>
                {m.replied_at ? (
                  <Badge variant="secondary" className="gap-1">
                    <Check aria-hidden /> Replied
                  </Badge>
                ) : (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={replied.isPending}
                    onClick={() =>
                      replied.mutate(m.id, {
                        onSuccess: () => toast.success("Logged their reply"),
                        onError: () => toast.error("Couldn't record that."),
                      })
                    }
                  >
                    They replied
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
      <MessageDialog opportunity={opportunity} open={open} onOpenChange={setOpen} />
    </Card>
  )
}
