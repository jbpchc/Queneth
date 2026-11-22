"use client";

import { Bell, BellRing } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Switch } from "@/components/ui/checkbox";
import { api, toApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";

/** "Notify me" for an upcoming drop. Opt-in only (spec §6: no notification spam). */
export function NotifyToggle({ slug, title, initial }: { slug: string; title: string; initial: boolean }) {
  const { status } = useSession();
  const router = useRouter();
  const [on, setOn] = useState(initial);
  const id = `notify-${slug}`;

  const drops = useQuery({
    queryKey: ["drops", "mine"],
    enabled: status === "authenticated",
    queryFn: async () => (await api.GET("/api/v1/catalog/drops")).data ?? [],
  });
  useEffect(() => {
    const mine = drops.data?.find((d) => d.slug === slug);
    if (mine) setOn(mine.is_subscribed);
  }, [drops.data, slug]);

  async function change(next: boolean) {
    if (status !== "authenticated") {
      toast("Sign in to get drop alerts", {
        action: { label: "Sign in", onClick: () => router.push(`/login?next=${encodeURIComponent(location.pathname)}`) },
      });
      return;
    }
    setOn(next);
    const res = next
      ? await api.PUT("/api/v1/catalog/drops/{slug}/notify", { params: { path: { slug } } })
      : await api.DELETE("/api/v1/catalog/drops/{slug}/notify", { params: { path: { slug } } });
    if (res.error) {
      setOn(!next);
      toast.error("Couldn't update the alert", { description: toApiError(res.error).message });
    } else if (next) {
      toast.success("We'll let you know", { description: `You'll get an alert when ${title} goes live.` });
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Switch id={id} checked={on} onCheckedChange={change} />
      <label htmlFor={id} className="inline-flex cursor-pointer items-center gap-2 text-small font-semibold">
        {on ? <BellRing aria-hidden className="size-4" /> : <Bell aria-hidden className="size-4" />}
        {on ? "You'll be notified" : "Notify me"}
      </label>
    </div>
  );
}
