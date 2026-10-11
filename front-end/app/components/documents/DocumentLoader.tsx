"use client";

import { Quantum } from "ldrs/react";
import "ldrs/react/Quantum.css";

export function DocumentLoader({
  label,
}: {
  label: string;
}) {
  return (
    <div role="status" aria-label={label} className="flex items-center justify-center">
      <Quantum size="90" speed="1.75" color="var(--primary)" />
    </div>
  );
}
