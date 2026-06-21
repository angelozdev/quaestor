# Zod + react-hook-form Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plain `useState`-based form state across all create/edit forms with `zod` schemas validated via `react-hook-form` + `@hookform/resolvers`, and harden backend Pydantic constraints so non-numeric input is rejected both client-side (inline Spanish error) and server-side (422).

**Architecture:** Hybrid schema pattern. Reusable zod primitives live in `frontend/lib/schemas/primitives.ts`. Each form declares its own `z.object({...})` schema inline, composing primitives. A shared `<FormField>` wraps `<Label>` + `<Input>` + error display. Global zod error map (`frontend/lib/schemas/messages.ts`) provides Spanish messages. Backend: add `gt`/`ge`/`le` `Field` constraints to numeric Pydantic models in `src/quaestor/mcp/tools/core.py`. Axios interceptor exposes `field` from Pydantic 422 detail so forms can `setError(field, ...)`.

**Tech Stack:**
- Frontend: Next.js 16.2.9, React 19.2.4, TypeScript 5, Biome 2.5
- Frontend deps (new): `zod`, `react-hook-form`, `@hookform/resolvers`
- Frontend deps (new, dev): `vitest`, `@testing-library/react`, `@testing-library/user-event`, `happy-dom`, `@vitest/coverage-v8`
- Backend: Python 3.12+, Pydantic v2, FastAPI

**Spec:** `docs/superpowers/specs/2026-06-21-zod-form-validation-design.md`

## Global Constraints

- Package manager: `pnpm@11.3.0` (per `frontend/package.json`). Use `pnpm add` / `pnpm add -D`.
- Linter/Formatter: Biome 2.5. Run `pnpm biome check --write .` before commit.
- TypeScript strict mode (per `frontend/tsconfig.json` `"strict": true`). All new code must compile under strict.
- Path alias: `@/*` → `frontend/*` (per `frontend/tsconfig.json`). Use `@/lib/...`, `@/components/...`, `@/ui` for imports.
- React 19: forms must be `"use client"`. No class components.
- React Query (`@tanstack/react-query@5.101`) for API calls; use `useMutation` with `mutation.isPending` for button disabled state.
- Spanish UI copy. Error messages: "Requerido", "Solo números", "Debe ser ≥ 1", "Fecha inválida", "Fin debe ser ≥ inicio".
- Currency inputs in cents (integer). FX rate in `usd_cop` (float, > 0). Money text parsing stays in `MoneyInput` (`parseMoneyToCents`).
- Dates: ISO `YYYY-MM-DD` strings in zod schemas; native `<input type="date">` produces this natively.
- Backend Pydantic constraints: positive integers (`gt=0`), non-negative allowed only for `balance` (`ge=0`). Sensible upper bounds: `usd_cop` ≤ 100_000, `interval_count` ≤ 1000.
- Big-bang single PR. Order: setup → primitives → components → forms (recurring first because it has the bug) → backend → interceptor → polish.

---

## File Structure

### New frontend files

| Path | Responsibility |
|---|---|
| `frontend/lib/schemas/primitives.ts` | Reusable zod primitives (single source of truth for numeric bounds, date format, string length). |
| `frontend/lib/schemas/messages.ts` | Spanish error message map + `registerZodMessages()` helper. |
| `frontend/lib/schemas/primitives.test.ts` | Vitest unit tests for primitives. |
| `frontend/lib/schemas/messages.test.ts` | Vitest tests for error map registration. |
| `frontend/components/form-field.tsx` | `<Label>` + `<Input>` + error display, integrates with `useForm`. |
| `frontend/components/form-field.test.tsx` | Component test. |
| `frontend/vitest.config.ts` | Vitest config (jsdom env, path alias `@/*`). |
| `frontend/tests/setup.ts` | Test setup (cleanup, `@testing-library/jest-dom` matchers). |

### Modified frontend files

| Path | Change |
|---|---|
| `frontend/package.json` | Add new deps; add `test`, `test:watch`, `test:coverage` scripts. |
| `frontend/app/providers.tsx` | Call `registerZodMessages()` once at mount. |
| `frontend/app/(app)/recurring/page.tsx` | Migrate create + edit forms (interval_count bug source). |
| `frontend/app/(app)/budgets/page.tsx` | Migrate assign-budget form. |
| `frontend/app/(app)/goals/page.tsx` | Migrate create + contribute forms. |
| `frontend/app/(app)/settings/page.tsx` | Migrate FX-rate form. |
| `frontend/app/(app)/to-pay/page.tsx` | Migrate plan-payment form. |
| `frontend/components/transaction-create-dialog.tsx` | Migrate new-transaction form. |
| `frontend/components/transaction-edit-dialog.tsx` | Migrate edit-transaction form. |
| `frontend/components/entity-form-dialog.tsx` | Migrate generic entity form (last; consumers depend on it). |

### Modified backend files

