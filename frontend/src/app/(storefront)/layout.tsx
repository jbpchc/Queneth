import type { ReactNode } from "react";

import { BagSync } from "@/components/catalog/bag-sync";
import { MobileTabBar } from "@/components/layout/mobile-tab-bar";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { getDeals, getNavCategories } from "@/lib/catalog";
import { buildPrimaryNav } from "@/lib/nav";

export default async function StorefrontLayout({ children }: { children: ReactNode }) {
  // Nav mirrors the live taxonomy; "Deals" appears only while something is on sale.
  const [categories, deals] = await Promise.all([getNavCategories(), getDeals()]);
  const nav = buildPrimaryNav(categories, deals.promotions.length + deals.on_sale.length > 0);
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader nav={nav} />
      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
        {children}
      </main>
      <SiteFooter />
      <MobileTabBar />
      <BagSync />
    </div>
  );
}
