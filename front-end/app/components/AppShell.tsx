"use client";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import {
  SidebarInset,
  SidebarProvider as UiSidebarProvider,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "./auth/AuthProvider";
import { SidebarProvider } from "./sidebar/SidebarProvider";
import { AppSidebar } from "./sidebar/AppSidebar";
export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const accountPage = /^\/(login|cadastro|recuperar-senha|conta)(\/|$)/.test(
    path,
  );
  return (
    <AuthProvider>
      <TooltipProvider>
        {accountPage ? (
          children
        ) : (
          <SidebarProvider>
            <UiSidebarProvider
              className="app-glass-background"
              style={
                {
                  "--sidebar-width": "17.5rem",
                  "--sidebar-width-icon": "3.5rem",
                } as React.CSSProperties
              }
            >
              <AppSidebar />
              <SidebarInset className="h-dvh min-w-0 overflow-hidden bg-transparent!">
                <div className="h-dvh min-w-0 flex-1 overflow-hidden">
                  {children}
                </div>
              </SidebarInset>
            </UiSidebarProvider>
          </SidebarProvider>
        )}
        <Toaster position="top-right" />
      </TooltipProvider>
    </AuthProvider>
  );
}
