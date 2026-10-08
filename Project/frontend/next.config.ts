import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: { proxyTimeout: 900_000 },
  async rewrites() {
    return [{
      source: "/api/:path*",
      destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/:path*`,
    }];
  },
};

export default nextConfig;
