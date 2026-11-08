import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { ArchTwinAuth } from "@/lib/auth";
import { router } from "@/router";
import "./styles.css";

document.documentElement.setAttribute("data-theme", localStorage.getItem("at-theme") ?? "light");
const qc = new QueryClient({ defaultOptions: { queries: { retry: (n, e: any) => n < 2 && !(e?.status >= 400 && e?.status < 500), refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(<StrictMode>
  <ArchTwinAuth><QueryClientProvider client={qc}><RouterProvider router={router} /><Toaster richColors position="bottom-right" /></QueryClientProvider></ArchTwinAuth>
</StrictMode>);
