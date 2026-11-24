"use client";

import { Search, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ReasonForm } from "@/components/admin/reason-form";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DialogDescription, DialogTitle, Sheet, SheetContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { USERS_PAGE, useAdminUser, useAdminUsers, useUserActions, type UserFilters } from "@/lib/admin";
import { useSession } from "@/lib/auth/session";
import { formatNumber, formatQc } from "@/lib/format";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" });

/**
 * People search. UX: Doherty Threshold — results update as you type (kept
 * on screen while the next page loads). Details open in a side panel so the
 * list keeps its place.
 */
export function UsersView() {
  const [f, setF] = useState<UserFilters>({ q: "", role: null, status: null, offset: 0 });
  const [open, setOpen] = useState<string | null>(null);
  const list = useAdminUsers(f);
  const set = (p: Partial<UserFilters>) => setF((cur) => ({ ...cur, offset: 0, ...p }));
  const total = list.data?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">People</p>
        <h1 className="text-h1 text-ink">Users</h1>
      </header>
      <div className="flex flex-wrap items-end gap-3">
        <label className="relative w-full sm:w-80">
          <span className="sr-only">Search by name or email</span>
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
          <Input value={f.q} onChange={(e) => set({ q: e.target.value })} placeholder="Name or email" className="pl-9" />
        </label>
        <Select aria-label="Role" value={f.role ?? ""} onChange={(e) => set({ role: (e.target.value || null) as UserFilters["role"] })} className="w-40">
          <option value="">All roles</option>
          <option value="BUYER">Buyers</option>
          <option value="SELLER">Sellers</option>
          <option value="ADMIN">Admins</option>
        </Select>
        <Select aria-label="Status" value={f.status ?? ""} onChange={(e) => set({ status: (e.target.value || null) as UserFilters["status"] })} className="w-40">
          <option value="">Any status</option>
          <option value="active">Active</option>
          <option value="banned">Banned</option>
        </Select>
        {list.data && <span className="ml-auto text-small text-ink-muted" aria-live="polite">{formatNumber(total)} {total === 1 ? "person" : "people"}</span>}
      </div>

      {list.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading users">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-14 rounded-input" />)}</div>
      ) : list.isError ? (
        <ErrorState message={toApiError(list.error).message} onRetry={() => list.refetch()} />
      ) : list.data.items.length === 0 ? (
        <EmptyState icon={Users} title="Nobody matches" description="Try part of a name or email, or clear the filters." />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-small">
            <thead className="border-b border-border text-left text-ink-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Person</th>
                <th className="py-3 font-semibold">Roles</th>
                <th className="py-3 font-semibold">Status</th>
                <th className="py-3 text-right font-semibold">Orders</th>
                <th className="py-3 text-right font-semibold">Wallet</th>
                <th className="py-3 pr-4 text-right font-semibold">Joined</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((u) => (
                <tr key={u.id} className="border-b border-border last:border-0 hover:bg-surface-muted/50">
                  <td className="px-4 py-2.5">
                    <button type="button" onClick={() => setOpen(u.id)} className="flex min-h-11 items-center gap-3 text-left hover:underline">
                      <Avatar name={u.name} src={u.avatar_url} size={32} />
                      <span className="flex flex-col"><span className="font-semibold text-ink">{u.name}</span><span className="text-caption text-ink-muted">{u.email}</span></span>
                    </button>
                  </td>
                  <td className="py-2.5"><span className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} tone={r === "ADMIN" ? "ink" : r === "SELLER" ? "info" : "neutral"} withIcon={false}>{r.toLowerCase()}</Badge>)}</span></td>
                  <td className="py-2.5"><Badge tone={u.status === "banned" ? "danger" : "success"} withIcon={false}>{u.status}</Badge></td>
                  <td className="tabular py-2.5 text-right">{u.orders}</td>
                  <td className="tabular py-2.5 text-right">{formatQc(u.wallet_qc)}</td>
                  <td className="py-2.5 pr-4 text-right text-ink-muted">{dateFmt.format(new Date(u.created_at))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {total > USERS_PAGE && (
        <nav aria-label="Pages" className="flex items-center justify-between text-small">
          <Button variant="outline" size="sm" disabled={f.offset === 0} onClick={() => setF((c) => ({ ...c, offset: Math.max(0, c.offset - USERS_PAGE) }))}>Previous</Button>
          <span className="tabular text-ink-muted">{f.offset + 1}–{Math.min(total, f.offset + USERS_PAGE)} of {total}</span>
          <Button variant="outline" size="sm" disabled={f.offset + USERS_PAGE >= total} onClick={() => setF((c) => ({ ...c, offset: c.offset + USERS_PAGE }))}>Next</Button>
        </nav>
      )}

      <Sheet open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent side="right">{open && <UserPanel id={open} />}</SheetContent>
      </Sheet>
    </div>
  );
}

type Panel = "ban" | "unban" | "roles" | null;

