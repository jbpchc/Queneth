import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-h1 text-ink">Welcome back.</h1>
        <p className="text-ink-muted">Your wishlist, bag and wallet are right where you left them.</p>
      </header>
      <Suspense fallback={<Skeleton className="h-72 w-full" />}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
