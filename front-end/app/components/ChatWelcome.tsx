"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandLogo } from "./BrandLogo";

const greetings = [
  "Bora falar do IF?",
  "Tem dúvidas sobre o IF?",
  "O que você quer saber do IF?",
  "Eu te explico o IF!",
  "O IF tem muita coisa né.",
  "Te ajudo a entender o IF!",
];

export function ChatWelcome() {
  const [greeting, setGreeting] = useState<string | null>(null);
  useEffect(() => {
    queueMicrotask(() => setGreeting(greetings[Math.floor(Math.random() * greetings.length)]));
  }, []);
  return (
    <div className="mb-6 flex flex-col items-center justify-center gap-4 text-center">
      <BrandLogo size={128} className="size-24 md:size-32" />
      {greeting ? <h1 className="text-3xl font-semibold">{greeting}</h1> : <Skeleton className="h-9 w-64 max-w-full" />}
    </div>
  );
}
