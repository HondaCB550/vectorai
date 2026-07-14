import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/carosio",
        destination: "/carosio.html",
      },
    ];
  },
};

export default nextConfig;
