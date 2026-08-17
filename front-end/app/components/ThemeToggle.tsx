"use client";

import {useEffect, useSyncExternalStore} from "react";
import {MoonIcon, SunIcon} from "lucide-react";
import {Button} from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const THEME_CHANGE_EVENT = "informante-theme-change";

export function ThemeToggle() {
  const isDark = useSyncExternalStore(
    (onStoreChange) => {
      window.addEventListener(THEME_CHANGE_EVENT, onStoreChange);
      return () =>
        window.removeEventListener(THEME_CHANGE_EVENT, onStoreChange);
    },
    () => document.documentElement.classList.contains("dark"),
    () => false,
  );

  function toggleTheme() {
    const nextTheme = document.documentElement.classList.contains("dark")
      ? "light"
      : "dark";

    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    document.cookie = `theme=${nextTheme}; Path=/; Max-Age=${THEME_COOKIE_MAX_AGE}; SameSite=Lax`;
    window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
  }

  useEffect(() => {
    function handleThemeShortcut(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() !== "l" ||
        !event.ctrlKey ||
        !event.altKey ||
        event.metaKey ||
        event.shiftKey ||
        event.repeat
      ) {
        return;
      }

      event.preventDefault();
      toggleTheme();
    }

    window.addEventListener("keydown", handleThemeShortcut);
    return () => window.removeEventListener("keydown", handleThemeShortcut);
  }, []);

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            aria-label={isDark ? "Ativar modo claro" : "Ativar modo escuro"}
            onClick={toggleTheme}
            size="icon-lg"
            variant="ghost"
          >
            {isDark ? <SunIcon /> : <MoonIcon />}
          </Button>
        }
      />
      <TooltipContent>Ctrl + Alt + L</TooltipContent>
    </Tooltip>
  );
}
