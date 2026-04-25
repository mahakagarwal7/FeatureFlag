import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    // Turbopack settings for Next.js 15+
  },
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;