| Path | Change |
|---|---|
| `backend/src/quaestor/mcp/tools/core.py` | Add `gt`/`ge`/`le` constraints to numeric fields missing them. |
| `backend/src/quaestor/mcp/registry.py` | If needed, surface Pydantic 422 field paths through tool error wrapper (read in Task 17). |
| `backend/src/quaestor/mcp/format.py` | (Same as above, only if read shows it's the right place.) |
| `backend/tests/mcp/test_core_writes.py` | Add constraint-violation test cases. |

### Modified frontend infra

| Path | Change |
|---|---|
| `frontend/lib/api/client.ts` | Expose Pydantic `detail[].loc` → `field` on `ApiError`. |
| `frontend/lib/api/types.ts` | Add `field?: string` to `ApiError`. |

---

## Task 1: Add frontend dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install runtime deps**

```bash
cd frontend && pnpm add zod react-hook-form @hookform/resolvers
```

Expected: `+ zod 4.x`, `+ react-hook-form 7.x`, `+ @hookform/resolvers 5.x` appended to `dependencies`. `pnpm-lock.yaml` updated.

**Step 2: Install test deps**

```bash
cd frontend && pnpm add -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom happy-dom @vitest/coverage-v8 jsdom
```

Expected: dev deps appended. Versions: vitest ^3.x, RTL ^16.x, user-event ^14.x, jest-dom ^6.x, happy-dom ^15.x, coverage-v8 ^3.x, jsdom ^26.x.

**Step 3: Add test scripts**

Edit `frontend/package.json` `scripts` block. Add after `"check:ci"`:

```json
"test": "vitest run",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage",
```

**Step 4: Verify install**

```bash
cd frontend && pnpm vitest --version
```

Expected: prints `vitest` version (no error).

**Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(frontend): add zod, react-hook-form, vitest deps"
```

---

## Task 2: Configure Vitest

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/setup.ts`
- Modify: `frontend/tsconfig.json` (exclude tests from `next build` if needed)

**Step 1: Create vitest config**

Create `frontend/vitest.config.ts`:

```ts
import { fileURLToPath } from "node:url"
import { defineConfig } from "vitest/config"
import tsconfigPaths from "vite-tsconfig-paths"

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
})
```

**Step 2: Install vite-tsconfig-paths**

```bash
cd frontend && pnpm add -D vite-tsconfig-paths
```

Expected: `+ vite-tsconfig-paths 5.x`.

**Step 3: Create test setup file**

Create `frontend/tests/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest"
import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"

afterEach(() => {
  cleanup()
})
```

**Step 4: Smoke test**

Create `frontend/tests/smoke.test.ts`:

```ts
import { describe, expect, it } from "vitest"

describe("smoke", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2)
  })
})
```

Run: `cd frontend && pnpm test`

Expected: 1 passed.

**Step 5: Delete smoke, commit config**

```bash
rm frontend/tests/smoke.test.ts
cd /Users/angelozdev/me/quaestor && git add frontend/vitest.config.ts frontend/tests/setup.ts frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(frontend): configure vitest with happy-dom + RTL setup"
```

---

## Task 3: Create zod primitives

**Files:**
- Create: `frontend/lib/schemas/primitives.ts`
- Create: `frontend/lib/schemas/primitives.test.ts`

**Interfaces:**
- Produces: `nonNegativeCents`, `positiveCents`, `intervalCount`, `fxRate`, `isoDate`, `requiredString`, `optionalString` — all `z.ZodType` exports consumed by form schemas in later tasks.

**Step 1: Write failing tests**

Create `frontend/lib/schemas/primitives.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import {
  fxRate,
  intervalCount,
  isoDate,
  nonNegativeCents,
  optionalString,
  positiveCents,
  requiredString,
} from "./primitives"

describe("nonNegativeCents", () => {
  it("rejects negative", () => {
    expect(nonNegativeCents.safeParse(-1).success).toBe(false)
  })
  it("accepts zero", () => {
    expect(nonNegativeCents.safeParse(0).success).toBe(true)
  })
  it("accepts large positive", () => {
    expect(nonNegativeCents.safeParse(10_000_000).success).toBe(true)
  })
  it("rejects NaN", () => {
    expect(nonNegativeCents.safeParse(Number.NaN).success).toBe(false)
  })
})

describe("positiveCents", () => {
  it("rejects zero", () => {
    expect(positiveCents.safeParse(0).success).toBe(false)
  })
  it("rejects negative", () => {
    expect(positiveCents.safeParse(-100).success).toBe(false)
  })
  it("accepts 1", () => {
    expect(positiveCents.safeParse(1).success).toBe(true)
  })
})

describe("intervalCount", () => {
  it("rejects 0", () => {
    expect(intervalCount.safeParse(0).success).toBe(false)
  })
  it("rejects 1.5", () => {
    expect(intervalCount.safeParse(1.5).success).toBe(false)
  })
  it("rejects > 1000", () => {
    expect(intervalCount.safeParse(1001).success).toBe(false)
  })
  it("accepts 2", () => {
    expect(intervalCount.safeParse(2).success).toBe(true)
  })
})

describe("fxRate", () => {
  it("rejects 0", () => {
    expect(fxRate.safeParse(0).success).toBe(false)
  })
  it("rejects > 100000", () => {
    expect(fxRate.safeParse(100_001).success).toBe(false)
  })
  it("accepts 4150.5", () => {
    expect(fxRate.safeParse(4150.5).success).toBe(true)
  })
})

describe("isoDate", () => {
  it("accepts YYYY-MM-DD", () => {
    expect(isoDate.safeParse("2026-06-21").success).toBe(true)
  })
  it("rejects DD/MM/YYYY", () => {
    expect(isoDate.safeParse("21/06/2026").success).toBe(false)
  })
  it("rejects empty", () => {
    expect(isoDate.safeParse("").success).toBe(false)
  })
})

describe("requiredString", () => {
  it("rejects empty", () => {
    expect(requiredString.safeParse("").success).toBe(false)
  })
  it("rejects whitespace-only", () => {
    expect(requiredString.safeParse("   ").success).toBe(false)
  })
  it("accepts non-empty", () => {
    expect(requiredString.safeParse("Hola").success).toBe(true)
  })
})

describe("optionalString", () => {
  it("accepts undefined", () => {
    expect(optionalString.safeParse(undefined).success).toBe(true)
  })
  it("accepts empty string", () => {
    expect(optionalString.safeParse("").success).toBe(true)
  })
  it("accepts long string", () => {
    expect(optionalString.safeParse("a".repeat(500)).success).toBe(true)
  })
})
```

**Step 2: Run tests, expect failure**

Run: `cd frontend && pnpm test lib/schemas/primitives.test.ts`

Expected: FAIL — `Cannot find module './primitives'`.

**Step 3: Implement primitives**

Create `frontend/lib/schemas/primitives.ts`:

```ts
import { z } from "zod"

/** Integer cents >= 0. Used for balances and zero-allowed amounts. */
export const nonNegativeCents = z
  .number({ invalid_type_error: "Solo números" })
  .int("Solo números enteros")
  .nonnegative("Debe ser ≥ 0")

/** Integer cents > 0. Used for expenses, income, transfers, contributions. */
export const positiveCents = z
  .number({ invalid_type_error: "Solo números" })
  .int("Solo números enteros")
  .positive("Debe ser > 0")

/** Recurring interval count: integer 1..1000. */
export const intervalCount = z
  .number({ invalid_type_error: "Solo números" })
  .int("Solo números enteros")
  .min(1, "Debe ser ≥ 1")
  .max(1000, "Debe ser ≤ 1000")

/** USD→COP rate: float (0, 100000]. */
export const fxRate = z
  .number({ invalid_type_error: "Solo números" })
  .positive("Debe ser > 0")
  .max(100_000, "Debe ser ≤ 100000")

/** ISO date string YYYY-MM-DD. Native <input type="date"> produces this. */
export const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Fecha inválida (YYYY-MM-DD)")

/** Required, trimmed, non-empty string with sane length. */
export const requiredString = z
  .string()
  .trim()
  .min(1, "Requerido")
  .max(120, "Máximo 120 caracteres")

/** Optional free-form string, trimmed, capped. */
export const optionalString = z
  .string()
  .trim()
  .max(500, "Máximo 500 caracteres")
  .optional()
```

**Step 4: Run tests, expect pass**

Run: `cd frontend && pnpm test lib/schemas/primitives.test.ts`

Expected: 18 passed.

**Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add frontend/lib/schemas/primitives.ts frontend/lib/schemas/primitives.test.ts
git commit -m "feat(frontend): zod primitives for forms (cents, dates, strings)"
```

---

## Task 4: Create global zod error messages

**Files:**
- Create: `frontend/lib/schemas/messages.ts`
- Create: `frontend/lib/schemas/messages.test.ts`
- Modify: `frontend/app/providers.tsx`

**Interfaces:**
- Produces: `registerZodMessages()` — call once at app boot; overrides default English messages with Spanish for the codes we use.

**Step 1: Write failing test**

Create `frontend/lib/schemas/messages.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { z } from "zod"
import { registerZodMessages } from "./messages"

describe("registerZodMessages", () => {
  it("overrides invalid_type for number with Solo números", () => {
    registerZodMessages()
    const schema = z.number({ invalid_type_error: "Solo números" })
    const result = schema.safeParse("abc")
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe("Solo números")
    }
  })
})
```

**Step 2: Run test, expect failure**

Run: `cd frontend && pnpm test lib/schemas/messages.test.ts`

Expected: FAIL — `Cannot find module './messages'`.

**Step 3: Implement messages**

Create `frontend/lib/schemas/messages.ts`:

```ts
import { z } from "zod"

