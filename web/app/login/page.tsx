"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { ApiError, auth } from "@/lib/api";
import { AuthShell, Field, FormError } from "@/components/AuthForm";
import { Button } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.login(email, password);
      router.push("/");
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not sign in just now.",
      );
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Open a client ledger and pick up where you left off."
      footer={
        <>
          Setting this up for the first time?{" "}
          <Link href="/signup" className="font-medium text-accent hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={submit}>
        {error ? <FormError message={error} /> : null}
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
          autoFocus
          placeholder="you@firm.co.in"
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />
        <Button type="submit" variant="primary" disabled={busy}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : null}
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
