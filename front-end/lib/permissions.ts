import type { User } from "@/app/models/user";

export function isAdmin(user: User | null | undefined) {
  return user?.role === "ADMIN" || user?.role === "SUPER";
}

export function canNavigateFromSystem() {
  return window.dispatchEvent(new Event("system:before-navigate", { cancelable: true }));
}