function UserPanel({ id }: { id: string }) {
  const { user: me } = useSession();
  const u = useAdminUser(id);
  const { setStatus, setRoles } = useUserActions();
  const [panel, setPanel] = useState<Panel>(null);
  const [roles, setRolesDraft] = useState<("BUYER" | "SELLER")[] | null>(null);

  if (u.isPending) return <div className="flex flex-col gap-3 pt-8" aria-busy="true" aria-label="Loading person"><Skeleton className="h-16 w-full" /><Skeleton className="h-40 w-full" /></div>;
  if (u.isError) return <ErrorState message={toApiError(u.error).message} onRetry={() => u.refetch()} />;
  const d = u.data;
  const isAdmin = d.roles.includes("ADMIN");
  const self = me?.id === d.id;
  const draft = roles ?? (d.roles.filter((r) => r !== "ADMIN").slice(0, 1) as ("BUYER" | "SELLER")[]);

  return (
    <div className="flex flex-col gap-5 pt-6">
      <div className="flex items-center gap-3">
        <Avatar name={d.name} src={d.avatar_url} size={56} />
        <div className="flex min-w-0 flex-col">
          <DialogTitle className="text-h3 text-ink">{d.name}</DialogTitle>
          <DialogDescription className="truncate text-small text-ink-muted">{d.email}</DialogDescription>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {d.roles.map((r) => <Badge key={r} tone="neutral" withIcon={false}>{r.toLowerCase()}</Badge>)}
        <Badge tone={d.status === "banned" ? "danger" : "success"} withIcon={false}>{d.status}</Badge>
        {!d.email_verified && <Badge tone="warning" withIcon={false}>email unverified</Badge>}
      </div>
      <dl className="grid grid-cols-2 gap-3 text-small">
        {[
          ["Orders", formatNumber(d.orders)],
          ["Spent", formatQc(d.spent_qc)],
          ["Wallet", formatQc(d.wallet_qc)],
          ["Que Points", formatNumber(d.que_points)],
          ["Reviews", formatNumber(d.reviews)],
          ["Reports made", formatNumber(d.reports_made)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-input bg-surface-muted p-3"><dt className="text-caption text-ink-muted">{k}</dt><dd className="tabular font-semibold text-ink">{v}</dd></div>
        ))}
      </dl>
      {d.boutique && (
        <p className="text-small text-ink">Boutique: <Link href={`/admin/sellers?status=${d.boutique.status}`} className="font-semibold underline">{d.boutique.name}</Link> <span className="text-ink-muted">({d.boutique.status})</span></p>
      )}
      <p className="text-caption text-ink-muted">
        Joined {dateFmt.format(new Date(d.created_at))}{d.last_login_at && ` · last sign-in ${dateFmt.format(new Date(d.last_login_at))}`}
      </p>

      {isAdmin || self ? (
        <p className="text-small text-ink-muted">{self ? "This is you." : "Admins are managed outside the app"}, so account type and bans can&apos;t be changed here.</p>
      ) : panel === "ban" ? (
        <ReasonForm label="Why ban this person? Their sessions end immediately." confirmLabel="Ban" danger
          onSubmit={(reason) => setStatus.mutateAsync({ id: d.id, status: "banned", reason }).then(() => { toast.success(`${d.name} banned`); setPanel(null); u.refetch(); })}
          onCancel={() => setPanel(null)} />
      ) : panel === "unban" ? (
        <ReasonForm label="Why lift the ban?" confirmLabel="Unban"
          onSubmit={(reason) => setStatus.mutateAsync({ id: d.id, status: "active", reason }).then(() => { toast.success(`${d.name} can sign in again`); setPanel(null); u.refetch(); })}
          onCancel={() => setPanel(null)} />
      ) : panel === "roles" ? (
        <div className="flex flex-col gap-3">
          {/* One account, one type: a buyer never sells and a seller never shops. */}
          <fieldset className="flex gap-2">
            <legend className="mb-2 text-small font-semibold text-ink">Account type</legend>
            {(["BUYER", "SELLER"] as const).map((r) => (
              <button key={r} type="button" role="radio" aria-checked={draft[0] === r} aria-pressed={draft[0] === r} onClick={() => setRolesDraft([r])}
                className="h-11 rounded-pill border border-border-strong px-4 text-small font-semibold aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-bg">
                {r === "BUYER" ? "Buyer" : "Seller"}
              </button>
            ))}
          </fieldset>
          <p className="text-caption text-ink-muted">
            {draft[0] === "SELLER"
              ? "A seller account can't shop. It applies for a boutique, and Seller Studio opens once you approve it."
              : "A buyer account shops. It can't sell or use Seller Studio."}
          </p>
          <ReasonForm label="Why change the account type?" confirmLabel="Save account type"
            onSubmit={(reason) => setRoles.mutateAsync({ id: d.id, roles: draft, reason }).then(() => { toast.success("Account type updated"); setPanel(null); setRolesDraft(null); u.refetch(); })}
            onCancel={() => { setPanel(null); setRolesDraft(null); }} />
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setPanel("roles")}>Change account type…</Button>
          {d.status === "banned"
            ? <Button variant="primary" size="sm" onClick={() => setPanel("unban")}>Unban…</Button>
            : <Button variant="danger" size="sm" onClick={() => setPanel("ban")}>Ban…</Button>}
        </div>
      )}

      {d.recent_audit.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="text-small font-semibold text-ink">Recent activity</h3>
          <ul className="flex flex-col gap-1.5 text-caption text-ink-muted">
            {d.recent_audit.map((a, i) => (
              <li key={i}><span className="font-semibold text-ink">{String(a.action)}</span> · {dateFmt.format(new Date(String(a.created_at)))}{a.reason ? ` · ${String(a.reason)}` : ""}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
