"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { systemRequest, SystemRequestError } from "@/lib/system-client";

export function RoleDialog({ role, onClose, onAccessLost }: { role: "ADMIN" | "SUPER"; onClose: () => void; onAccessLost: () => void }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const promoting = role === "SUPER";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await systemRequest<{ message: string }>("users/role", { email: email.trim(), role });
      toast.success(result.message);
      onClose();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
      if (error instanceof SystemRequestError && [401, 403].includes(error.status)) onAccessLost();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose(); }}>
      <DialogContent showCloseButton={!busy}>
        <DialogHeader>
          <DialogTitle>{promoting ? "Promover usuário" : "Rebaixar usuário"}</DialogTitle>
          <DialogDescription>{promoting ? "Promova um administrador a SUPER para permitir edição de prompts e gestão de permissões." : "Rebaixe um SUPER a ADMIN. Ele continuará administrando documentos, mas perderá o acesso ao Sistema."}</DialogDescription>
        </DialogHeader>
        <form id="system-role-form" onSubmit={submit}>
          <FieldGroup>
            <Field data-invalid={!!error}>
              <FieldLabel htmlFor="system-user-email">E-mail institucional</FieldLabel>
              <Input id="system-user-email" type="email" autoComplete="email" value={email} onChange={(event) => { setEmail(event.target.value); setError(""); }} required maxLength={255} disabled={busy} aria-invalid={!!error} aria-describedby={error ? "system-role-error" : undefined} />
              {error && <p id="system-role-error" role="alert" className="text-sm text-destructive">{error}</p>}
            </Field>
          </FieldGroup>
        </form>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="system-role-form" disabled={busy || !email.trim()}>{busy && <Spinner data-icon="inline-start" />}Confirmar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
