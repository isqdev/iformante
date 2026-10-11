import Link from "next/link";
import type { ReactNode } from "react";
import { BrandLogo } from "../BrandLogo";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
export function AuthFrame({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <main className="app-glass-background flex min-h-dvh items-center justify-center overflow-auto p-4 sm:p-8">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-6 flex items-center justify-center gap-3 text-xl font-semibold">
          <BrandLogo size={48} className="size-12" />
          InFormante
        </Link>
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>
        <Link
          href="/"
          className="mt-5 block text-center text-sm text-muted-foreground hover:underline"
        >
          Continuar sem entrar
        </Link>
      </div>
    </main>
  );
}
