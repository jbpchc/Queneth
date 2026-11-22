"use client";

import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/states";
import { api, toApiError } from "@/lib/api/client";

export default function ForgotPasswordPage() {
  const request = useMutation({
    mutationFn: async (email: string) => {
      const { data, error } = await api.POST("/api/v1/auth/password/forgot", { body: { email } });
      if (error || !data) throw error;
      return data.message;
    },
  });
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ email: string }>();

  if (request.isSuccess) {
    return (
      <div className="flex flex-col gap-6">
        <span className="grid size-14 place-items-center rounded-full bg-success-soft text-success">
          <MailCheck aria-hidden className="size-7" />
        </span>
        <h1 className="text-h1 text-ink">Check your inbox.</h1>
        <p role="status" className="text-ink-muted">
          {request.data}
        </p>
        <Button asChild variant="outline" size="lg" block>
          <Link href="/login">Back to sign in</Link>
        </Button>
      </div>
    );
  }

  const apiError = request.error ? toApiError(request.error) : null;
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-h1 text-ink">Forgot your password?</h1>
        <p className="text-ink-muted">Enter your email and we&apos;ll send a link to choose a new one.</p>
      </header>
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={handleSubmit((v) => request.mutate(v.email))}
      >
        {apiError && <Alert tone="danger">{apiError.message}</Alert>}
        <Field label="Email" error={errors.email?.message}>
          <Input
            type="email"
            autoComplete="email"
            autoFocus
            {...register("email", {
              required: "Enter your email.",
              pattern: { value: /^\S+@\S+\.\S+$/, message: "That doesn't look like an email." },
            })}
          />
        </Field>
        <Button type="submit" variant="primary" size="lg" block loading={request.isPending}>
          Send reset link
        </Button>
        <p className="text-center text-small text-ink-muted">
          Remembered it?{" "}
          <Link href="/login" className="font-semibold text-accent-2 underline-offset-4 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
