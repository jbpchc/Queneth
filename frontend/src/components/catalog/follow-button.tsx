"use client";

import { Check, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, toApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { formatNumber } from "@/lib/format";

/** Optimistic follow toggle (UX: Doherty Threshold). */
export function FollowButton({
  slug,
  name,
  initialFollowing,
  initialCount,
  showCount = false,
  size = "sm",
}: {
  slug: string;
  name: string;
  initialFollowing: boolean;
  initialCount: number;
  showCount?: boolean;
  size?: "sm" | "md";
}) {
  const { status, can } = useSession();
  const router = useRouter();
  const [following, setFollowing] = useState(initialFollowing);
  const [count, setCount] = useState(initialCount);
  const [busy, setBusy] = useState(false);

  // Pages render anonymously on the server; fetch this user's real state.
  const state = useQuery({
    queryKey: ["follow", slug],
    enabled: status === "authenticated",
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/catalog/boutiques/{slug}", { params: { path: { slug } } });
      return data ?? null;
    },
  });
  useEffect(() => {
    if (state.data) {
      setFollowing(state.data.is_following);
      setCount(state.data.follower_count);
    }
  }, [state.data]);

  // Hide for roles that can't follow (admins) only after hydration, so the
  // first client render matches the anonymous server render.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (mounted && status === "authenticated" && !can("boutique:follow")) return null;

  async function toggle() {
    if (status !== "authenticated") {
      toast("Sign in to follow boutiques", {
        description: "New pieces from boutiques you follow appear on your home page.",
        action: { label: "Sign in", onClick: () => router.push(`/login?next=${encodeURIComponent(location.pathname)}`) },
      });
      return;
    }
    const next = !following;
    setFollowing(next);
    setCount((c) => c + (next ? 1 : -1));
    setBusy(true);
    const res = next
      ? await api.PUT("/api/v1/catalog/boutiques/{slug}/follow", { params: { path: { slug } } })
      : await api.DELETE("/api/v1/catalog/boutiques/{slug}/follow", { params: { path: { slug } } });
    setBusy(false);
    if (res.error || !res.data) {
      setFollowing(!next);
      setCount((c) => c + (next ? -1 : 1));
      toast.error("Couldn't update", { description: toApiError(res.error).message });
      return;
    }
    setFollowing(res.data.is_following);
    setCount(res.data.follower_count);
  }

  return (
    <div className="flex items-center gap-3">
      <Button
        variant={following ? "outline" : "secondary"}
        size={size}
        onClick={toggle}
        disabled={busy}
        aria-pressed={following}
        aria-label={following ? `Unfollow ${name}` : `Follow ${name}`}
      >
        {following ? <Check aria-hidden /> : <Plus aria-hidden />}
        {following ? "Following" : "Follow"}
      </Button>
      {showCount && (
        <span className="tabular text-small text-ink-muted" aria-live="polite">
          {formatNumber(count)} followers
        </span>
      )}
    </div>
  );
}
