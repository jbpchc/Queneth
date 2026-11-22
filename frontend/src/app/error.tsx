"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main id="main" className="mx-auto grid min-h-[70dvh] max-w-xl place-items-center px-4 py-16">
      <div className="flex w-full flex-col gap-4">
        <ErrorState
          title="This page stumbled"
          message="Something went wrong while loading it. Your bag and wallet are safe."
          onRetry={reset}
        />
        <Button asChild variant="ghost" className="self-center">
          <Link href="/">Return home</Link>
        </Button>
        {error.digest && (
          <p className="text-center text-caption text-ink-muted">Reference: {error.digest}</p>
        )}
      </div>
    </main>
  );
}
