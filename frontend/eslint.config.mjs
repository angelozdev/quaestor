import { defineConfig, globalIgnores } from "eslint/config"
import nextVitals from "eslint-config-next/core-web-vitals"
import nextTs from "eslint-config-next/typescript"

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Design system boundary (docs/adr/0002): ui/ must stay app-agnostic. It may
  // import React, generic UI libraries, and its own internals — never app or
  // domain code. This rule is the primary automated guard for that invariant.
  {
    files: ["ui/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "@/app",
                "@/app/*",
                "@/lib",
                "@/lib/*",
                "@/components",
                "@/components/*",
                "@/hooks",
                "@/hooks/*",
              ],
              message:
                "ui/ is the app-agnostic design system (docs/adr/0002): do not import app or domain code (@/app, @/lib, @/components, @/hooks). Use React, generic UI libraries, or ui/ internals only.",
            },
          ],
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
])

export default eslintConfig
