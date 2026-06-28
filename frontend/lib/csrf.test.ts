import { describe, expect, it } from "vitest"
import {
  CSRF_COOKIE_NAME,
  CSRF_HEADER_NAME,
  csrfHeaders,
  getCsrfToken,
} from "./csrf"

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/`
}

describe("csrf", () => {
  describe("getCsrfToken", () => {
    it("returns the value of the quaestor_csrf cookie", () => {
      setCookie(CSRF_COOKIE_NAME, "abc123")
      expect(getCsrfToken()).toBe("abc123")
    })

    it("ignores unrelated cookies and picks the right one", () => {
      setCookie("session", "secret")
      setCookie("other", "zzz")
      setCookie(CSRF_COOKIE_NAME, "right-one")
      expect(getCsrfToken()).toBe("right-one")
    })

    it("decodes URI-encoded values", () => {
      setCookie(CSRF_COOKIE_NAME, "%2Bhello%2Fworld")
      expect(getCsrfToken()).toBe("+hello/world")
    })

    it("returns the last occurrence when the cookie appears twice", () => {
      setCookie(CSRF_COOKIE_NAME, "first")
      setCookie(CSRF_COOKIE_NAME, "second")
      expect(getCsrfToken()).toBe("second")
    })
  })

  describe("csrfHeaders", () => {
    it("returns the X-CSRF-Token header carrying the cookie value", () => {
      setCookie(CSRF_COOKIE_NAME, "token-value")
      expect(csrfHeaders()).toEqual({ [CSRF_HEADER_NAME]: "token-value" })
    })

    it("returns the empty object when no quaestor_csrf cookie is present", () => {
      document.cookie = `${CSRF_COOKIE_NAME}=__sentinel__; path=/`
      setCookie("unrelated", "x")
      document.cookie = `${CSRF_COOKIE_NAME}=; path=/`
      expect(csrfHeaders()).toEqual({})
    })
  })
})