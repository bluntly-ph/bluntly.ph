import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Not ours to lint. Without these, eslint walks the Python virtualenv and
    // the bundled skill scripts and reports thousands of problems in vendored
    // minified JS, burying anything real.
    "backend/**",
    ".claude/**",
    ".remember/**",
    "node_modules/**",
    // Generated from docs/openapi.json by `npm run gen:api`.
    "lib/api-types.d.ts",
  ]),
]);

export default eslintConfig;
