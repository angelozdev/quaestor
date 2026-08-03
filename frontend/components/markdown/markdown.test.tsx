import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Markdown } from "./markdown"

describe("Markdown", () => {
  it("renders bold text as a <strong> element", () => {
    render(<Markdown>{"**hola**"}</Markdown>)
    const strong = screen.getByText("hola")
    expect(strong.tagName).toBe("STRONG")
  })

  it("renders italic text as an <em> element", () => {
    render(<Markdown>{"*hola*"}</Markdown>)
    const em = screen.getByText("hola")
    expect(em.tagName).toBe("EM")
  })

  it("renders a GFM table with thead and th cells", () => {
    const md = `| A | B |
| --- | --- |
| 1 | 2 |`
    const { container } = render(<Markdown>{md}</Markdown>)
    expect(container.querySelector("table")).toBeInTheDocument()
    expect(container.querySelector("thead")).toBeInTheDocument()
    expect(container.querySelectorAll("th").length).toBe(2)
    expect(container.querySelectorAll("tbody td").length).toBe(2)
  })

  it("renders an unordered list", () => {
    const { container } = render(<Markdown>{"- a\n- b"}</Markdown>)
    expect(container.querySelector("ul")).toBeInTheDocument()
    expect(container.querySelectorAll("li").length).toBe(2)
  })

  it("renders an ordered list", () => {
    const { container } = render(<Markdown>{"1. a\n2. b"}</Markdown>)
    expect(container.querySelector("ol")).toBeInTheDocument()
    expect(container.querySelectorAll("li").length).toBe(2)
  })

  it("renders inline code in a <code> element", () => {
    const { container } = render(<Markdown>{"usa `npm test` ahora"}</Markdown>)
    const code = container.querySelector("code")
    expect(code).toBeInTheDocument()
    expect(code?.textContent).toBe("npm test")
  })

  it("renders fenced code blocks in a <pre><code> structure", () => {
    const md = "```js\nconst x = 1\n```"
    const { container } = render(<Markdown>{md}</Markdown>)
    expect(container.querySelector("pre")).toBeInTheDocument()
    expect(container.querySelector("pre code")).toBeInTheDocument()
  })

  it("opens links with safe rel and target", () => {
    const { container } = render(<Markdown>{"[t](https://example.com)"}</Markdown>)
    const a = container.querySelector("a")
    expect(a).toBeInTheDocument()
    expect(a?.getAttribute("target")).toBe("_blank")
    expect(a?.getAttribute("rel")).toBe("noopener noreferrer")
    expect(a?.getAttribute("href")).toMatch(/^https:\/\/example\.com\/?$/)
  })

  it("strips dangerous url schemes (javascript:)", () => {
    const { container } = render(<Markdown>{"[t](javascript:alert(1))"}</Markdown>)
    // rehype-harden must drop the href or replace it with a safe value.
    const a = container.querySelector("a")
    if (a) {
      expect(a.getAttribute("href") ?? "").not.toMatch(/^javascript:/i)
    } else {
      // Equally acceptable: the entire link is stripped.
      expect(a).toBeNull()
    }
  })

  it("strips raw <script> tags from input", () => {
    const { container } = render(<Markdown>{"<script>alert(1)</script>"}</Markdown>)
    expect(container.querySelector("script")).toBeNull()
  })

  it("handles unterminated markdown without throwing", () => {
    expect(() => render(<Markdown>{"**bold sin cerrar"}</Markdown>)).not.toThrow()
  })

  it("passes className through to the root element", () => {
    const { container } = render(<Markdown className="my-custom-class">{"hola"}</Markdown>)
    expect(container.firstChild).not.toBeNull()
    const root = container.firstChild as HTMLElement
    expect(root.className).toContain("my-custom-class")
  })
})
