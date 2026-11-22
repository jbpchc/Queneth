import type { Metadata } from "next";

import { ReviewsView } from "./reviews-view";

export const metadata: Metadata = { title: "Reviews", robots: { index: false } };

export default function ReviewsPage() {
  return <ReviewsView />;
}
