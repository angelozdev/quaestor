"use client"

import { useState } from "react"
import type { StatedAmount } from "@/lib/money"

/**
 * The amount box of a screen that also offers an account, when the figure it
 * shows is held elsewhere — a form field, which the same figure is validated and
 * submitted from.
 *
 * `write` is the owner stating a figure and `offer` is the app proposing one, so
 * a currency he only passed through leaves no mark: what he stated is what every
 * restatement reads, so going out to another currency and back offers the
 * movement's own figure again and an amount he never wrote is never corrected
 * (AC-21).
 */
export function useAmountBox(initial: StatedAmount, show: (cents: number | null) => void) {
  const [stated, setStated] = useState<StatedAmount>(initial)

  function write(cents: number | null, currency: string) {
    show(cents)
    setStated({ cents, currency })
  }

  return { stated, offer: show, write }
}

/**
 * The amount box of a screen that also offers an account, holding the figure it
 * shows itself.
 *
 * One hook for the three screens that offer an account: correcting a movement,
 * confirming a payment and moving a repeating charge behave identically on
 * purpose (ADR-0051, ADR-0052).
 */
export function useStatedAmount(initial: StatedAmount) {
  const [amount, setAmount] = useState<number | null>(initial.cents)
  const box = useAmountBox(initial, setAmount)

  return { amount, ...box }
}
