/**
 * The two nouns, derived and never stored (product ADR-042).
 *
 * One record shape underneath: a fund that carries its leftover money into the
 * next month is a *fondo*, and one that does not is a *presupuesto*. Storing
 * the split would make a second source of truth that can disagree with
 * `accumulates`, so every screen that names a shape reads it from here.
 */
export type FundShape = "fondo" | "presupuesto"

/** Which of the two a record is, read from the only field that decides it. */
export function shapeOf(fund: { accumulates: boolean }): FundShape {
  return fund.accumulates ? "fondo" : "presupuesto"
}

/** The same derivation the other way: which entry point was used decides it. */
export function accumulatesAs(shape: FundShape): boolean {
  return shape === "fondo"
}

/** The noun as a label or a sentence starts it: "Fondo", "Presupuesto". */
export function nounOf(shape: FundShape): string {
  return shape === "fondo" ? "Fondo" : "Presupuesto"
}
