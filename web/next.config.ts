import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ponytail: every page is dynamic (no-store fetches); Cache Components would demand a Suspense boundary per page.
  cacheComponents: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
