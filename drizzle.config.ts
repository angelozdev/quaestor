import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  dialect: 'sqlite',
  schema: './src/shell/db/**/*.schema.ts',
  out: './migrations',
})
