import type { Metadata } from "next";
import { Suspense } from "react";

import { ProductWizard } from "@/components/studio/wizard/product-wizard";

export const metadata: Metadata = { title: "Add a product", robots: { index: false } };

export default function NewProductPage() {
  return (
    <Suspense>
      <ProductWizard productId={null} />
    </Suspense>
  );
}
