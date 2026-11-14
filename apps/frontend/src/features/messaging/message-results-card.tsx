import { MailCheck } from "lucide-react"

import { useMessageStats } from "@/api/messaging"
import { EmptyState } from "@/components/common/empty-state"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatPercent } from "@/lib/format"

/** Which messages get answered. Fed by "I sent it" and "They replied". */
export function MessageResultsCard() {
  const stats = useMessageStats()
  if (!stats.data) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Message results</CardTitle>
        <CardDescription>
          Last 90 days. Counts the messages you marked as sent and the replies you logged.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {stats.data.sent === 0 ? (
          <EmptyState
            icon={MailCheck}
            title="No messages recorded yet"
            description="Write a message from any opportunity, then choose “I sent it”."
          />
        ) : (
          <div className="space-y-4">
            <p className="text-sm">
              <span className="font-mono text-2xl font-semibold">
                {formatPercent(stats.data.reply_rate)}
              </span>{" "}
              replied ({stats.data.replied} of {stats.data.sent})
            </p>
            <ul className="divide-y text-sm" aria-label="Replies by message">
              {stats.data.by_template.map((row) => (
                <li key={`${row.key}|${row.channel}`} className="flex items-center gap-3 py-2">
                  <span className="min-w-0 flex-1 truncate">
                    {row.name}{" "}
                    <span className="text-xs text-muted-foreground">
                      ({row.channel === "email" ? "email" : "LinkedIn"})
                    </span>
                  </span>
                  <span className="font-mono text-muted-foreground">
                    {row.replied}/{row.sent}
                  </span>
                  <span className="w-12 text-right font-mono">{formatPercent(row.reply_rate)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
