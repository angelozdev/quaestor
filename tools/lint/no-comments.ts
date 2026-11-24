import { defineRule } from '@oxlint/plugins'

export const noComments = defineRule({
  meta: { type: 'problem', docs: { description: 'Code carries no comments; names explain it' } },
  create(context) {
    return {
      Program() {
        for (const comment of context.sourceCode.getAllComments()) {
          if (comment.type === 'Shebang') continue
          context.report({
            node: comment,
            message: 'Remove the comment; let names and extracted functions explain the code',
          })
        }
      },
    }
  },
})
