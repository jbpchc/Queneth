"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Alert } from "@/components/ui/states";
import { fieldErrors, toApiError } from "@/lib/api/client";
import { safeNext } from "@/lib/auth/redirect";
import { useRegister } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

interface RegisterValues {
  name: string;
  email: string;
  password: string;
}

const rules = [
  { label: "8+ characters", test: (v: string) => v.length >= 8 },
  { label: "A letter", test: (v: string) => /[A-Za-z]/.test(v) },
  { label: "A number", test: (v: string) => /\d/.test(v) },
];

export function RegisterForm() {
  const router = useRouter();
  const next = useSearchParams().get("next");
  const signUp = useRegister();
  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<RegisterValues>({ mode: "onBlur" });
  const password = watch("password") ?? "";

  const apiError = signUp.error ? toApiError(signUp.error) : null;

  // Server-side validation is the source of truth; show its messages inline.
  useEffect(() => {
    if (!apiError) return;
    for (const [field, message] of Object.entries(fieldErrors(apiError))) {
      if (field === "name" || field === "email" || field === "password") {
        setError(field, { message });
      }
    }
  }, [apiError, setError]);

  const onSubmit = handleSubmit(async (values) => {
    try {
      await signUp.mutateAsync(values);
      router.replace(safeNext(next, "/account"));
      router.refresh();
    } catch {
      /* rendered below */
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      {apiError && apiError.code !== "validation_error" && (
        <Alert
          tone="danger"
          title="Couldn't create your account"
          action={
            apiError.code === "email_taken" ? (
              <Button asChild variant="outline" size="sm">
                <Link href="/login">Sign in</Link>
              </Button>
            ) : undefined
          }
        >
          {apiError.message}
        </Alert>
      )}
      <Field label="Full name" error={errors.name?.message}>
        <Input
          autoComplete="name"
          autoFocus
          placeholder="Isabela Reyes"
          {...register("name", {
            required: "Tell us your name.",
            minLength: { value: 2, message: "At least 2 characters." },
          })}
        />
      </Field>
      <Field label="Email" error={errors.email?.message}>
        <Input
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder="you@example.com"
          {...register("email", {
            required: "Enter your email.",
            pattern: { value: /^\S+@\S+\.\S+$/, message: "That doesn't look like an email." },
          })}
        />
      </Field>
      <Field label="Password" error={errors.password?.message}>
        <PasswordInput
          autoComplete="new-password"
          {...register("password", {
            required: "Choose a password.",
            validate: (v) => rules.every((r) => r.test(v)) || "Use 8+ characters with a letter and a number.",
          })}
        />
      </Field>
      {/* Inline checklist instead of a rules paragraph (UX: Cognitive Load). */}
      <ul aria-label="Password requirements" className="-mt-2 flex flex-wrap gap-x-4 gap-y-1 text-small">
        {rules.map((rule) => {
          const ok = rule.test(password);
          return (
            <li key={rule.label} className={cn("inline-flex items-center gap-1.5", ok ? "text-success" : "text-ink-muted")}>
              <Check aria-hidden className={cn("size-4", !ok && "opacity-30")} />
              {rule.label}
              <span className="sr-only">{ok ? "(met)" : "(not yet)"}</span>
            </li>
          );
        })}
      </ul>
      <Button type="submit" variant="primary" size="lg" block loading={signUp.isPending}>
        Create account
      </Button>
      <p className="text-center text-small text-ink-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-accent-2 underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
