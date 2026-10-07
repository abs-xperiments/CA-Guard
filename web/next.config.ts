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

  async headers() {
    return [{ source: "/:path*", headers: securityHeaders() }];
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

/**
 * Headers on every response. The CSP is production-only because the dev server
 * evaluates code at runtime. 'unsafe-inline' for scripts is what Next's inline
 * bootstrap needs without a nonce-issuing middleware; React escapes all
 * rendered text, and the policy still forbids every other origin, framing,
 * plugins and form posts elsewhere.
 */
function securityHeaders() {
  const headers = [
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    // Ignored by browsers over plain http, so harmless on a local install.
    { key: "Strict-Transport-Security", value: "max-age=31536000" },
  ];
  if (process.env.NODE_ENV === "production") {
    headers.push({
      key: "Content-Security-Policy",
      value: [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
      ].join("; "),
    });
  }
  return headers;
}

export default config;
