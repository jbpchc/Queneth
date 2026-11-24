"use client";

import { Clock, Store, Wand2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { SingleImageField, type GalleryItem } from "@/components/studio/uploads";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, ErrorState } from "@/components/ui/states";
import { fieldErrors, refreshSession, toApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useApplication, useApply, type Application } from "@/lib/studio";

/**
 * Become a seller. One short form; the application then waits for review.
 * UX: Zeigarnik — the pending state stays visible on this page until decided.
 * UX: Cognitive Load — helper text says exactly what reviewers look for.
 */
export function SellView() {
  const { status, can } = useSession();
  const app = useApplication();
  const [editing, setEditing] = useState(false);

  if (status === "loading" || app.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading your application">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-96 rounded-card" />
      </div>
    );
  }
  if (app.isError) return <ErrorState message={toApiError(app.error).message} onRetry={() => app.refetch()} />;
  const a = app.data;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Sell on Queneth</p>
        <h1 className="text-h1 text-ink">Open your boutique</h1>
        <p className="max-w-2xl text-body text-ink-muted">
          Tell us about your atelier. Our team reviews every boutique by hand, usually within two working days.
        </p>
      </header>

      {a?.status === "approved" ? (
        <Approved />
      ) : !can("seller:apply") ? (
        <SellerAccountNeeded />
      ) : a?.status === "pending" && !editing ? (
        <Pending app={a} onEdit={() => setEditing(true)} />
      ) : (
        <>
          {a?.status === "rejected" && (
            <Alert tone="warning" title="Your last application wasn't approved">
              {a.rejection_reason} Update the details below and send it again.
            </Alert>
          )}
          <ApplicationForm app={a ?? null} onDone={() => setEditing(false)} />
        </>
      )}
    </div>
  );
}

/** Buyer accounts shop; a boutique needs its own seller account. */
function SellerAccountNeeded() {
  return (
    <Card className="flex flex-col items-start gap-4 p-6">
      <Store aria-hidden className="size-8 text-accent" />
      <h2 className="text-h3 text-ink">Boutiques have their own accounts</h2>
      <p className="max-w-xl text-body text-ink-muted">
        This is a shopping account. To sell on Queneth, sign out and create a seller account: choose{" "}
        <strong className="text-ink">Open a boutique</strong> when you sign up, then send this application.
      </p>
    </Card>
  );
}

function Approved() {
  const router = useRouter();
  const { refetch } = useSession();
  return (
    <Card className="flex flex-col items-start gap-4 p-6">
      <Store aria-hidden className="size-8 text-accent" />
      <h2 className="text-h3 text-ink">Your boutique is open</h2>
      <p className="text-body text-ink-muted">Add pieces, schedule drops and fulfil orders in Seller Studio.</p>
      <Button
        variant="primary"
        onClick={async () => {
          await refreshSession(); // picks up the new SELLER role
          await refetch();
          router.push("/seller");
        }}
      >
        Open Seller Studio
      </Button>
    </Card>
  );
}

function Pending({ app, onEdit }: { app: Application; onEdit: () => void }) {
  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-full bg-warning-soft text-warning"><Clock aria-hidden className="size-5" /></span>
        <div>
          <h2 className="text-h3 text-ink">{app.boutique_name} is under review</h2>
          <p className="text-small text-ink-muted">Submitted {new Date(app.created_at).toLocaleDateString("en-PH", { dateStyle: "medium" })}. We&apos;ll email you and leave a note in your inbox.</p>
        </div>
      </div>
      <ol className="flex flex-col gap-2 text-small text-ink-muted">
        <li>1. Application received ✓</li>
        <li>2. Our team reviews your boutique</li>
        <li>3. You get Seller Studio access</li>
      </ol>
      <Button variant="outline" className="self-start" onClick={onEdit}>Edit application</Button>
    </Card>
  );
}

type Errors = Partial<Record<"boutique_name" | "bio" | "return_policy" | "contact_email" | "city", string>>;

