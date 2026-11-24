import { definePlugin } from '@oxlint/plugins'
import { noComments } from './no-comments.ts'

export default definePlugin({
  meta: { name: 'local' },
  rules: { 'no-comments': noComments },
})
