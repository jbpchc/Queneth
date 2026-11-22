import type { Metadata } from "next";

import { UsersView } from "./users-view";

export const metadata: Metadata = { title: "Users", robots: { index: false } };

export default function AdminUsersPage() {
  return <UsersView />;
}
