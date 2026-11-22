"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, MailWarning } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { api, toApiError } from "@/lib/api/client";
import { ME_KEY } from "@/lib/auth/session";

/** Opened from the emailed link; confirms on arrival (works signed in or out). */
export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const qc = useQueryClient();
  const started = useRef(false);
  const verify = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/auth/verify-email", { body: { token } });
      if (error || !data) throw error;
      return data.message;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ME_KEY }),
  });

  useEffect(() => {
    // Tokens are single-use: guard against React strict-mode double effects.
    if (token && !started.current) {
      started.current = true;
      verify.mutate();
    }
  }, [token, verify]);

  if (verify.isSuccess) {
    return (
      <div className="flex flex-col gap-6">
        <span className="grid size-14 place-items-center rounded-full bg-success-soft text-success">
          <CircleCheck aria-hidden className="size-7" />
        </span>
        <h1 className="text-h1 text-ink">You&apos;re confirmed.</h1>
        <p role="status" className="text-ink-muted">
          {verify.data} Order updates and drop alerts will reach you there.
        </p>
        <Button asChild variant="primary" size="lg" block>
          <Link href="/">Start exploring</Link>
        </Button>
      </div>
    );
  }

  if (!token || verify.isError) {
    const message = token ? toApiError(verify.error).message : "This link is missing its code.";
    return (
      <div className="flex flex-col gap-6">
        <span className="grid size-14 place-items-center rounded-full bg-warning-soft text-warning">
          <MailWarning aria-hidden className="size-7" />
        </span>
        <h1 className="text-h1 text-ink">That link didn&apos;t work.</h1>
        <p role="alert" className="text-ink-muted">
          {message} Sign in and send a fresh link from your account page.
        </p>
        <Button asChild variant="secondary" size="lg" block>
          <Link href="/account">Go to your account</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 py-12 text-center" aria-busy="true">
      <Spinner className="text-h2 text-ink" label="Confirming your email" />
      <p className="text-ink-muted">Confirming your email…</p>
    </div>
  );
}
