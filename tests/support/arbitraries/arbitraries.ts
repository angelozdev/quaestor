import fc from 'fast-check'
import {
  BOOKED_ACCOUNTS,
  CENTS_PER_UNIT,
  FAULTS,
  ISO_DATE_LENGTH,
  MAX_BOOKED,
  MAX_DAYS_AFTER,
  MAX_DECIMAL_DIGITS,
  MAX_FAULTY_ITEMS,
  MAX_MOVED,
  MAX_MOVEMENT_CENTS,
  MAX_WHOLE_PART,
  MOVED_ACCOUNTS,
  MS_PER_DAY,
  SIGNS,
} from './arbitraries.constants.ts'
import type { Booked, Fault, Moved, BookedWithDeletes } from './arbitraries.types.ts'

export const amountText = fc
  .tuple(
    fc.constantFrom(...SIGNS),
    fc.integer({ min: 0, max: MAX_WHOLE_PART }),
    fc.array(fc.integer({ min: 0, max: 9 }), { maxLength: MAX_DECIMAL_DIGITS }),
  )
  .map(
    ([sign, whole, decimals]) =>
      `${sign}${whole}${decimals.length === 0 ? '' : `.${decimals.join('')}`}`,
  )

const positiveCents = fc.integer({ min: 1, max: MAX_MOVEMENT_CENTS })

const movementCents = fc
  .tuple(fc.constantFrom(1, -1), positiveCents)
  .map(([sign, magnitude]) => sign * magnitude)

export function amountTextOf(cents: number): string {
  const magnitude = Math.abs(cents)
  const decimals = String(magnitude % CENTS_PER_UNIT).padStart(MAX_DECIMAL_DIGITS, '0')
  return `${cents < 0 ? '-' : ''}${Math.floor(magnitude / CENTS_PER_UNIT)}.${decimals}`
}

export function dateOnOrAfter(first: string): fc.Arbitrary<string> {
  return fc
    .integer({ min: 0, max: MAX_DAYS_AFTER })
    .map((days) =>
      new Date(Date.parse(first) + days * MS_PER_DAY).toISOString().slice(0, ISO_DATE_LENGTH),
    )
}

export function booked(openingDate: string): fc.Arbitrary<Booked[]> {
  return fc.array(
    fc.record({
      account: fc.constantFrom(...BOOKED_ACCOUNTS),
      cents: movementCents,
      date: dateOnOrAfter(openingDate),
    }),
    { minLength: 1, maxLength: MAX_BOOKED },
  )
}

export function bookedWithDeletes(openingDate: string): fc.Arbitrary<BookedWithDeletes> {
  return fc
    .tuple(booked(openingDate), fc.array(fc.nat(), { minLength: 1, maxLength: MAX_BOOKED }))
    .map(([items, picks]) => ({ items, deletes: picks.map((pick) => pick % items.length) }))
}

export const faultyItems: fc.Arbitrary<(Fault | undefined)[]> = fc
  .tuple(
    fc.array(fc.constantFrom(...FAULTS, undefined), { minLength: 1, maxLength: MAX_FAULTY_ITEMS }),
    fc.nat(),
    fc.constantFrom(...FAULTS),
  )
  .map(([faults, at, fault]) => faults.with(at % faults.length, fault))

export function moved(openingDate: string): fc.Arbitrary<Moved[]> {
  return fc
    .array(
      fc.record({
        from: fc.constantFrom(...MOVED_ACCOUNTS),
        step: fc.integer({ min: 1, max: MOVED_ACCOUNTS.length - 1 }),
        sent: positiveCents,
        received: positiveCents,
        date: dateOnOrAfter(openingDate),
      }),
      { minLength: 1, maxLength: MAX_MOVED },
    )
    .map((items) =>
      items.map(({ from, step, ...amounts }) => ({
        from,
        to: MOVED_ACCOUNTS[(MOVED_ACCOUNTS.indexOf(from) + step) % MOVED_ACCOUNTS.length]!,
        ...amounts,
      })),
    )
}
