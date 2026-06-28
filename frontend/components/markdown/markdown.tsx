"use client"

import { memo } from "react"
import { Streamdown } from "streamdown"
import { markdownComponents } from "./markdown-elements"

type Props = {
  children: string
  className?: string
}

function MarkdownImpl({ children, className }: Props) {
  return (
    <Streamdown mode="streaming" className={className} components={markdownComponents}>
      {children}
    </Streamdown>
  )
}

export const Markdown = memo(MarkdownImpl)
