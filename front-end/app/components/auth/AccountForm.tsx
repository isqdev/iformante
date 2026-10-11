"use client";
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { authRequest } from "@/lib/auth-client";
import { useAuth } from "./AuthProvider";
import { AuthFrame } from "./AuthFrame";
import { EmailField } from "./EmailField";
import { PasswordFields } from "./PasswordFields";
export function AccountForm({ signup = false }: { signup?: boolean }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { refresh, user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!signup && !loading && user) router.replace("/");
  }, [signup, loading, user, router]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (signup) {
        const result = await authRequest<{ registration_id: string }>(
          "register",
          { ...fields, email },
        );
        router.push(
          `/cadastro/confirmar?registration=${encodeURIComponent(result.registration_id)}`,
        );
      } else {
        await authRequest("login", { ...fields, email });
        await refresh();
        router.push("/");
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
    } finally {
      setBusy(false);
    }
  }
  if (!signup && (loading || user)) {
    return (
      <main className="app-glass-background flex min-h-dvh items-center justify-center p-4" role="status" aria-label="Verificando sessão">
        <div className="flex w-full max-w-md flex-col gap-4 rounded-xl border bg-card p-6">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </main>
    );
  }
  return (
    <AuthFrame
      title={signup ? "Criar conta" : "Entrar"}
      description={
        signup
          ? "Use seu e-mail institucional para confirmar o cadastro."
          : "Entre para guardar suas conversas por uma semana."
      }
    >
      <form className="grid gap-4" onSubmit={submit}>
        {signup && (
          <Field>
            <FieldLabel htmlFor="name">Nome</FieldLabel>
            <Input
              id="name"
              name="name"
              autoComplete="name"
              required
              maxLength={120}
            />
          </Field>
        )}
        <EmailField value={email} onChange={setEmail} />
        <PasswordFields confirm={signup} />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy}>
          {busy ? "Aguarde..." : signup ? "Enviar código" : "Entrar"}
        </Button>
        {!signup && (
          <Link
            className="text-center text-sm hover:underline"
            href="/recuperar-senha"
          >
            Esqueci minha senha
          </Link>
        )}
        <Link
          className="text-center text-sm hover:underline"
          href={signup ? "/login" : "/cadastro"}
        >
          {signup ? "Já tenho uma conta" : "Criar conta"}
        </Link>
      </form>
    </AuthFrame>
  );
}
