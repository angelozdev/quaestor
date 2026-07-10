"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useCallback, useMemo } from "react"
import { z } from "zod"

/**
 * Folds parse/validate/default and clear-on-default into one object.
 * `encode` returning null means "omit this param from the URL".
 */
export type Codec<T> = {
  decode: (raw: string | null) => T
  encode: (value: T) => string | null
}

const str = (fallback: string | null = null): Codec<string | null> => ({
  decode: (raw) => (raw && raw.length > 0 ? raw : fallback),
  encode: (value) => (value && value.length > 0 && value !== fallback ? value : null),
})

const int = (fallback: number | null = null): Codec<number | null> => {
  const schema = z.coerce.number().int()
  return {
    decode: (raw) => {
      if (raw === null || raw === "") return fallback
      const parsed = schema.safeParse(raw)
      return parsed.success ? parsed.data : fallback
    },
    encode: (value) => (value === null ? null : String(value)),
  }
}

const enumOf = <T extends string>(
  values: readonly [T, ...T[]],
  fallback: T | null = null,
): Codec<T | null> => {
  const schema = z.enum(values)
  return {
    decode: (raw) => {
      if (raw === null) return fallback
      const parsed = schema.safeParse(raw)
      return parsed.success ? parsed.data : fallback
    },
    encode: (value) => (value && value !== fallback ? value : null),
  }
}

const bool = (fallback = false): Codec<boolean> => ({
  decode: (raw) => (raw === null ? fallback : raw === "true"),
  encode: (value) => (value === fallback ? null : String(value)),
})

/** Codec factories. Domain views compose these into a schema (see lib/filter-schemas.ts). */
export const p = { str, int, enum: enumOf, bool }

type FilterValues<S extends Record<string, Codec<any>>> = {
  [K in keyof S]: S[K] extends Codec<infer T> ? T : never
}

/**
 * Reads typed filter values from the URL (source of truth) and writes changes back
 * via router.replace. `schema` MUST be a module-level constant for stable memoization.
 */
export function useUrlFilters<S extends Record<string, Codec<any>>>(schema: S) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  const values = useMemo(() => {
    const out = {} as FilterValues<S>
    for (const key in schema) {
      out[key] = schema[key].decode(searchParams.get(key)) as FilterValues<S>[typeof key]
    }
    return out
  }, [schema, searchParams])

  const replaceWith = useCallback(
    (params: URLSearchParams) => {
      const query = params.toString()
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
    },
    [router, pathname],
  )

  const patch = useCallback(
    (partial: Partial<FilterValues<S>>) => {
      const params = new URLSearchParams(searchParams.toString())
      for (const key in partial) {
        const encoded = schema[key].encode(partial[key] as never)
        if (encoded === null) params.delete(key)
        else params.set(key, encoded)
      }
      replaceWith(params)
    },
    [schema, searchParams, replaceWith],
  )

  const clear = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString())
    for (const key in schema) params.delete(key)
    replaceWith(params)
  }, [schema, searchParams, replaceWith])

  return { values, patch, clear }
}
