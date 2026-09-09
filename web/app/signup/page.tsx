"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2, ShieldCheck } from "lucide-react";
import { ApiError, auth } from "@/lib/api";
import type { SignupState } from "@/lib/types";
import { AuthShell, Field, FormError } from "@/components/AuthForm";
import { Button, Spinner } from "@/components/ui";

export default function SignupPage() {
  const router = useRouter();
  const [state, setState] = useState<SignupState | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    auth
      .signupState()
      .then(setState)
      .catch(() =>
        setError("Cannot reach CA-Guard. Is it running? Start it with: caguard serve"),
      );
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.signup({
        email,
        name,
        password,
        invite_code: invite.trim() || undefined,
      });
      router.push("/");
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not create the account.",
      );
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      // The bootstrap case is explained in the callout below, so repeating it
      // here would say the same sentence twice on one small page.
      subtitle={
        state?.needs_invite
          ? state.explanation
          : "Setting up CA-Guard for your firm."
      }
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      {state === null && !error ? (
        <Spinner label="Checking this installation…" />
      ) : (
        <form onSubmit={submit}>
          {error ? <FormError message={error} /> : null}

          {state?.state === "bootstrap" ? (
            <p className="mb-4 flex items-start gap-2 rounded-md border border-accent/20 bg-accent-soft px-3 py-2 text-[12px] text-accent">
              <ShieldCheck size={14} className="mt-0.5 shrink-0" />
              This is a new installation, so this first account becomes the
              administrator.
            </p>
          ) : null}

          <Field
            label="Your name"
            value={name}
            onChange={setName}
            autoFocus
            autoComplete="name"
            placeholder="As it should appear on review decisions"
          />
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            placeholder="you@firm.co.in"
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            hint="At least 10 characters. A phrase you will remember beats a short word with symbols."
          />
          {state?.needs_invite ? (
            <Field
              label="Invite code"
              value={invite}
              onChange={setInvite}
              hint="From whoever set CA-Guard up for your firm."
            />
          ) : null}

          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : null}
            {busy ? "Creating…" : "Create account"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
