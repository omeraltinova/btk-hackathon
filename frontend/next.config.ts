import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // WHY standalone: smaller production Docker image — only the trace-traced
  // node_modules + minimal server are copied to the runtime stage.
  output: "standalone",
  reactStrictMode: true,
  // Day 1 placeholder: no remote image hosts yet. MinIO bucket added Day 4.
  images: {
    remotePatterns: [],
  },
  // WHY ignore lint during build: ESLint 9 flat config (see `eslint.config.mjs`)
  // is wired through `@eslint/eslintrc` FlatCompat, but `next build` still uses
  // its legacy lint runner which prints a "flat-config plugin warning" on every
  // run. Lint hygiene is enforced separately via `pnpm lint` (eslint .) so the
  // build pipeline can stay quiet without losing CI coverage.
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
