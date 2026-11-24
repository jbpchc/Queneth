"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Alert } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { safeNext } from "@/lib/auth/redirect";
import { homeFor, landingFor, useLogin } from "@/lib/auth/session";

interface LoginValues {
  email: string;
  password: string;
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const login = useLogin();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({ mode: "onBlur" });

  const onSubmit = handleSubmit(async (values) => {
    try {
      const user = await login.mutateAsync(values);
      router.replace(safeNext(landingFor(user, next), homeFor(user)));
      router.refresh();
    } catch {
      /* rendered from login.error below */
    }
  });

  const apiError = login.error ? toApiError(login.error) : null;

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      {next && !apiError && (
        <Alert tone="info">Sign in to continue to that page.</Alert>
      )}
      {apiError && (
        <Alert tone="danger" title={apiError.code === "rate_limited" ? "Slow down" : "Couldn't sign you in"}>
          {apiError.message}
        </Alert>
      )}
      <Field label="Email" error={errors.email?.message}>
        <Input
          type="email"
          autoComplete="email"
          inputMode="email"
          autoFocus
          placeholder="you@example.com"
          {...register("email", {
            required: "Enter your email.",
            pattern: { value: /^\S+@\S+\.\S+$/, message: "That doesn't look like an email." },
          })}
        />
      </Field>
      <Field label="Password" error={errors.password?.message}>
        <PasswordInput
          autoComplete="current-password"
          {...register("password", { required: "Enter your password." })}
        />
      </Field>
      <Link
        href="/forgot-password"
        className="-mt-2 inline-flex min-h-11 items-center self-end text-small font-semibold text-accent-2 underline-offset-4 hover:underline"
      >
        Forgot password?
      </Link>
      {/* UX: Fitts's Law — full-width 48px primary action. Von Restorff: the only accent CTA here. */}
      <Button type="submit" variant="primary" size="lg" block loading={login.isPending}>
        Sign in
      </Button>
      <p className="text-center text-small text-ink-muted">
        New to Queneth?{" "}
        <Link
          href={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}
          className="font-semibold text-accent-2 underline-offset-4 hover:underline"
        >
          Create an account
        </Link>
      </p>
    </form>
  );
}
