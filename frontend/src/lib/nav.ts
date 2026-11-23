/**
 * Navigation config.
 *
 * The storefront nav is built from the live taxonomy (`/catalog/categories`):
 * nothing here names a product or a boutique.
 * UX: Serial Position effect — New first, Boutiques last; the strongest items
 * sit at the ends.
 * UX: Hick's Law — the mega-menu lists at most 8 subcategories, the ones with
 * pieces first.
 */
export interface NavItem {
  label: string;
  href: string;
  children?: { label: string; href: string }[];
}

interface NavCategory {
  name: string;
  slug: string;
  product_count: number;
  subcategories: { name: string; slug: string; product_count: number }[];
}

export function buildPrimaryNav(categories: NavCategory[], hasDeals = false): NavItem[] {
  const items: NavItem[] = [{ label: "New", href: "/search?sort=newest" }];
  for (const c of categories) {
    const subs = [...c.subcategories]
      .sort((a, b) => Number(b.product_count > 0) - Number(a.product_count > 0))
      .slice(0, 8);
    items.push({
      label: c.name,
      href: `/c/${c.slug}`,
      children: subs.map((s) => ({ label: s.name, href: `/c/${c.slug}/${s.slug}` })),
    });
  }
  if (hasDeals) items.push({ label: "Deals", href: "/deals" });
  items.push({ label: "Boutiques", href: "/boutiques" });
  return items;
}

/** Studio sidebar entry: grouped, with an icon and a plain-language hint. */
export interface StudioNavItem {
  label: string;
  href: string;
  /** Section heading in the sidebar. */
  group: string;
  /** One line under the page title saying what the page is for. */
  hint: string;
  /** Icon name, mapped to a component in the (client) shell. */
  icon: StudioIcon;
}

export type StudioIcon =
  | "home" | "box" | "layers" | "truck" | "star" | "percent" | "ticket" | "rocket"
  | "wallet" | "settings" | "store" | "users" | "folder" | "flag" | "plug" | "scroll";

/*
 * UX: Chunking — 10 destinations in 4 named groups instead of one flat list.
 * Labels say what the page does in everyday words ("Stock", "Discount codes").
 */
export const sellerNav: StudioNavItem[] = [
  { group: "Overview", label: "Dashboard", href: "/seller", icon: "home", hint: "Today's sales, orders to ship and what needs your attention." },
  { group: "Products", label: "My products", href: "/seller/products", icon: "box", hint: "Add, edit, publish or archive the pieces in your store." },
  { group: "Products", label: "Stock", href: "/seller/inventory", icon: "layers", hint: "Update how many of each size and color you have." },
  { group: "Buyers", label: "Orders", href: "/seller/orders", icon: "truck", hint: "Accept, pack and ship what buyers ordered." },
  { group: "Buyers", label: "Reviews", href: "/seller/reviews", icon: "star", hint: "Read what buyers said and reply." },
  { group: "Promote", label: "Queneth sales", href: "/seller/promotions", icon: "percent", hint: "Put pieces on sale in site-wide events like the End of the Year Sale." },
  { group: "Promote", label: "Discount codes", href: "/seller/vouchers", icon: "ticket", hint: "Codes buyers type at checkout for money off your pieces." },
  { group: "Promote", label: "Product launches", href: "/seller/drops", icon: "rocket", hint: "Schedule new pieces to go live together, with a countdown." },
  { group: "Store", label: "Earnings", href: "/seller/earnings", icon: "wallet", hint: "Money from orders: what's available, in escrow and paid out." },
  { group: "Store", label: "Store settings", href: "/seller/settings", icon: "settings", hint: "Your store name, logo, banner, policies and contact details." },
];

export const adminNav: StudioNavItem[] = [
  { group: "Overview", label: "Overview", href: "/admin", icon: "home", hint: "Sales, orders, people and escrow across the marketplace." },
  { group: "People", label: "Sellers", href: "/admin/sellers", icon: "store", hint: "Approve new boutiques, feature or suspend stores." },
  { group: "People", label: "Users", href: "/admin/users", icon: "users", hint: "Look up accounts, roles and bans." },
  { group: "Catalog", label: "Catalog", href: "/admin/catalog", icon: "folder", hint: "Categories, picks and editorial collections." },
  { group: "Catalog", label: "Promotions", href: "/admin/promotions", icon: "percent", hint: "Schedule site-wide sales that boutiques can join." },
  { group: "Catalog", label: "Moderation", href: "/admin/moderation", icon: "flag", hint: "Reported products, reviews and stores." },
  { group: "System", label: "QueWallet", href: "/admin/wallet", icon: "wallet", hint: "The credit ledger, top-up codes and reconciliation." },
  { group: "System", label: "Integrations", href: "/admin/integrations", icon: "plug", hint: "Email, media and other connected services." },
  { group: "System", label: "Audit log", href: "/admin/audit", icon: "scroll", hint: "Every admin action, who did it and when." },
];
