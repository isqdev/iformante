"use client";

import {type MouseEvent} from "react";
import {Button, Modal, type UseOverlayStateReturn} from "@heroui/react";

import type {User} from "../models/user";

type SettingsModalProps = {
  state: UseOverlayStateReturn;
  user: User;
};

export function SettingsModal({state, user}: SettingsModalProps) {
  function stopModalClickPropagation(event: MouseEvent) {
    event.stopPropagation();
  }

  return (
    <Modal state={state}>
      <Modal.Backdrop
        className="bg-backdrop"
        isDismissable
        onClick={state.close}
      >
        <Modal.Container
          className="flex min-h-screen items-center justify-center p-4"
          placement="center"
        >
          <Modal.Dialog
            className="w-[min(92vw,28rem)] rounded-2xl bg-overlay p-6 shadow-overlay"
            onClick={stopModalClickPropagation}
          >
            <Modal.Header>
              <Modal.Heading>Configuracoes</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <div className="space-y-2">
                <p className="text-sm">{user.name}</p>
                <p className="text-sm text-muted">
                  {user.role}
                </p>
              </div>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="ghost" onPress={state.close}>
                Fechar
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}
