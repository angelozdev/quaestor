import type { StreamdownProps } from "streamdown"

export const markdownComponents: NonNullable<StreamdownProps["components"]> = {
  h1: ({ children, ...rest }) => (
    <h1 {...rest} className="text-xl font-semibold tracking-tight mt-3 mb-1.5 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children, ...rest }) => (
    <h2 {...rest} className="text-lg font-semibold tracking-tight mt-3 mb-1">
      {children}
    </h2>
  ),
  h3: ({ children, ...rest }) => (
    <h3 {...rest} className="text-base font-semibold mt-2.5 mb-1">
      {children}
    </h3>
  ),
  h4: ({ children, ...rest }) => (
    <h4 {...rest} className="text-sm font-semibold mt-2 mb-0.5">
      {children}
    </h4>
  ),
  h5: ({ children, ...rest }) => (
    <h5 {...rest} className="text-sm font-semibold mt-2 mb-0.5">
      {children}
    </h5>
  ),
  h6: ({ children, ...rest }) => (
    <h6 {...rest} className="text-sm font-semibold mt-2 mb-0.5">
      {children}
    </h6>
  ),
  p: ({ children, ...rest }) => (
    <p {...rest} className="text-sm leading-relaxed my-1.5 first:mt-0 last:mb-0">
      {children}
    </p>
  ),
  strong: ({ children, ...rest }) => (
    <strong {...rest} className="font-semibold">
      {children}
    </strong>
  ),
  em: ({ children, ...rest }) => (
    <em {...rest} className="italic">
      {children}
    </em>
  ),
  ul: ({ children, ...rest }) => (
    <ul {...rest} className="my-1.5 ml-5 list-disc space-y-0.5">
      {children}
    </ul>
  ),
  ol: ({ children, ...rest }) => (
    <ol {...rest} className="my-1.5 ml-5 list-decimal space-y-0.5">
      {children}
    </ol>
  ),
  li: ({ children, ...rest }) => (
    <li {...rest} className="pl-0.5">
      {children}
    </li>
  ),
  a: ({ children, href, ...rest }) => (
    <a
      {...rest}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[color:var(--primary)] underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  code: ({ children, ...rest }) => (
    <code {...rest} className="rounded bg-[color:var(--muted)] px-1 py-0.5 text-[0.85em] font-mono">
      {children}
    </code>
  ),
  pre: ({ children, ...rest }) => (
    <pre
      {...rest}
      className="my-2 overflow-x-auto rounded-md border border-[color:var(--border)] bg-[color:var(--muted)]/40 p-3 text-xs"
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...rest }) => (
    <blockquote
      {...rest}
      className="my-1.5 border-l-2 border-[color:var(--primary)]/40 pl-3 text-[color:var(--muted-foreground)] italic"
    >
      {children}
    </blockquote>
  ),
  hr: ({ ...rest }) => <hr {...rest} className="my-3 border-[color:var(--border)]" />,
  table: ({ children, ...rest }) => (
    <table {...rest} className="my-2 w-full text-xs">
      {children}
    </table>
  ),
  thead: ({ children, ...rest }) => (
    <thead {...rest} className="border-b border-[color:var(--border)]">
      {children}
    </thead>
  ),
  th: ({ children, ...rest }) => (
    <th {...rest} className="text-left font-semibold py-1.5 px-2">
      {children}
    </th>
  ),
  td: ({ children, ...rest }) => (
    <td {...rest} className="py-1.5 px-2 align-top border-t border-[color:var(--border)]/50">
      {children}
    </td>
  ),
  del: ({ children, ...rest }) => (
    <del {...rest} className="text-[color:var(--muted-foreground)] line-through">
      {children}
    </del>
  ),
}
