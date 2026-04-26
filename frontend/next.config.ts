import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  /* config options here */
  output: 'export',
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;