function ApplicationForm({ app, onDone }: { app: Application | null; onDone: () => void }) {
  const { user } = useSession();
  const apply = useApply();
  const [name, setName] = useState(app?.boutique_name ?? "");
  const [tagline, setTagline] = useState(app?.tagline ?? "");
  const [bio, setBio] = useState(app?.bio ?? "");
  const [policy, setPolicy] = useState(app?.return_policy ?? "");
  const [email, setEmail] = useState(app?.contact_email ?? "");
  const [city, setCity] = useState(app?.city ?? "");
  const [logo, setLogo] = useState<GalleryItem | null>(app?.logo_url ? { key: "logo", url: app.logo_url, text: "" } : null);
  const [banner, setBanner] = useState<GalleryItem | null>(app?.banner_url ? { key: "banner", url: app.banner_url, text: "" } : null);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!email && user?.email) setEmail(user.email);
  }, [user, email]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const next: Errors = {};
    if (name.trim().length < 3) next.boutique_name = "At least 3 characters.";
    if (bio.trim().length < 40) next.bio = `Tell us a little more (${bio.trim().length}/40 characters).`;
    if (policy.trim().length < 20) next.return_policy = "Describe your returns in a sentence or two.";
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) next.contact_email = "Enter an email shoppers can reach.";
    if (city.trim().length < 2) next.city = "Where do you ship from?";
    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length) return;
    try {
      await apply.mutateAsync({
        boutique_name: name,
        tagline: tagline || null,
        bio,
        return_policy: policy,
        contact_email: email.trim(),
        city,
        logo_asset_id: logo?.assetId ?? null,
        banner_asset_id: banner?.assetId ?? null,
      });
      toast.success("Application sent", { description: "We'll let you know as soon as it's reviewed." });
      onDone();
    } catch (err) {
      const api = toApiError(err);
      const fields = fieldErrors(api);
      if (api.code === "boutique_name_taken") setErrors({ boutique_name: api.message });
      else if (Object.keys(fields).length) setErrors(fields);
      else setFormError(api.message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <Card className="flex flex-col gap-5 p-6">
        {formError && <Alert tone="danger">{formError}</Alert>}
        <Field label="Boutique name" error={errors.boutique_name} hint="Shown on every piece you sell.">
          <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} />
        </Field>
        <Field label="Tagline" optional hint="One line, e.g. “Hand-finished linen from Cebu”.">
          <Input value={tagline} onChange={(e) => setTagline(e.target.value)} maxLength={160} />
        </Field>
        <Field label="About your atelier" error={errors.bio} hint="What you make, how, and where. At least 40 characters.">
          <Textarea rows={5} value={bio} onChange={(e) => setBio(e.target.value)} maxLength={2000} />
        </Field>
        <Field label="Return policy" error={errors.return_policy} hint="Shoppers see this before they buy.">
          <Textarea rows={3} value={policy} onChange={(e) => setPolicy(e.target.value)} maxLength={2000} />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Contact email" error={errors.contact_email}>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </Field>
          <Field label="City" error={errors.city} hint="Where your parcels ship from.">
            <Input value={city} onChange={(e) => setCity(e.target.value)} maxLength={80} />
          </Field>
        </div>
      </Card>
      <aside className="flex flex-col gap-5">
        <Card className="flex flex-col gap-5 p-6">
          <SingleImageField label="Logo" hint="Square, at least 400 × 400." purpose="boutique" url={logo?.url ?? null} onUploaded={setLogo} />
          <SingleImageField label="Banner" hint="Wide, at least 1500 × 500." purpose="boutique" url={banner?.url ?? null} onUploaded={setBanner} aspect="wide" />
        </Card>
        <Button type="submit" variant="primary" size="lg" loading={apply.isPending}>
          <Wand2 aria-hidden /> {app ? "Send application again" : "Send application"}
        </Button>
        <p className="text-caption text-ink-muted">All brands on Queneth are original or fictional. QueWallet credits are simulated for academic purposes and have no cash value.</p>
      </aside>
    </form>
  );
}
