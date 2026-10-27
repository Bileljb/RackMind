import type { NextConfig } from "next";

// Where the Next.js server reaches FastAPI. In Docker Compose this is `http://api:8000`.
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // `next build` also writes a self-contained server to .next/standalone (used by the
  // production Docker image), so the image doesn't need a full node_modules install.
  output: "standalone",
  // Compression happens in the reverse proxy (Caddy) in production. Next's own gzip could
  // buffer the /api/stream Server-Sent Events, delaying live updates.
  compress: false,
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
