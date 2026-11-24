"use client";

import { Ruler } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

// Body measurements in cm (bust, waist, hip), Queneth house standard.
const CLOTHING: [string, number, number, number][] = [
  ["XXS", 78, 60, 86], ["XS", 82, 64, 90], ["S", 86, 68, 94], ["M", 92, 74, 100],
  ["L", 98, 80, 106], ["XL", 104, 86, 112], ["XXL", 110, 92, 118],
];

export function recommendSize(bust: number, waist: number, hip: number): string | null {
  if (!bust && !waist && !hip) return null;
  // The size whose every given measurement fits; otherwise the largest needed.
  let best = 0;
  for (const [i, [, b, w, h]] of CLOTHING.entries()) {
    if ((bust && bust > b) || (waist && waist > w) || (hip && hip > h)) best = i + 1;
  }
  return CLOTHING[Math.min(best, CLOTHING.length - 1)]![0];
}

/** Clothing module: measurement table + "Find my size" helper (spec §9). */
export function SizeGuide({ fit, available }: { fit?: string; available: string[] }) {
  const [m, setM] = useState({ bust: "", waist: "", hip: "" });
  const num = (v: string) => Number(v.replace(",", ".")) || 0; // Postel's Law
  const rec = recommendSize(num(m.bust), num(m.waist), num(m.hip));
  const adjusted = rec && fit === "oversized" ? `${rec} (or one size down for a closer fit)` : rec;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="link" size="sm" className="gap-1.5">
          <Ruler aria-hidden /> Size guide
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Size guide</DialogTitle>
          <DialogDescription>Body measurements in centimetres. This piece has a {fit ?? "regular"} fit.</DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="find" className="mt-4">
          <TabsList>
            <TabsTrigger value="find">Find my size</TabsTrigger>
            <TabsTrigger value="table">Measurements</TabsTrigger>
          </TabsList>
          <TabsContent value="find" className="flex flex-col gap-5">
            <div className="grid gap-4 sm:grid-cols-3">
              {(["bust", "waist", "hip"] as const).map((k) => (
                <Field key={k} label={`${k[0]!.toUpperCase()}${k.slice(1)} (cm)`}>
                  <Input inputMode="decimal" value={m[k]} onChange={(e) => setM({ ...m, [k]: e.target.value })} placeholder="e.g. 86" />
                </Field>
              ))}
            </div>
            <div aria-live="polite" className="rounded-card bg-surface-muted p-4">
              {adjusted ? (
                <p className="text-ink">
                  We recommend <strong className="font-display text-h3">{adjusted}</strong>
                  {rec && !available.includes(rec) && <span className="block text-small text-warning">That size isn&apos;t offered in this piece.</span>}
                </p>
              ) : (
                <p className="text-small text-ink-muted">Enter one or more measurements for a recommendation.</p>
              )}
            </div>
          </TabsContent>
          <TabsContent value="table">
            <table className="w-full text-small">
              <caption className="sr-only">Body measurements by size, in centimetres</caption>
              <thead className="text-left text-caption uppercase tracking-[0.08em] text-ink-muted">
                <tr><th scope="col" className="py-2">Size</th><th scope="col">Bust</th><th scope="col">Waist</th><th scope="col">Hip</th></tr>
              </thead>
              <tbody className="tabular divide-y divide-border">
                {CLOTHING.map(([s, b, w, h]) => (
                  <tr key={s} className={cn(!available.includes(s) && "text-ink-muted")}>
                    <th scope="row" className="py-2 text-left font-semibold">{s}</th><td>{b}</td><td>{w}</td><td>{h}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
