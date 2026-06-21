# Zod + react-hook-form Validation for Quaestor Forms

**Date:** 2026-06-21
**Status:** Approved (brainstorming)
**Scope:** Frontend (all create/edit forms) + Backend (numeric constraint hardening)

## Problem

Several frontend forms accept non-numeric characters in fields that should be numeric only (e.g. `interval_count` in recurring, amounts in budgets/goals, FX rate). Root cause: `type="number"` allows pasted non-digit text, and parsing via `Number(e.target.value)` returns `NaN` silently — the bad value reaches state and is submitted. Backend Pydantic lacks numeric constraints on some fields (`gt=0`, `ge=0`), so even if frontend misses it, server accepts `amount=-100`.

## Goal

1. Reject invalid numeric input **before** it leaves the browser, with inline Spanish error messages.
2. Hard equivalent on backend so defense-in-depth holds.
3. Adopt zod + react-hook-form as the standard validation stack for all create/edit forms.
4. Keep refactor scope to a single PR (big-bang migration).

## Non-Goals

- Replacing Pydantic with a zod-like Python library (Pydantic is FastAPI-native; no Python port of zod exists).
- Refactoring read-only views (transaction list, reports) — only create/edit forms.
- Adding new fields or changing domain model.

## Architecture

### Frontend (Next.js 16, React 19)

**New dependencies:**
- `zod` (already transitive via zod-validation-error; promote to direct dep)
- `react-hook-form`
- `@hookform/resolvers`

**New files:**

| Path | Purpose |
|---|---|
| `frontend/lib/schemas/primitives.ts` | Reusable zod primitives: `nonNegativeCents`, `positiveCents`, `intervalCount`, `isoDate`, `yearMonth`, `requiredString(min, max)`, `optionalString(max)`. |
| `frontend/lib/schemas/messages.ts` | Spanish error strings + `zodErrorMap` exported for global registration. |
| `frontend/components/form-field.tsx` | `<Label>` + `<Input>` + error display. Props: `name`, `label`, `control` (from `useForm`), `type?`, `placeholder?`. |

**Modified files (every create/edit form):**

| Path | Form |
|---|---|
| `frontend/app/(app)/recurring/page.tsx` | Create + Edit recurring |
| `frontend/app/(app)/budgets/page.tsx` | Set monthly budget per category |
| `frontend/app/(app)/goals/page.tsx` | Create + contribute goal |
| `frontend/app/(app)/settings/page.tsx` | FX rate input |
| `frontend/app/(app)/to-pay/page.tsx` | Plan payment form |
| `frontend/components/transaction-create-dialog.tsx` | New transaction |
| `frontend/components/transaction-edit-dialog.tsx` | Edit transaction |
| `frontend/components/entity-form-dialog.tsx` | Generic account/category/etc. create |

Each form declares schema inline using primitives:

```ts
const schema = z.object({
  name: requiredString(1, 80),
  count: intervalCount,
  startDate: isoDate,
  endDate: isoDate.optional(),
}).refine(d => !d.endDate || d.endDate >= d.startDate, {
  message: "Fin debe ser ≥ inicio",
  path: ["endDate"],
});

type FormValues = z.infer<typeof schema>;
```

Hookup pattern:

```ts
const { register, handleSubmit, formState: { errors }, setValue } =
  useForm<FormValues>({ resolver: zodResolver(schema), defaultValues });

<Input {...register("count", { valueAsNumber: true })} />
<FormField name="name" label="Nombre *" control={control} />
```

**Global zod error map** registered once in `app/providers.tsx` so all schemas share Spanish messages without per-schema repetition.

### Backend (FastAPI + Pydantic)

Touch only fields missing constraints. Audit and harden in `src/quaestor/mcp/tools/core.py`:

| Field | Tool | Add |
|---|---|---|
| `amount` | `record_expense`, `record_income`, `plan_payment`, `transfer` | `gt=0` (cents must be positive) |
| `count` | `create_recurring`, `update_recurring` | `gt=0, le=1000` |
| `monthly_amount` | `create_goal`, `update_goal` | `gt=0` |
| `target_amount` | `create_goal` | `gt=0` |
| `usd_cop` | `set_fx_rate` | `gt=0, le=100000` |
| `balance` | `create_account` | `ge=0` (allow zero) |
| `amount` | `contribute_goal` | `gt=0` |

Cross-field rules (e.g. `end_date > start_date`) added via `@model_validator(mode="after")` on the relevant model, not per-field.

Pydantic error responses already surface as 422 with structured `detail` — frontend maps them to field errors via `setError` when path matches, otherwise shows toast.

## Data Flow

```
user types in Input
  ↓ register({ name: "count", valueAsNumber: true })
formState updated
  ↓ user clicks Save
handleSubmit(onValid, onInvalid)
  ↓ zodResolver(schema).safeParse(values)
  ├─ invalid → formState.errors populated → <FormField error=...> renders
  └─ valid   → onValid(values) → mutation.mutate(values)
                                          ↓
                              Pydantic validates (defense in depth)
                                          ├─ 422 → toast + setError if path matches
                                          └─ 200 → toast success + close dialog
```

**Number input handling:** `valueAsNumber: true` converts pasted "12abc" to `NaN`. zod rejects `NaN` via custom message `"Solo números enteros"`. User sees inline error before submit.

