import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Not found" };

export default function NotFound() {
  return (
    <main id="main" className="grain grid min-h-dvh place-items-center px-4">
      <div className="relative z-[2] flex max-w-lg flex-col items-center gap-6 text-center">
        <Logo />
        <p className="font-display text-[clamp(6rem,20vw,11rem)] leading-none text-ink/10">404</p>
        <h1 className="-mt-10 text-h1 text-ink">This piece has left the atelier.</h1>
        <p className="text-ink-muted">
          The page you&apos;re after was moved, sold out, or never existed. Let&apos;s find you
          something just as good.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild variant="primary" size="lg">
            <Link href="/">Back to Queneth</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/search">Search the collection</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
