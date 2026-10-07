import type { NextConfig } from "next";

const config: NextConfig = {
  // Produces a self-contained server bundle, so the container ships the app
  // without node_modules or the build toolchain.
  output: "standalone",

  experimental: {
    // Next buffers proxied request bodies and silently truncates them at 10 MB
    // by default, which broke every ledger upload above that size while the API
    // itself accepted 200 MB. Keep this equal to MAX_UPLOAD_BYTES in
    // src/caguard/intake/readers.py so the API, not the proxy, decides.
    proxyClientMaxBodySize: "200mb",
  },

  // The API runs on this machine only. Proxying through Next keeps the browser
  // talking to one origin, so nothing needs CORS opened up.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.CAGUARD_API ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};

export default config;
