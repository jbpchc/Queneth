import type { Metadata } from "next";
import { Suspense } from "react";

import { ProductWizard } from "@/components/studio/wizard/product-wizard";

export const metadata: Metadata = { title: "Edit piece", robots: { index: false } };

export default async function EditProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <ProductWizard productId={id} />
    </Suspense>
  );
}
