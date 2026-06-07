import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chat Academico",
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
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