/**
 * Register a global Spanish error map for zod. Call once at app boot
 * (Providers). After this call, every `z.X.safeParse` returns issues
 * with Spanish `message` for the codes listed below; per-schema custom
 * messages (e.g. `z.number({ invalid_type_error: ... })`) still win
 * because zod prefers schema-level over global.
 */
export function registerZodMessages(): void {
  z.setErrorMap((issue, _ctx) => {
    switch (issue.code) {
      case z.ZodIssueCode.invalid_type:
        if (issue.received === "nan") return { message: "Solo números" }
        if (issue.expected === "number") return { message: "Solo números" }
        return { message: "Valor inválido" }
      case z.ZodIssueCode.invalid_string:
        return { message: "Formato inválido" }
      case z.ZodIssueCode.too_small:
        if (issue.type === "string" && issue.minimum === 1) return { message: "Requerido" }
        if (issue.type === "number" && issue.minimum === 1) return { message: "Debe ser ≥ 1" }
        if (issue.type === "number" && issue.minimum === 0) return { message: "Debe ser ≥ 0" }
        return { message: "Valor demasiado pequeño" }
      case z.ZodIssueCode.too_big:
        return { message: "Valor demasiado grande" }
      case z.ZodIssueCode.invalid_enum_value:
        return { message: "Opción inválida" }
      default:
        return { message: "Valor inválido" }
    }
  })
}
```

**Step 4: Run test, expect pass**

Run: `cd frontend && pnpm test lib/schemas/messages.test.ts`

Expected: 1 passed.

**Step 5: Register in Providers**

Edit `frontend/app/providers.tsx`. Add import at top:

```ts
import { registerZodMessages } from "@/lib/schemas/messages"
```

Inside the `Providers` component function, before `useEffect`:

```ts
useState(() => {
  registerZodMessages()
})
```

Resulting top of function:

```tsx
export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  // Register zod Spanish error map exactly once.
  useState(() => {
    registerZodMessages()
  })
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
  )
  // ...rest unchanged
```

**Step 6: Lint and commit**

```bash
cd frontend && pnpm biome check --write app/providers.tsx lib/schemas/
cd /Users/angelozdev/me/quaestor && git add frontend/lib/schemas/messages.ts frontend/lib/schemas/messages.test.ts frontend/app/providers.tsx
git commit -m "feat(frontend): Spanish zod error map, registered in Providers"
```

---

## Task 5: Create FormField component

**Files:**
- Create: `frontend/components/form-field.tsx`
- Create: `frontend/components/form-field.test.tsx`

**Interfaces:**
- Props: `control: Control<any>`, `name: FieldPath<any>`, `label: string`, `type?: "text" | "number" | "date"` (default `"text"`), `placeholder?: string`, `disabled?: boolean`, `min?: number`, `valueAsNumber?: boolean`.
- Reads `formState.errors[name]` and renders `<p className="text-xs text-destructive">` when present.

**Step 1: Write failing test**

Create `frontend/components/form-field.test.tsx`:

```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useForm } from "react-hook-form"
import { describe, expect, it } from "vitest"
import { z } from "zod"
import { FormField } from "./form-field"

