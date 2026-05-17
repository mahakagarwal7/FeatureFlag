import { FlagDetailClient } from "./flag-client";

export function generateStaticParams() {
  // Providing few common IDs for static export
  return [
    { id: "feature-alpha" }, 
    { id: "feature-beta" }, 
    { id: "feature-gamma" },
    { id: "new-user-flow" },
    { id: "payment-gateway-v2" }
  ];
}

// Ensure the page is treated as static
export const dynamic = 'force-static';

export default function Page() {
  return <FlagDetailClient />;
}
