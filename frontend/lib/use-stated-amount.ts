"use client"

import { useState } from "react"
import type { StatedAmount } from "@/lib/money"

/**
 * The amount box of a screen that also offers an account: the figure it shows,
 * and the figure the owner stated together with the currency he stated it in.
 *
 * The two are told apart because a currency the owner only passed through must
 * leave no mark: what he stated is what every restatement reads, so going out to
 * another currency and back offers the movement's own figure again and an amount
 * he never wrote is never corrected (AC-21).
 *
 * One hook for both screens that offer an account: correcting a movement and
 * confirming a payment behave identically on purpose (ADR-0051).
 */
export function useStatedAmount(initial: StatedAmount) {
  const [amount, setAmount] = useState<number | null>(initial.cents)
  const [stated, setStated] = useState<StatedAmount>(initial)

  function write(cents: number | null, currency: string) {
    setAmount(cents)
    setStated({ cents, currency })
  }

  return { amount, stated, offer: setAmount, write }
}
