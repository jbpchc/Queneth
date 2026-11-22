"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password-input";
import { Alert, EmptyState } from "@/components/ui/states";
import { api, fieldErrors, toApiError } from "@/lib/api/client";
import { ME_KEY } from "@/lib/auth/session";

export function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const qc = useQueryClient();
  const reset = useMutation({
    mutationFn: async (password: string) => {
      const { data, error } = await api.POST("/api/v1/auth/password/reset", { body: { token, password } });
      if (error || !data) throw error;
      return data.message;
    },
    onSuccess: () => qc.setQueryData(ME_KEY, null), // every session was signed out
  });
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ password: string }>({ mode: "onBlur" });

  if (!token) {
    return (
      <EmptyState
        title="This link is incomplete"
        description="Open the link from your email again, or request a new one."
        action={
          <Button asChild variant="secondary">
            <Link href="/forgot-password">Request a new link</Link>
          </Button>
        }
      />
    );
  }

  if (reset.isSuccess) {
    return (
      <div className="flex flex-col gap-6">
        <span className="grid size-14 place-items-center rounded-full bg-success-soft text-success">
          <CircleCheck aria-hidden className="size-7" />
        </span>
        <h1 className="text-h1 text-ink">Password updated.</h1>
        <p role="status" className="text-ink-muted">
          {reset.data} We signed you out everywhere else, just in case.
        </p>
        <Button asChild variant="primary" size="lg" block>
          <Link href="/login">Sign in</Link>
        </Button>
      </div>
    );
  }

  const apiError = reset.error ? toApiError(reset.error) : null;
  const passwordError = apiError ? fieldErrors(apiError).password : undefined;
  const tokenProblem = apiError && ["invalid_token", "token_expired"].includes(apiError.code);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-h1 text-ink">Choose a new password.</h1>
        <p className="text-ink-muted">Use 8+ characters with at least one letter and one number.</p>
      </header>
      <form noValidate className="flex flex-col gap-5" onSubmit={handleSubmit((v) => reset.mutate(v.password))}>
        {apiError && !passwordError && (
          <Alert
            tone="danger"
            action={
              tokenProblem ? (
                <Button asChild variant="outline" size="sm">
                  <Link href="/forgot-password">New link</Link>
                </Button>
              ) : undefined
            }
          >
            {apiError.message}
          </Alert>
        )}
        <Field label="New password" error={errors.password?.message ?? passwordError}>
          <PasswordInput
            autoComplete="new-password"
            autoFocus
            {...register("password", {
              required: "Choose a password.",
              validate: (v) =>
                (v.length >= 8 && /[A-Za-z]/.test(v) && /\d/.test(v)) ||
                "Use 8+ characters with a letter and a number.",
            })}
          />
        </Field>
        <Button type="submit" variant="primary" size="lg" block loading={reset.isPending}>
          Save new password
        </Button>
      </form>
    </div>
  );
}
