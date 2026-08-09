import type { FundRule } from "@/lib/api/types"
import type { FundShape } from "@/lib/funds"
import { formatCents } from "@/lib/money"

/** One rule as the owner meets it: the job it does, and what it costs him. */
export interface RuleOffer {
  rule: FundRule
  label: string
  example: string
}

const FONDO_RULES: RuleOffer[] = [
  {
    rule: "fixed",
    label: "Aparto un monto fijo cada mes",
    example:
      "Por ejemplo: $100.000 al mes en Tecnología. Si gastas $60.000, septiembre guarda $40.000 y tendrás $140.000.",
  },
  {
    rule: "average",
    label: "Aparto lo que suelo gastar",
    example:
      "Por ejemplo: Los últimos 3 meses gastaste $300.000 en Mercado. Aparto eso, y lo que sobre se queda.",
  },
  {
    rule: "from-recurring",
    label: "Pago mis suscripciones mes a mes",
    example:
      "Por ejemplo: Netflix cobra $600.000 en febrero. Desde agosto aparto $100.000 al mes, y cuando se paga empieza sola para el año siguiente.",
  },
]

const PRESUPUESTO_RULES: RuleOffer[] = [
  {
    rule: "fixed",
    label: "Yo pongo el tope",
    example: "Por ejemplo: Máximo $100.000 al mes en Restaurantes. Lo que no gastes no se guarda.",
  },
  {
    rule: "average",
    label: "El tope sale de lo que ya gastabas",
    example: "Por ejemplo: Los últimos 3 meses gastaste $89.000 al mes. Ese es el tope.",
  },
]

/**
 * The rules a shape may use.
 *
 * Reading the owner's recurring charges has to carry money forward, so it is
 * never offered as a presupuesto (AC-12).
 */
export function rulesFor(shape: FundShape): RuleOffer[] {
  return shape === "fondo" ? FONDO_RULES : PRESUPUESTO_RULES
}

/** How a screen names a rule, in the words of the shape that carries it. */
export function ruleLabel(rule: FundRule, shape: FundShape): string {
  return rulesFor(shape).find((offer) => offer.rule === rule)?.label ?? rule
}

function windowSaid(windowMonths: number, figure: string, where: string): string {
  return windowMonths === 1
    ? `El último mes gastaste ${figure}${where}.`
    : `Los últimos ${windowMonths} meses gastaste ${figure} al mes${where}.`
}

/**
 * What choosing this rule would mean, in the owner's own figures where the
 * screen has them and in a worked example where it does not.
 *
 * `wouldAsk` is what the fund would ask its first month, as the server works
 * it out — the screen never runs the arithmetic itself.
 */
export function ruleConsequence(
  rule: FundRule,
  shape: FundShape,
  live: { wouldAsk: number | null; categoryName: string | null; windowMonths: number },
): string {
  const offer = rulesFor(shape).find((it) => it.rule === rule)
  const example = offer?.example ?? ""
  if (live.wouldAsk === null || live.categoryName === null) return example
  const figure = formatCents(live.wouldAsk, "COP")
  if (rule === "average") {
    return shape === "presupuesto"
      ? `${windowSaid(live.windowMonths, figure, "")} Ese es el tope.`
      : `${windowSaid(live.windowMonths, figure, ` en ${live.categoryName}`)} Aparto eso, y lo que sobre se queda.`
  }
  if (rule === "from-recurring") {
    return live.wouldAsk === 0
      ? `${live.categoryName} no tiene cobros registrados: pediría ${figure} al mes.`
      : `Aparto ${figure} al mes, y cuando se paga empieza sola para el año siguiente.`
  }
  return example
}
