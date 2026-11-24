"use client";

import { Bell, LogOut, MapPin, Package, Store } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AvatarUploader } from "@/components/forms/avatar-uploader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Alert } from "@/components/ui/states";
import { api, fieldErrors, toApiError } from "@/lib/api/client";
import { useLogout, useSession, useUpdateProfile } from "@/lib/auth/session";

const tierLabel: Record<string, string> = {
  INGENUE: "Ingénue",
  AFICIONADO: "Aficionado",
  CONNOISSEUR: "Connoisseur",
  MAISON: "Maison",
};

const roleLabel = { BUYER: "Buyer", SELLER: "Seller", ADMIN: "Admin" } as const;

export function AccountOverview() {
  const { user, status, hasRole, refetch } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const logout = useLogout();

  // The proxy lets this page through on a session hint; if the API says the
  // session is gone (expired or banned), send the user to sign in.
  useEffect(() => {
    if (status === "guest") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  if (status === "loading" || status === "guest") {
    return (
      <div aria-busy="true" aria-label="Loading your account" className="flex flex-col gap-8">
        <div className="flex items-center gap-5">
          <Skeleton className="size-20 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-10 w-2/3 max-w-sm" />
            <Skeleton className="h-4 w-1/3" />
          </div>
        </div>
        <Skeleton className="h-56 w-full rounded-card" />
      </div>
    );
  }

  if (!user) {
    return <ErrorState message="We couldn't load your account." onRetry={() => refetch()} />;
  }

  return (
    <div className="flex flex-col gap-10">
      {!user.email_verified && <VerifyBanner email={user.email} />}
      <header className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <AvatarUploader name={user.name} src={user.avatar_url} size={80} />
        <div className="flex flex-1 flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Your account</p>
          <h1 className="text-h1 text-ink">{user.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            {user.roles.map((r) => (
              <Badge key={r} tone={r === "ADMIN" ? "ink" : r === "SELLER" ? "info" : "neutral"} withIcon={false}>
                {roleLabel[r]}
              </Badge>
            ))}
            {hasRole("BUYER") && (
              <Badge tone="lilac" withIcon={false}>
                {tierLabel[user.tier] ?? user.tier}
              </Badge>
            )}
          </div>
        </div>
        <Button
          variant="outline"
          loading={logout.isPending}
          onClick={async () => {
            await logout.mutateAsync();
            router.push("/");
            router.refresh();
          }}
        >
          <LogOut aria-hidden /> Sign out
        </Button>
      </header>

      <div className="grid gap-6 md:grid-cols-[1.4fr_1fr]">
        <ProfileCard name={user.name} email={user.email} verified={user.email_verified} />
        <Card>
          <CardHeader>
            <CardTitle>Inbox</CardTitle>
            <CardDescription>Order updates, drop alerts and account messages.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" block>
              <Link href="/account/notifications">
                <Bell aria-hidden /> Open inbox
              </Link>
            </Button>
          </CardContent>
        </Card>
        {hasRole("BUYER") && (
          <Card>
            <CardHeader>
              <CardTitle>Orders &amp; delivery</CardTitle>
              <CardDescription>Track what you bought and manage where it ships.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Button asChild variant="secondary" block>
                <Link href="/account/orders">
                  <Package aria-hidden /> Your orders
                </Link>
              </Button>
              <Button asChild variant="outline" block>
                <Link href="/account/addresses">
                  <MapPin aria-hidden /> Addresses
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
        {hasRole("SELLER") && (
          <Card>
            <CardHeader>
              <CardTitle>Seller Studio</CardTitle>
              <CardDescription>
                Your boutique&apos;s products, orders and earnings. A new boutique opens here once it&apos;s approved.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="secondary" block>
                <Link href="/seller">
                  <Store aria-hidden /> Open Seller Studio
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

/**
 * UX: Zeigarnik effect — an unfinished task (unconfirmed email) stays visible
 * until it's done, with the next action one tap away.
 */
function VerifyBanner({ email }: { email: string }) {
  const resend = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/auth/verify-email/resend");
      if (error || !data) throw error;
      return data.message;
    },
    onSuccess: (message) => toast.success("Link sent", { description: message }),
    onError: (err) => toast.error("Couldn't send the link", { description: toApiError(err).message }),
  });
  return (
    <Alert
      tone="warning"
      title="Confirm your email"
      action={
        <Button variant="outline" size="sm" loading={resend.isPending} onClick={() => resend.mutate()}>
          Resend link
        </Button>
      }
    >
      We sent a link to {email}. Confirming lets us send receipts and drop alerts. The link is also in
      your <Link href="/account/notifications" className="font-semibold text-accent-2 underline">inbox</Link>.
    </Alert>
  );
}

function ProfileCard({ name, email, verified }: { name: string; email: string; verified: boolean }) {
  const update = useUpdateProfile();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm<{ name: string }>({ defaultValues: { name } });

  const onSubmit = handleSubmit(async (values) => {
    try {
      const saved = await update.mutateAsync(values);
      reset({ name: saved.name });
      toast.success("Profile saved");
    } catch (err) {
      const apiError = toApiError(err);
      setError("name", { message: fieldErrors(apiError).name ?? apiError.message });
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>How you appear on reviews and parcels.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <Field label="Full name" error={errors.name?.message}>
            <Input
              autoComplete="name"
              {...register("name", {
                required: "Tell us your name.",
                minLength: { value: 2, message: "At least 2 characters." },
              })}
            />
          </Field>
          <Field label="Email" hint={verified ? "Confirmed." : "Not confirmed yet."}>
            <Input value={email} readOnly disabled />
          </Field>
          <div>
            <Button type="submit" variant="secondary" disabled={!isDirty} loading={update.isPending}>
              Save changes
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
