import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CA-Guard",
  description:
    "A private review workspace: find, understand and record decisions on unusual financial transactions.",
};

import { ToastProvider } from "@/components/Toast";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN">
      <body className="min-h-screen antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
