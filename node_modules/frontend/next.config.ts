import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    outputFileTracingRoot: path.join(process.cwd(), '../../'),
  },
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;
