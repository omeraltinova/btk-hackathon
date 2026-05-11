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
};

export default nextConfig;
