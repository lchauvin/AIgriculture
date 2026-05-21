/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The backend lives at a different origin in dev (FastAPI on :8008).
  // Production deployments will use their own ingress / reverse proxy.
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8008",
  },
};

export default nextConfig;
