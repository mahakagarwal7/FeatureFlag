"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ExperimentsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/monitoring");
  }, [router]);

  return (
    <div className="flex-1 p-8 text-sm text-muted-foreground">Redirecting…</div>
  );
}