**MoneyInput:** Already parses text → cents. Wrap its `onChange` in `setValue("amount", cents, { shouldValidate: true })` — do not register it directly (it manages its own internal state).

## Error Handling

Three sources, three display channels:

1. **Schema errors** (zod, pre-submit) → inline below input via `<FormField>`. Spanish, concise.
2. **API field errors** (Pydantic 422 with field path) → `mutation.onError` maps `detail[].loc` to `setError(field, ...)`. Inline display.
3. **Generic API errors** (network, 5xx, unknown) → `toast.error()` via sonner. No field mapping.

zod error map (set globally):

| Code | Spanish |
|---|---|
| `invalid_type` (expected number, got NaN) | `"Solo números"` |
| `too_small` (min=1) | `"Debe ser ≥ 1"` |
| `invalid_string` (date) | `"Fecha inválida"` |
| `required` / `too_small` (string min=1) | `"Requerido"` |
| custom refine | per-schema |

Backend: Pydantic 422 body shape `{ detail: [{ loc: ["body", "amount"], msg: "...", type: "..." }] }` — frontend already has axios interceptor (`lib/api/client.ts`); extend it to expose `field` when `loc.length === 2` and `loc[0] === "body"`.

## Testing

### Frontend

**Schema unit tests** (`frontend/lib/schemas/primitives.test.ts` + per-schema tests):

```ts
expect(nonNegativeCents.safeParse(-1).success).toBe(false);
expect(nonNegativeCents.safeParse(0).success).toBe(true);
expect(intervalCount.safeParse(0).success).toBe(false);
expect(intervalCount.safeParse(1.5).success).toBe(false);
expect(intervalCount.safeParse(2).success).toBe(true);
expect(isoDate.safeParse("21/06/2026").success).toBe(false);
expect(isoDate.safeParse("2026-06-21").success).toBe(true);
```

**Form schema tests** (`frontend/app/(app)/recurring/schema.test.ts` and similar):

```ts
const bad = recurringSchema.safeParse({ name: "", count: 0 });
expect(bad.success).toBe(false);
const good = recurringSchema.safeParse({ name: "Rent", count: 1, startDate: "2026-06-21" });
expect(good.success).toBe(true);
```

**Component tests** (React Testing Library + happy-dom, since vitest is Next 16 default):

```ts
render(<RecurringForm onSubmit={vi.fn()} />);
await user.type(screen.getByLabelText(/cada/i), "abc");
await user.click(screen.getByRole("button", { name: /guardar/i }));
expect(await screen.findByText(/solo números/i)).toBeInTheDocument();
```

### Backend

Existing `tests/mcp/test_core_writes.py` (already modified per git status). Add constraint cases:

```python
def test_record_expense_rejects_negative():
    with pytest.raises(ValidationError) as exc:
        RecordExpenseInput(payee="X", amount=-100, account="A")
    assert "amount" in str(exc.value)

def test_create_recurring_rejects_zero_count():
    with pytest.raises(ValidationError):
        CreateRecurringInput(name="X", payee="Y", type="expense",
                             mode="auto", amount=1000, account="A",
                             currency="COP", interval_unit="month",
                             interval_count=0, start_date=date(2026,6,21))

def test_set_fx_rate_rejects_zero():
    with pytest.raises(ValidationError):
        SetFxRateInput(date=date(2026,6,21), usd_cop=0)
```

OpenAPI snapshot includes `minimum: 1` / `maximum: 1000` on relevant fields (assert via `model_json_schema()`).

### E2E (manual)

Use `run` skill: open each form in browser, paste "abc" in numeric input, verify rejection. Submit valid data, verify roundtrip persists.

## Migration Strategy

**Big-bang, single PR.** Reasons:
- User explicitly chose this scope.
- One shared primitive file + one shared FormField component means consistency upfront is cheap.
- Splitting into multiple PRs would leave half-migrated forms using two patterns.

**Order within the PR:**
1. Add deps (`package.json`).
2. Create `primitives.ts`, `messages.ts`, `form-field.tsx`.
3. Register zod error map in `providers.tsx`.
4. Migrate forms in dependency order: `recurring` → `transactions` → `budgets` → `goals` → `to-pay` → `settings` → `entity-form-dialog`.
5. Backend constraint hardening + new tests.
6. Update existing component tests that asserted old `<Input>` behavior.
7. Run `biome check` + full test suite.

## Risks

- **Bundle size:** react-hook-form + zod add ~25kb gzipped. Acceptable for desktop-first admin app.
- **Dialog refactor scope:** `transaction-create-dialog` and `entity-form-dialog` have non-trivial state (multi-step, conditional fields). Migration risks subtle regressions. Mitigation: component tests for each before/after.
- **MoneyInput integration:** Custom `setValue(..., { shouldValidate: true })` wiring is non-obvious. Add comment in `form-field.tsx` showing the pattern.
- **Backend hardening may surface latent client bugs** — clients (incl. CLI) sending `amount=0` to `record_expense` will now get 422. Audit CLI scripts before merging.

## Out of Scope (Follow-ups)

- ADR for "zod + react-hook-form as validation stack" — recommend filing after implementation lands, per CLAUDE.md.
- Unify date input UX (currently mixing native `<input type="date">` and string parsing).
- Schema codegen from Pydantic → zod (eliminate drift).
