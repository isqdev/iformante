import type { Metadata } from "next";
import {AppSidebar} from "./components/sidebar/AppSidebar";
import {SidebarProvider} from "./components/sidebar/SidebarProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "IFormante",
  description:
    "Interface de chatbot academico para alunos, professores e comunidade externa.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full">
        <SidebarProvider>
          <AppSidebar />
          {children}
        </SidebarProvider>
      </body>
    </html>
  );
}
