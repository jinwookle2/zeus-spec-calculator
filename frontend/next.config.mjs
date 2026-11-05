/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_URL || "http://localhost:8000";
export default {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
    ];
  },
};
