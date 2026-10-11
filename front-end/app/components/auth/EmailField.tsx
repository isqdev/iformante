"use client";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { completeInstitutionalEmail } from "@/lib/auth-client";
export function EmailField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field>
      <FieldLabel htmlFor="auth-email">E-mail institucional</FieldLabel>
      <Input
        id="auth-email"
        name="email"
        type="email"
        autoComplete="email"
        required
        maxLength={255}
        value={value}
        onChange={(event) =>
          onChange(completeInstitutionalEmail(event.target.value))
        }
      />
    </Field>
  );
}