function Harness() {
  const schema = z.object({ name: z.string().min(1, "Requerido") })
  const { control, handleSubmit } = useForm<{ name: string }>({
    resolver: zodResolver(schema),
    defaultValues: { name: "" },
  })
  return (
    <form onSubmit={handleSubmit(() => {})}>
      <FormField control={control} name="name" label="Nombre" />
      <button type="submit">Enviar</button>
    </form>
  )
}

describe("FormField", () => {
  it("shows label", () => {
    render(<Harness />)
    expect(screen.getByText("Nombre")).toBeInTheDocument()
  })

  it("shows error after invalid submit", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole("button", { name: "Enviar" }))
    expect(await screen.findByText("Requerido")).toBeInTheDocument()
  })

  it("clears error when user types", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole("button", { name: "Enviar" }))
    await user.type(screen.getByLabelText("Nombre"), "Ana")
    expect(screen.queryByText("Requerido")).not.toBeInTheDocument()
  })
})
```

**Step 2: Run test, expect failure**

Run: `cd frontend && pnpm test components/form-field.test.tsx`

Expected: FAIL — `Cannot find module './form-field'`.

**Step 3: Implement FormField**

Create `frontend/components/form-field.tsx`:

```tsx
"use client"

import type { Control, FieldPath, FieldValues } from "react-hook-form"
import { useController } from "react-hook-form"
import { Input, Label } from "@/ui"

type Props<T extends FieldValues> = {
  control: Control<T>
  name: FieldPath<T>
  label: string
  type?: "text" | "number" | "date"
  placeholder?: string
  disabled?: boolean
  min?: number
  valueAsNumber?: boolean
}

/**
 * <Label> + <Input> + inline error. Bridges react-hook-form's `useController`
 * with our `Input` component. Use `valueAsNumber` for `<input type="number">`
 * so pasted "12abc" becomes NaN and zod rejects it.
 */
