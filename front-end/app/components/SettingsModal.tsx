"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { authRequest } from "@/lib/auth-client";
import { useAuth } from "./auth/AuthProvider";
import type { User } from "../models/user";
export function SettingsModal({
  open,
  user,
  onOpenChange,
}: {
  open: boolean;
  user: User;
  onOpenChange: (open: boolean) => void;
}) {
  const [name, setName] = useState(user.first_name);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { refresh, logout } = useAuth();
  const router = useRouter();
  async function save() {
    setBusy(true);
    setError("");
    try {
      await authRequest("profile", { name }, "PATCH");
      await refresh();
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tente novamente.");
    } finally {
      setBusy(false);
    }
  }
  async function exit() {
    setBusy(true);
    try {
      await logout();
      onOpenChange(false);
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tente novamente.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{user.first_name}</DialogTitle>
          <DialogDescription>
            {user.role === "SUPER" ? "SUPER" : user.role === "ADMIN" ? "Admin" : "Estudante"}
          </DialogDescription>
        </DialogHeader>
        <Field>
          <FieldLabel htmlFor="profile-name">Nome</FieldLabel>
          <Input
            id="profile-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={120}
          />
        </Field>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button
          variant="outline"
          onClick={() => {
            onOpenChange(false);
            router.push("/conta/alterar-senha");
          }}
        >
          Alterar senha
        </Button>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={exit}>
            Sair
          </Button>
          <Button disabled={busy || !name.trim()} onClick={save}>
            Salvar nome
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
