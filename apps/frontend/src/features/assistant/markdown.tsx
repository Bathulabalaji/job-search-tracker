import Markdown, { type Components } from "react-markdown"
import { Link } from "react-router-dom"
import remarkGfm from "remark-gfm"

// Model output is untrusted: raw HTML is never rendered (react-markdown's default), and only
// links into this app become links. Anything else stays visible as plain text.
const components: Components = {
  a: ({ href, children }) =>
    href?.startsWith("/") && !href.startsWith("//") ? (
      <Link to={href} className="font-medium text-primary underline underline-offset-2">
        {children}
      </Link>
    ) : (
      <span>{children}</span>
    ),
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  code: ({ children }) => (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
  ),
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto">
      <table className="text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b px-2 py-1 text-left font-medium">{children}</th>,
  td: ({ children }) => <td className="border-b px-2 py-1">{children}</td>,
  h1: ({ children }) => <p className="mb-2 font-semibold">{children}</p>,
  h2: ({ children }) => <p className="mb-2 font-semibold">{children}</p>,
  h3: ({ children }) => <p className="mb-2 font-semibold">{children}</p>,
}

export function AssistantMarkdown({ text }: { text: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} components={components}>
      {text}
    </Markdown>
  )
}
