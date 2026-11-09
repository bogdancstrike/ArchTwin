import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { ArchTwinAuth } from "@/lib/auth";
import { router } from "@/router";
import { useTheme } from "@/lib/theme";           // also applies the stored theme before the first render
import "./styles.css";

function ThemedToaster() {
  return <Toaster richColors position="bottom-right" theme={useTheme()} />;
}
const qc = new QueryClient({ defaultOptions: { queries: { retry: (n, e: any) => n < 2 && !(e?.status >= 400 && e?.status < 500), refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(<StrictMode>
  <ArchTwinAuth><QueryClientProvider client={qc}><RouterProvider router={router} /><ThemedToaster /></QueryClientProvider></ArchTwinAuth>
</StrictMode>);
