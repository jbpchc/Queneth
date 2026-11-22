/**
 * Navigation config.
 *
 * UX: Serial Position effect — primary nav order is New, Clothing, Shoes, Bags,
 * Accessories, Perfumes, Boutiques: strongest items first and last.
 * UX: Hick's Law — the mega-menu shows the five categories with at most 6–8
 * subcategories each. (Phase 4 swaps this static list for /catalog/categories.)
 */
export interface NavItem {
  label: string;
  href: string;
  children?: { label: string; href: string }[];
}

const sub = (category: string, names: string[]) =>
  names.map((name) => ({
    label: name,
    href: `/c/${category}/${name.toLowerCase().replace(/\s+/g, "-")}`,
  }));

export const primaryNav: NavItem[] = [
  { label: "New", href: "/search?sort=newest" },
  {
    label: "Clothing",
    href: "/c/clothing",
    children: sub("clothing", ["Dresses", "Tops", "Outerwear", "Trousers", "Knitwear", "Suiting"]),
  },
  {
    label: "Shoes",
    href: "/c/shoes",
    children: sub("shoes", ["Heels", "Sneakers", "Loafers", "Boots", "Sandals"]),
  },
  {
    label: "Bags",
    href: "/c/bags",
    children: sub("bags", ["Totes", "Shoulder", "Crossbody", "Clutches", "Backpacks"]),
  },
  {
    label: "Accessories",
    href: "/c/accessories",
    children: sub("accessories", ["Jewelry", "Watches", "Sunglasses", "Belts", "Scarves", "Hats"]),
  },
  {
    label: "Perfumes",
    href: "/c/perfumes",
    children: sub("perfumes", ["Women", "Men", "Unisex", "Niche", "Gift sets"]),
  },
  { label: "Boutiques", href: "/boutiques" },
];

export const sellerNav: NavItem[] = [
  { label: "Dashboard", href: "/seller" },
  { label: "Products", href: "/seller/products" },
  { label: "Inventory", href: "/seller/inventory" },
  { label: "Orders", href: "/seller/orders" },
  { label: "Drops", href: "/seller/drops" },
  { label: "Vouchers", href: "/seller/vouchers" },
  { label: "Reviews", href: "/seller/reviews" },
  { label: "Earnings", href: "/seller/earnings" },
  { label: "Settings", href: "/seller/settings" },
];

export const adminNav: NavItem[] = [
  { label: "Overview", href: "/admin" },
  { label: "Sellers", href: "/admin/sellers" },
  { label: "Users", href: "/admin/users" },
  { label: "Catalog", href: "/admin/catalog" },
  { label: "Moderation", href: "/admin/moderation" },
  { label: "QueWallet", href: "/admin/wallet" },
  { label: "Integrations", href: "/admin/integrations" },
  { label: "Audit log", href: "/admin/audit" },
];
