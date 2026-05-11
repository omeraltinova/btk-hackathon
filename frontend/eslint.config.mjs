import { FlatCompat } from "@eslint/eslintrc";
import { dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      // WHY: TS strict mode already catches most `any` slips; we keep the rule
      // on but with a TODO escape hatch (eslint-disable-next-line) for places
      // a justified inline comment is required.
      "@typescript-eslint/no-explicit-any": "warn",
      // WHY: Turkish text uses apostrophes constantly ("Cüzdan Koçu'na",
      // "Day 2'de"). React renders them correctly without HTML entity
      // escaping, and forcing &apos; would make every Turkish string ugly.
      "react/no-unescaped-entities": "off",
    },
  },
  {
    ignores: [".next/**", "node_modules/**", "*.config.mjs", "next-env.d.ts"],
  },
];

export default eslintConfig;
