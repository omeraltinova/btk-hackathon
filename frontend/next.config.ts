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
  // WHY centralize redirects here (P2.11 in docs/decisions.md): we used to keep
  // a `page.tsx` file per stale URL whose only body was `redirect("/new/path")`.
  // Eight such files cluttered the route tree, slowed build traces, and meant a
  // route rename touched many files. Listing the same rules here keeps the
  // routing config in one place and lets stale links keep working after the
  // P2.12 flatten (everything top-level under (app)).
  async redirects() {
    return [
      // Root → overview panel.
      { source: "/", destination: "/dashboard", permanent: false },
      // P2.12 IA flatten: /dashboard/{transactions,income-expense,goals}
      // moved to top-level. Preserve any incoming query string so deep
      // links like /dashboard/goals?hedef=X keep working.
      {
        source: "/dashboard/transactions",
        destination: "/transactions",
        permanent: false,
      },
      {
        source: "/dashboard/income-expense",
        destination: "/income-expense",
        permanent: false,
      },
      { source: "/dashboard/goals", destination: "/goals", permanent: false },
      // Pre-flatten deep links inside the goals tree.
      {
        source: "/dashboard/goals/envelopes",
        destination: "/goals?sekme=zarflar",
        permanent: false,
      },
      {
        source: "/dashboard/goals/envelopes/:slug",
        destination: "/goals?zarf=:slug",
        permanent: false,
      },
      {
        source: "/dashboard/goals/:goalId",
        destination: "/goals?hedef=:goalId",
        permanent: false,
      },
      // Legacy envelope routes — already redirected pre-P2.11, now collapsed
      // into the config.
      {
        source: "/dashboard/envelopes",
        destination: "/goals?sekme=zarflar",
        permanent: false,
      },
      {
        source: "/dashboard/envelopes/:slug",
        destination: "/goals?zarf=:slug",
        permanent: false,
      },
      // /dashboard/recurring + /receipts both used to land users on the
      // transactions screen. Keep them pointing at the new flat path.
      {
        source: "/dashboard/recurring",
        destination: "/transactions",
        permanent: false,
      },
      { source: "/receipts", destination: "/transactions", permanent: false },
    ];
  },
};

export default nextConfig;
