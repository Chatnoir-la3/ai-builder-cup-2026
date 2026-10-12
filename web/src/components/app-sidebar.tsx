"use client";

import { ListChecks, ShieldCheck, Workflow } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

export function AppSidebar({ pending }: { pending: number | null }) {
  const pathname = usePathname();
  return (
    <Sidebar>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ShieldCheck className="size-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">Payment check</div>
            <div className="text-xs text-muted-foreground">株式会社ミオリ工務店</div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Payments</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={pathname.startsWith("/approvals")}>
                  <Link href="/approvals">
                    <ListChecks />
                    <span>Approval queue</span>
                  </Link>
                </SidebarMenuButton>
                {pending !== null && <SidebarMenuBadge>{pending}</SidebarMenuBadge>}
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>About</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={pathname.startsWith("/how-it-works")}>
                  <Link href="/how-it-works">
                    <Workflow />
                    <span>How it works</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="flex size-8 items-center justify-center rounded-full bg-muted text-xs font-medium">鈴木</div>
          <div className="leading-tight">
            <div className="text-sm font-medium">鈴木 花子</div>
            <div className="text-xs text-muted-foreground">Accounts payable · fictional data</div>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
