"use client";
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { authRequest } from "@/lib/auth-client";
import { AuthFrame } from "./AuthFrame";
import { EmailField } from "./EmailField";
import { PasswordFields } from "./PasswordFields";
import { useAuth } from "./AuthProvider";
export function PasswordForm({
  mode,
  token = "",
}: {
  mode: "forgot" | "reset" | "change";
  token?: string;
}) {
  const [email, setEmail] = useState("");
  const [masked, setMasked] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [valid, setValid] = useState(mode !== "reset");
  const { user, loading, refresh } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (mode === "change" && !loading && !user) router.replace("/login");
    if (mode === "reset")
      void authRequest<{ masked_email: string }>("password/reset/validate", {
        token,
      })
        .then((result) => {
          setMasked(result.masked_email);
          setValid(true);
        })
        .catch((e) => setError(e.message));
  }, [mode, token, user, loading, router]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await authRequest(
        `password/${mode}`,
        mode === "forgot" ? { email } : { ...fields, token },
      );
      setMessage(result.message);
      if (mode !== "forgot") {
        await refresh();
        router.replace("/login");
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame
      title={mode === "forgot" ? "Recuperar senha" : "Alterar senha"}
      description={
        mode === "forgot"
          ? "Enviaremos um link para alterar sua senha."
          : masked
            ? `Conta ${masked}`
            : "Sua nova senha deve ter pelo menos 8 caracteres."
      }
    >
      {message ? (
        <p role="status" className="text-sm">
          {message}
        </p>
      ) : (
        <form className="grid gap-4" onSubmit={submit}>
          {mode === "forgot" ? (
            <EmailField value={email} onChange={setEmail} />
          ) : (
            <PasswordFields confirm current={mode === "change"} />
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button
            type="submit"
            disabled={busy || !valid || (mode === "change" && !user)}
          >
            {busy
              ? "Aguarde..."
              : mode === "forgot"
                ? "Enviar link"
                : "Salvar senha"}
          </Button>
        </form>
      )}
      <Link
        href="/login"
        className="mt-4 block text-center text-sm hover:underline"
      >
        Voltar para entrar
      </Link>
    </AuthFrame>
  );
}
