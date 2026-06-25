"use client"

import { memo } from "react"
import { Streamdown } from "streamdown"

type Props = {
  children: string
  className?: string
}

function MarkdownImpl({ children, className }: Props) {
  return (
    <Streamdown
      className={className}
      components={{
        strong: ({ children: c, ...rest }) => (
          <strong {...rest} className="font-semibold">
            {c}
          </strong>
        ),
      }}
    >
      {children}
    </Streamdown>
  )
}

export const Markdown = memo(MarkdownImpl)