export function FormField<T extends FieldValues>({
  control,
  name,
  label,
  type = "text",
  placeholder,
  disabled,
  min,
  valueAsNumber,
}: Props<T>) {
  const {
    field,
    fieldState: { error },
  } = useController({ control, name })

  return (
    <div className="space-y-1.5">
      <Label htmlFor={field.name}>
        {label}
        <span className="text-destructive"> *</span>
      </Label>
      <Input
        id={field.name}
        type={type}
        placeholder={placeholder}
        disabled={disabled}
        min={min}
        value={valueAsNumber ? (Number.isNaN(field.value) ? "" : String(field.value)) : (field.value as string | number | undefined) ?? ""}
        onChange={(e) => {
          if (valueAsNumber) {
            const raw = e.target.value
            field.onChange(raw === "" ? Number.NaN : Number(raw))
          } else {
            field.onChange(e.target.value)
          }
        }}
        onBlur={field.onBlur}
        ref={field.ref}
        aria-invalid={error ? true : undefined}
      />
      {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
    </div>
  )
}
```

**Step 4: Run test, expect pass**

Run: `cd frontend && pnpm test components/form-field.test.tsx`

Expected: 3 passed.

**Step 5: Lint and commit**

```bash
cd frontend && pnpm biome check --write components/form-field.tsx components/form-field.test.tsx
cd /Users/angelozdev/me/quaestor && git add frontend/components/form-field.tsx frontend/components/form-field.test.tsx
git commit -m "feat(frontend): FormField bridges react-hook-form + Input with errors"
```

---

## Task 6: Migrate recurring create form

**Files:**
- Modify: `frontend/app/(app)/recurring/page.tsx`

**Interfaces:**
- Consumes: `FormField`, `useForm` from `react-hook-form`, `zodResolver` from `@hookform/resolvers/zod`, `requiredString`, `intervalCount`, `positiveCents`, `isoDate`, `optionalString` from `@/lib/schemas/primitives`.

**Step 1: Add per-form schema at top of file**

Edit `frontend/app/(app)/recurring/page.tsx`. After imports, before existing component:

```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { FormField } from "@/components/form-field"
import {
  intervalCount,
  isoDate,
  optionalString,
  positiveCents,
  requiredString,
} from "@/lib/schemas/primitives"

const recurringCreateSchema = z
  .object({
    name: requiredString,
    payee: requiredString,
    amount: positiveCents,
    currency: z.enum(["COP", "USD"]),
    category: z.string().optional(),
    intervalCount: intervalCount,
    intervalUnit: z.enum(["day", "week", "month", "year"]),
    startDate: isoDate,
    endDate: isoDate.optional().or(z.literal("")),
  })
  .refine((d) => !d.endDate || d.endDate >= d.startDate, {
    message: "Fin debe ser ≥ inicio",
    path: ["endDate"],
  })

type RecurringCreateValues = z.infer<typeof recurringCreateSchema>
```

**Step 2: Replace useState with useForm in the create form section**

In `frontend/app/(app)/recurring/page.tsx`, locate the create-form state declarations:

```tsx
const [name, setName] = useState("")
const [payee, setPayee] = useState("")
// ... etc
```

Delete all of these. Replace with:

```tsx
const createForm = useForm<RecurringCreateValues>({
  resolver: zodResolver(recurringCreateSchema),
  defaultValues: {
    name: "",
    payee: "",
    amount: Number.NaN,
    currency: "COP",
    category: "",
    intervalCount: 1,
    intervalUnit: "month",
    startDate: new Date().toISOString().slice(0, 10),
    endDate: "",
  },
})

const { register: regCreate, handleSubmit: submitCreate, formState: { errors: errCreate }, reset: resetCreate } = createForm
```

**Step 3: Replace JSX inputs with registered/FormField components**

In the create form's JSX, replace each `<Input>` and `<Label>` pair with the matching rhf pattern. Example for `name`:

Before:
```tsx
<Label>Nombre *</Label>
<Input value={name} onChange={(e) => setName(e.target.value)} />
```

After:
```tsx
<FormField control={createForm.control} name="name" label="Nombre" />
```

For the amount (uses `MoneyInput`, keep as-is, wire via `setValue`):

Replace:
```tsx
<MoneyInput currency={currency} value={amount} onChange={setAmount} />
```

With:
```tsx
<Controller
  control={createForm.control}
  name="amount"
  render={({ field, fieldState: { error } }) => (
    <div className="space-y-1.5">
      <Label>Monto * ({createForm.watch("currency")})</Label>
      <MoneyInput
        currency={createForm.watch("currency")}
        value={typeof field.value === "number" && Number.isFinite(field.value) ? field.value : null}
        onChange={(cents) => field.onChange(cents ?? Number.NaN)}
      />
      {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
    </div>
  )}
/>
```

(Note: above uses `<Controller>` from `react-hook-form`; add `Controller` to the rhf import.)

For `intervalCount` (the buggy field):

Before:
```tsx
<Input
  type="number"
  min={1}
  value={count === null ? "" : String(count)}
  onChange={(e) => setCount(e.target.value === "" ? null : Number(e.target.value))}
/>
```

After:
```tsx
<FormField
  control={createForm.control}
  name="intervalCount"
  label="Cada (cantidad)"
  type="number"
  min={1}
  valueAsNumber
/>
```

For the date fields, use FormField with `type="date"`. For `intervalUnit` (select), use a plain `<select>` registered via `{...regCreate("intervalUnit")}`.

**Step 4: Replace the submit handler**

Find:
```tsx
function submitCreate() {
  // ...
}
```

Replace with:
```tsx
const onCreateSubmit = submitCreate((values) => {
  createMut.mutate({
    name: values.name,
    payee: values.payee,
    amount: values.amount,
    currency: values.currency,
    category: values.category || undefined,
    interval_unit: values.intervalUnit,
    interval_count: values.intervalCount,
    start_date: values.startDate,
    end_date: values.endDate || undefined,
  })
  resetCreate()
})
```

Wire the form's `onSubmit={onCreateSubmit}`. Add mutation `.onSuccess` to close the dialog (existing behavior).

**Step 5: Run typecheck and tests**

```bash
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm test
```

Expected: no type errors; existing tests pass.

**Step 6: Manual smoke (optional, but recommended)**

Run `pnpm dev`, open Recurring page, try typing "abc" in the Cada field, click Guardar. Expect "Solo números" error. Submit valid input. Expect row appears.

**Step 7: Lint and commit**

```bash
cd frontend && pnpm biome check --write 'app/(app)/recurring/page.tsx'
cd /Users/angelozdev/me/quaestor && git add frontend/app/\(app\)/recurring/page.tsx
git commit -m "feat(frontend): zod-validated recurring create form (fixes interval_count bug)"
```

---

## Task 7: Migrate recurring edit form

**Files:**
- Modify: `frontend/app/(app)/recurring/page.tsx`

**Step 1: Add edit schema after create schema**

```tsx
const recurringEditSchema = recurringCreateSchema
type RecurringEditValues = z.infer<typeof recurringEditSchema>
```

**Step 2: Replace edit useState block**

Find the edit-form `useState` block (same pattern as create). Replace with `useForm<RecurringEditValues>` with `defaultValues` from the row being edited:

```tsx
const editForm = useForm<RecurringEditValues>({
  resolver: zodResolver(recurringEditSchema),
  defaultValues: {
    name: "", payee: "", amount: Number.NaN, currency: "COP",
    category: "", intervalCount: 1, intervalUnit: "month",
    startDate: "", endDate: "",
  },
})

const { register: regEdit, handleSubmit: submitEdit, formState: { errors: errEdit }, reset: resetEdit } = editForm
```

**Step 3: Reseed on edit open**

Inside the existing edit-open effect (or the existing `if (open !== prevOpen)` derived-during-render block), replace direct state setters with:

```tsx
if (open && row) {
  resetEdit({
    name: row.name,
    payee: row.payee,
    amount: row.amount,
    currency: row.currency,
    category: row.category ?? "",
    intervalCount: row.interval_count,
    intervalUnit: row.interval_unit,
    startDate: row.start_date,
    endDate: row.end_date ?? "",
  })
}
```

**Step 4: Replace edit JSX with FormField pattern**

Same as Task 6 step 3, using `editForm.control`.

**Step 5: Replace edit submit**

```tsx
const onEditSubmit = submitEdit((values) => {
  updateMut.mutate({ id: row!.id, ... })
})
```

**Step 6: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write 'app/(app)/recurring/page.tsx' && pnpm test
cd /Users/angelozdev/me/quaestor && git add frontend/app/\(app\)/recurring/page.tsx
git commit -m "feat(frontend): zod-validated recurring edit form"
```

---

## Task 8: Migrate transaction-create-dialog

**Files:**
- Modify: `frontend/components/transaction-create-dialog.tsx`

**Step 1: Add schema and form hook at top of component**

After imports:

```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"
import { FormField } from "@/components/form-field"
import { positiveCents, isoDate, optionalString } from "@/lib/schemas/primitives"

const txCreateSchema = z.object({
  type: z.enum(["expense", "income"]),
  payee: requiredString,
  amount: positiveCents,
  currency: z.enum(["COP", "USD"]),
  category: z.string().optional(),
  date: isoDate,
  fxRate: z.number().positive().optional().or(z.literal(Number.NaN)),
  notes: optionalString,
})
type TxCreateValues = z.infer<typeof txCreateSchema>
```

Add `requiredString` to the primitives import list. Inside the component:

```tsx
const form = useForm<TxCreateValues>({
  resolver: zodResolver(txCreateSchema),
  defaultValues: {
    type: "expense",
    payee: "",
    amount: Number.NaN,
    currency: "COP",
    category: "",
    date: new Date().toISOString().slice(0, 10),
    fxRate: Number.NaN,
    notes: "",
  },
})
```

**Step 2: Replace each existing `<Input>` with FormField or Controller**

Payee, amount (Controller + MoneyInput), date → FormField. fxRate input → FormField with `valueAsNumber`. Notes → FormField.

**Step 3: Replace submit handler**

```tsx
const onSubmit = form.handleSubmit((values) => {
  createMut.mutate({
    type: values.type,
    payee: values.payee,
    amount: values.amount,
    currency: values.currency,
    category: values.category || undefined,
    date: values.date,
    fx_rate: Number.isFinite(values.fxRate) ? values.fxRate : undefined,
    notes: values.notes || undefined,
  })
  form.reset()
})
```

**Step 4: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write components/transaction-create-dialog.tsx
cd /Users/angelozdev/me/quaestor && git add frontend/components/transaction-create-dialog.tsx
git commit -m "feat(frontend): zod-validated transaction create dialog"
```

---

## Task 9: Migrate transaction-edit-dialog

**Files:**
- Modify: `frontend/components/transaction-edit-dialog.tsx`

**Step 1: Add edit schema**

```tsx
const txEditSchema = txCreateSchema
type TxEditValues = z.infer<typeof txEditSchema>
```

**Step 2: Reseed on open with current tx**

Use the same derived-during-render pattern (or existing `useEffect`) to call `form.reset({...currentTx})` when the dialog opens.

**Step 3: Replace inputs with FormField (same as Task 8)**

**Step 4: Wire submit to updateMut**

```tsx
const onSubmit = form.handleSubmit((values) => {
  updateMut.mutate({ id: tx.id, ...values })
})
```

**Step 5: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write components/transaction-edit-dialog.tsx
cd /Users/angelozdev/me/quaestor && git add frontend/components/transaction-edit-dialog.tsx
git commit -m "feat(frontend): zod-validated transaction edit dialog"
```

---

## Task 10: Migrate budgets page

**Files:**
- Modify: `frontend/app/(app)/budgets/page.tsx`

**Step 1: Add schema**

```tsx
const assignBudgetSchema = z.object({
  category: requiredString,
  amount: positiveCents,
  yearMonth: z.string().regex(/^\d{4}-\d{2}$/, "Mes inválido"),
})
```

**Step 2: Replace inline assign-budget form useState with useForm**

Same pattern as Task 6.

**Step 3: Replace inputs with FormField + Controller(MoneyInput)**

**Step 4: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write 'app/(app)/budgets/page.tsx'
cd /Users/angelozdev/me/quaestor && git add frontend/app/\(app\)/budgets/page.tsx
git commit -m "feat(frontend): zod-validated budget assignment form"
```

---

## Task 11: Migrate goals page

**Files:**
- Modify: `frontend/app/(app)/goals/page.tsx`

**Step 1: Add create-goal + contribute-goal schemas**

```tsx
const createGoalSchema = z.object({
  name: requiredString,
  monthlyAmount: positiveCents,
  savingsAccount: requiredString,
  targetAmount: positiveCents.optional().or(z.literal(Number.NaN)),
  deadline: isoDate.optional().or(z.literal("")),
})

const contributeGoalSchema = z.object({
  goalId: z.number().int().positive(),
  amount: positiveCents,
  date: isoDate,
})
```

**Step 2: Replace useState in both create-goal and contribute-goal forms**

Two `useForm` hooks (one per form). Same FormField pattern.

**Step 3: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write 'app/(app)/goals/page.tsx'
cd /Users/angelozdev/me/quaestor && git add frontend/app/\(app\)/goals/page.tsx
git commit -m "feat(frontend): zod-validated goal create + contribute forms"
```

---

## Task 12: Migrate settings page (FX rate)

**Files:**
- Modify: `frontend/app/(app)/settings/page.tsx`

**Step 1: Add schema**

```tsx
const fxRateSchema = z.object({
  date: isoDate,
  usdCop: fxRate,
})
```

**Step 2: Replace useState with useForm**

**Step 3: Replace inputs with FormField (date + number)**

**Step 4: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write 'app/(app)/settings/page.tsx'
cd /Users/angelozdev/me/quaestor && git add frontend/app/\(app\)/settings/page.tsx
git commit -m "feat(frontend): zod-validated FX rate form"
```

---

## Task 13: Migrate to-pay page (plan payment)

**Files:**
- Modify: `frontend/app/(app)/to-pay/page.tsx`

**Step 1: Add schema**

```tsx
const planPaymentSchema = z.object({
  payee: requiredString,
  amount: positiveCents,
  account: requiredString,
  currency: z.enum(["COP", "USD"]),
  category: z.string().optional(),
  dueDate: isoDate,
  notes: optionalString,
})
```

**Step 2: Replace useState with useForm + FormField/Controller pattern**

**Step 3: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write 'app/(app)/to-pay/page.tsx'
cd /Users/angelozdev/me/quaestor && git add frontend/app/\(app\)/to-pay/page.tsx
git commit -m "feat(frontend): zod-validated plan-payment form"
```

---

## Task 14: Migrate entity-form-dialog (generic, last)

**Files:**
- Modify: `frontend/components/entity-form-dialog.tsx`

This is the trickiest because the component is generic and used by multiple callers (accounts, categories, tags). Approach: convert to a typed schema-driven form.

**Step 1: Add per-kind schema factory**

```tsx
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { nonNegativeCents, requiredString } from "@/lib/schemas/primitives"

function buildSchema(field: Field): z.ZodTypeAny {
  switch (field.kind) {
    case "text":
      return field.required ? requiredString : z.string().optional()
    case "number":
      return z.number().int().min(field.min ?? 0)
    case "money":
      return nonNegativeCents
    case "select":
    case "entity":
      return field.required ? requiredString : z.string().nullable().optional()
    case "checkbox":
      return z.boolean()
  }
}

function buildObjectSchema(fields: Field[]) {
  const shape: Record<string, z.ZodTypeAny> = {}
  for (const f of fields) shape[f.name] = buildSchema(f)
  return z.object(shape)
}
```

**Step 2: Replace internal useState with useForm**

```tsx
const schema = useMemo(() => buildObjectSchema(fields), [fields])
type Values = z.infer<typeof schema>
const form = useForm<Values>({
  resolver: zodResolver(schema),
  defaultValues: initialValues as Values,
})

// Reseed on open via derived-during-render (preserve existing pattern).
if (open !== prevOpen) {
  setPrevOpen(open)
  if (open) form.reset(initialValues as Values)
}
```

**Step 3: Render inputs via `form.register(field.name)` instead of local `values`**

Replace each branch (`kind === "text"`, etc.) with rhf registration:

```tsx
{field.kind === "text" && (
  <Input {...form.register(field.name)} aria-invalid={!!form.formState.errors[field.name]} />
)}
{field.kind === "number" && (
  <Input type="number" {...form.register(field.name, { valueAsNumber: true })} />
)}
```

For `money`, use Controller with `MoneyInput`. For `entity`, use Controller with `EntitySelect`. For `checkbox`, use Controller with the existing `Checkbox`. For `select`, use `form.register(field.name)`.

**Step 4: Replace `submit` with `form.handleSubmit`**

```tsx
function submit(e: React.FormEvent) {
  e.preventDefault()
  form.handleSubmit((vals) => onSubmit(vals as FormValues))()
}
```

(Keep the `e.preventDefault` because Base UI's `<form onSubmit>` doesn't always prevent default.)

**Step 5: Typecheck, lint, commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write components/entity-form-dialog.tsx && pnpm test
cd /Users/angelozdev/me/quaestor && git add frontend/components/entity-form-dialog.tsx
git commit -m "feat(frontend): zod-validated entity-form-dialog (generic)"
```

---

## Task 15: Backend Pydantic constraint hardening

**Files:**
- Modify: `backend/src/quaestor/mcp/tools/core.py`

**Step 1: Add constraints to numeric fields**

For each model below, edit the `Field(...)` call. Use Edit tool, replace the exact existing line.

`CreateRecurringInput` (search existing class, add after the `Field` for `interval_unit`):

```python
interval_count: int = Field(gt=0, le=1000, description="How many units per interval")
```

`CreateGoalInput`:

```python
monthly_amount: int = Field(gt=0, description="Fixed monthly amount in cents")
target_amount: int | None = Field(default=None, gt=0, description="Target in cents (defined goal)")
```

`UpdateGoalInput`:

```python
monthly_amount: int | None = Field(default=None, gt=0, description="New monthly amount in cents")
```

`UpdateRecurringInput`:

```python
amount: int | None = Field(default=None, gt=0, description="New amount in cents")
interval_count: int | None = Field(default=None, gt=0, le=1000, description="New interval count")
```

`PlanPaymentInput`:

```python
amount: int = Field(gt=0, description="Amount in cents, original currency")
```

`ContributeGoalInput` (search the file; may already exist; ensure `gt=0`):

```python
amount: int = Field(gt=0, description="Contribution amount in cents")
```

**Step 2: Verify with existing tests**

```bash
cd /Users/angelozdev/me/quaestor/backend && pwd && ls pyproject.toml uv.lock 2>/dev/null && uv run pytest tests/mcp/test_core_writes.py -q 2>&1 | tail -20
```

Expected: existing tests pass. If any existing test was sending `amount=0` expecting success, fix the test.

**Step 3: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/src/quaestor/mcp/tools/core.py
git commit -m "fix(backend): add gt/ge/le constraints to numeric MCP tool inputs"
```

---

## Task 16: Backend constraint-violation tests

**Files:**
- Modify: `backend/tests/mcp/test_core_writes.py`

**Step 1: Add failing tests at the end of the file**

```python
import pytest
from pydantic import ValidationError

# Import the input models from the module that defines them.
from quaestor.mcp.tools.core import (
    CreateGoalInput,
    CreateRecurringInput,
    PlanPaymentInput,
    SetFxRateInput,
    UpdateRecurringInput,
)


def _today():
    from datetime import date
    return date(2026, 6, 21)


def test_create_recurring_rejects_zero_count():
    with pytest.raises(ValidationError) as exc:
        CreateRecurringInput(
            name="Rent",
            payee="Landlord",
            type="expense",
            mode="auto",
            amount=100_000,
            account="Bancolombia",
            currency="COP",
            interval_unit="month",
            interval_count=0,
            start_date=_today(),
        )
    assert "interval_count" in str(exc.value)


def test_create_recurring_rejects_count_over_1000():
    with pytest.raises(ValidationError) as exc:
        CreateRecurringInput(
            name="X", payee="Y", type="expense", mode="auto",
            amount=100, account="A", currency="COP",
            interval_unit="day", interval_count=1001, start_date=_today(),
        )
    assert "interval_count" in str(exc.value)


def test_set_fx_rate_rejects_zero():
    with pytest.raises(ValidationError):
        SetFxRateInput(date=_today(), usd_cop=0)


def test_set_fx_rate_rejects_over_100000():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SetFxRateInput(date=_today(), usd_cop=100_001)


def test_create_goal_rejects_zero_monthly_amount():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CreateGoalInput(
            name="Trip", monthly_amount=0, savings_account="Savings",
        )


def test_plan_payment_rejects_zero_amount():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PlanPaymentInput(
            payee="Friend", amount=0, account="Bancolombia",
            currency="COP", due_date=_today(),
        )


def test_update_recurring_rejects_zero_count():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        UpdateRecurringInput(recurring_id=1, interval_count=0)
```

**Step 2: Run tests, expect pass**

```bash
cd backend && uv run pytest tests/mcp/test_core_writes.py -q 2>&1 | tail -20
```

Expected: 7 new tests pass.

**Step 3: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add backend/tests/mcp/test_core_writes.py
git commit -m "test(backend): Pydantic numeric constraint violations"
```

---

## Task 17: Axios interceptor exposes Pydantic field

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/client.ts`

**Step 1: Add `field` to ApiError**

Read `frontend/lib/api/types.ts` first. Find the `ApiError` class and add:

```ts
field?: string
```

**Step 2: Update interceptor to parse Pydantic detail**

Edit `frontend/lib/api/client.ts`. Inside the `err.response?.data as ...` cast, the FastAPI 422 shape is:

```ts
{ detail: { msg: string, loc: (string | number)[], type: string }[] }
```

Replace the response handler:

```ts
http.interceptors.response.use(
  (res) => (res.status === 204 ? undefined : res.data),
  (err: AxiosError) => {
    const url = err.config?.url ?? ""
    if (err.response?.status === 401 && !url.startsWith("/auth")) {
      onUnauthorized?.()
      return undefined as unknown
    }
    const data = err.response?.data as
      | { error?: string; detail?: string; msg?: string; loc?: (string | number)[] }
      | null

    let field: string | undefined
    let message: string | undefined
    let detail: string | undefined

    if (Array.isArray(data?.detail)) {
      // Pydantic 422: { detail: [{ msg, loc, type }, ...] }
      const first = data.detail[0]
      message = first?.msg
      const loc = first?.loc ?? []
      if (loc.length >= 2 && loc[0] === "body") field = String(loc[loc.length - 1])
      detail = data.detail.map((d: any) => d.msg).join("; ")
    } else if (typeof data?.detail === "string") {
      detail = data.detail
    }

    throw new ApiError(
      err.response?.status ?? 0,
      data?.error ?? message ?? "Error",
      detail ?? message ?? `Request failed (${err.response?.status})`,
      field,
    )
  },
)
```

**Step 3: Update ApiError constructor**

In `frontend/lib/api/types.ts`, add `field` as 4th constructor arg and store it.

**Step 4: Typecheck + commit**

```bash
cd frontend && pnpm tsc --noEmit && pnpm biome check --write lib/api/
cd /Users/angelozdev/me/quaestor && git add frontend/lib/api/types.ts frontend/lib/api/client.ts
git commit -m "feat(frontend): expose Pydantic field path on ApiError"
```

---

## Task 18: Wire backend field errors into form setError + final polish

**Files:**
- Modify: each form's mutation `onError` to call `form.setError(apiErr.field, { message: apiErr.message })` when `apiErr.field` is present.
- Modify: `frontend/app/providers.tsx` (no changes if zod already registered)

**Step 1: In each migrated form, update mutation onError**

Example for `recurring/page.tsx` create mutation:

```tsx
createMut.mutate(values, {
  onError: (err) => {
    if (err instanceof ApiError && err.field) {
      createForm.setError(err.field as keyof RecurringCreateValues, {
        message: err.message,
      })
    } else {
      toast.error(err instanceof Error ? err.message : "No se pudo guardar")
    }
  },
})
```

Repeat pattern for every migrated form's mutations. Import `ApiError` from `@/lib/api`.

**Step 2: Add toast import where missing**

```tsx
import { toast } from "sonner"
```

**Step 3: Final lint + test + build**

```bash
cd frontend && pnpm biome check --write . && pnpm tsc --noEmit && pnpm test
cd backend && uv run pytest -q
```

Expected: biome clean, no TS errors, all FE tests pass, all BE tests pass.

**Step 4: Manual E2E via `run` skill (recommended)**

Open each form in browser, paste "abc" in number fields, verify rejection with Spanish inline error. Submit valid data, verify persistence.

**Step 5: Commit**

```bash
cd /Users/angelozdev/me/quaestor && git add -A
git commit -m "feat(frontend): surface backend field errors via setError + toast"
```

---

## Self-Review Checklist (run before declaring done)

- [ ] Every spec requirement covered (see Spec Coverage table below).
- [ ] No `TBD` / `TODO` / "similar to Task N" anywhere in this plan.
- [ ] Type/import names match across tasks (`FormField`, `registerZodMessages`, primitive names).
- [ ] All commits use conventional-commit prefixes (`feat:`, `fix:`, `chore:`, `test:`, `docs:`).
- [ ] `biome check` and `tsc --noEmit` clean.
- [ ] `pnpm test` green.
- [ ] `uv run pytest` green.

## Spec Coverage

| Spec requirement | Task |
|---|---|
| Add `zod`, `react-hook-form`, `@hookform/resolvers` | Task 1 |
| Vitest setup | Task 2 |
| `lib/schemas/primitives.ts` with named primitives | Task 3 |
| `lib/schemas/messages.ts` Spanish error map | Task 4 |
| `FormField` component | Task 5 |
| Migrate `recurring/page.tsx` create (interval_count bug) | Task 6 |
| Migrate `recurring/page.tsx` edit | Task 7 |
| Migrate `transaction-create-dialog.tsx` | Task 8 |
| Migrate `transaction-edit-dialog.tsx` | Task 9 |
| Migrate `budgets/page.tsx` | Task 10 |
| Migrate `goals/page.tsx` | Task 11 |
| Migrate `settings/page.tsx` (FX) | Task 12 |
| Migrate `to-pay/page.tsx` (plan payment) | Task 13 |
| Migrate `entity-form-dialog.tsx` | Task 14 |
| Backend `gt`/`ge`/`le` constraints | Task 15 |
| Backend constraint-violation tests | Task 16 |
| Axios interceptor exposes `field` | Task 17 |
| Forms surface backend field errors via `setError` | Task 18 |
| Schema unit tests | Task 3 + Task 5 |
| Form schema + component tests | Tasks 5, 6–14 (smoke at minimum) |
