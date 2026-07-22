import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { SkeletonBlock, SkeletonRows, SkeletonText } from "./skeleton"

describe("skeleton variants", () => {
  it("renders the requested number of text lines", () => {
    const { container } = render(<SkeletonText lines={3} />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(3)
  })

  it("renders the requested number of rows", () => {
    const { container } = render(<SkeletonRows rows={5} />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(5)
  })

  it("renders a free-form block", () => {
    const { container } = render(<SkeletonBlock className="h-14 w-64" />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(1)
  })
})
