import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_JP } from "next/font/google";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { listPayments } from "@/lib/payguard-server";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
// Ledger names, account holders and the originals are Japanese. The variable font is one file per
// unicode range (about 120); fixed weights would triple the downloads, and any failed one fails the build.
const notoJp = Noto_Sans_JP({ variable: "--font-noto-jp", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Payment check",
  description: "Check payment instructions against your own records before you approve a transfer.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const pending = await listPayments()
    .then((rows) => rows.filter((r) => r.status === "pending").length)
    .catch(() => null);
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${notoJp.variable} h-full antialiased`}>
      <body className="min-h-full">
        <TooltipProvider>
          <SidebarProvider>
            <AppSidebar pending={pending} />
            <SidebarInset>{children}</SidebarInset>
          </SidebarProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
