import type { NextConfig } from "next";

// Where the Next.js server reaches FastAPI. In Docker Compose this is `http://api:8000`.
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only ever talks to this Next.js app: `/api/racks` is proxied to
  // `${apiUrl}/racks`. Same origin means no CORS, and (Phase 5) auth cookies just work.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
