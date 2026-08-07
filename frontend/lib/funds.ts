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

/**
 * What each shape does, in the one clause every screen builds its sentence
 * from — the empty screen, an empty heading and the panel all make the same
 * claim, so the claim is written here once.
 */
export function whatItIs(shape: FundShape): string {
  return shape === "fondo"
    ? "aparta plata cada mes y guarda lo que sobra"
    : "es un tope: lo que no gastes no se guarda"
}

/** The clause as a whole sentence, with no full stop: "Un fondo aparta …". */
export function shapeSentence(shape: FundShape): string {
  return `Un ${shape} ${whatItIs(shape)}`
}

/** How a fund is labelled in a breakdown: "Presupuesto · Restaurantes". */
export function labelOf(fund: { accumulates: boolean; name: string }): string {
  return `${nounOf(shapeOf(fund))} · ${fund.name}`
}
