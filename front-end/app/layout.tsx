import type { Metadata } from "next";
import { Radley, Sora } from "next/font/google";
import { cookies } from "next/headers";
import { AppShell } from "./components/AppShell";
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
  const cookieStore = await cookies();
  const themeCookie = cookieStore.get("theme")?.value;
  const theme = themeCookie === "dark" ? "dark" : "light";

  return (
    <html
      lang="pt-BR"
      className={`${theme === "dark" ? "dark " : ""}${sora.variable} ${radley.variable} h-full font-sans antialiased`}
    >
      <body className={`${sora.className} min-h-full`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
