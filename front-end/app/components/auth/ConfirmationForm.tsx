"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel } from "@/components/ui/field";
import { authRequest } from "@/lib/auth-client";
import { AuthFrame } from "./AuthFrame";
export function ConfirmationForm({ registration }: { registration: string }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [seconds, setSeconds] = useState(60);
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(
      () => setSeconds((s) => Math.max(0, s - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authRequest("register/confirm", {
        registration_id: registration,
        code,
      });
      router.replace("/login");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
    } finally {
      setBusy(false);
    }
  }
  async function resend() {
    setBusy(true);
    setError("");
    try {
      await authRequest("register/resend", { registration_id: registration });
      setSeconds(60);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame
      title="Confirmar cadastro"
      description="Digite o código de 3 dígitos enviado ao seu e-mail. Ele vale por 10 minutos."
    >
      <form className="grid gap-4" onSubmit={submit}>
        <Field>
          <FieldLabel htmlFor="code">Código de confirmação</FieldLabel>
          <Input
            id="code"
            value={code}
            onChange={(e) =>
              setCode(e.target.value.replace(/\D/g, "").slice(0, 3))
            }
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{3}"
            maxLength={3}
            required
            className="text-center text-2xl tracking-[.5em]"
          />
        </Field>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy || code.length !== 3}>
          Confirmar
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={busy || seconds > 0}
          onClick={resend}
        >
          {seconds > 0 ? `Reenviar em ${seconds}s` : "Reenviar código"}
        </Button>
      </form>
    </AuthFrame>
  );
}
