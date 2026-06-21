"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Toaster } from "@/ui";
import { setUnauthorizedHandler } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
  );

  useEffect(() => {
    setUnauthorizedHandler(() => {
      client.clear();
      router.replace("/login");
      router.refresh();
    });
    return () => setUnauthorizedHandler(null);
  }, [client, router]);

  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
}
