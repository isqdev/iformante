import type { Metadata } from "next";
import {Radley, Sora} from "next/font/google";
import {cookies} from "next/headers";
import {SidebarInset, SidebarProvider as UiSidebarProvider} from "@/components/ui/sidebar";
import {Toaster} from "@/components/ui/sonner";
import {TooltipProvider} from "@/components/ui/tooltip";
import {AppSidebar} from "./components/sidebar/AppSidebar";
import {SidebarProvider} from "./components/sidebar/SidebarProvider";
import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  display: "swap",
});

const radley = Radley({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-radley",
  display: "swap",
});

export const metadata: Metadata = {
  title: "InFormante",
  description:
    "Interface de chatbot academico para alunos, professores e comunidade externa.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const themeCookie = (await cookies()).get("theme")?.value;
  const theme = themeCookie === "dark" ? "dark" : "light";

  return (
    <html
      lang="pt-BR"
      className={`${theme === "dark" ? "dark " : ""}${sora.variable} ${radley.variable} h-full font-sans antialiased`}
    >
      <body className={`${sora.className} min-h-full`}>
        <SidebarProvider>
          <TooltipProvider>
            <UiSidebarProvider
              className="app-glass-background"
              style={{
                "--sidebar-width": "17.5rem",
                "--sidebar-width-icon": "3.5rem",
              } as React.CSSProperties}
            >
              <AppSidebar />
              <SidebarInset className="h-svh min-w-0 overflow-hidden bg-transparent!">
                <div className="h-svh min-w-0 flex-1 overflow-hidden">
                  {children}
                </div>
              </SidebarInset>
            </UiSidebarProvider>
            <Toaster position="top-right" />
          </TooltipProvider>
        </SidebarProvider>
      </body>
    </html>
  );
}
