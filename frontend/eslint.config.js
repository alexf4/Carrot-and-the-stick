import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    // Exclude auto-generated directories and files:
    // - .next/  : Next.js build output and generated types (next dev / next build)
    // - dist/   : generic build output
    // - next-env.d.ts : Next.js auto-generated ambient type file; uses
    //   triple-slash references that @typescript-eslint/triple-slash-reference
    //   would flag as errors.
    ignores: ['.next', 'dist', 'next-env.d.ts'],
  },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
)
