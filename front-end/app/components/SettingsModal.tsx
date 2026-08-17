"use client";

import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import type {User} from "../models/user";

type SettingsModalProps = {
  open: boolean;
  user: User;
  onOpenChange: (open: boolean) => void;
};

export function SettingsModal({
  open,
  user,
  onOpenChange,
}: SettingsModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configurações</DialogTitle>
          <DialogDescription>Informações da conta atual.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <p className="text-sm">{user.name}</p>
          <p className="text-sm text-muted-foreground">{user.role}</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
