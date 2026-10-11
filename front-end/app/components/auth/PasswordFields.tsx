import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
export function PasswordFields({
  confirm = false,
  current = false,
}: {
  confirm?: boolean;
  current?: boolean;
}) {
  return (
    <>
      {current && (
        <Field>
          <FieldLabel htmlFor="current-password">Senha atual</FieldLabel>
          <Input
            id="current-password"
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
          />
        </Field>
      )}
      <Field>
        <FieldLabel htmlFor="password">
          {confirm ? "Nova senha" : "Senha"}
        </FieldLabel>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete={confirm ? "new-password" : "current-password"}
          minLength={confirm ? 8 : undefined}
          required
        />
      </Field>
      {confirm && (
        <Field>
          <FieldLabel htmlFor="confirm-password">Confirmar senha</FieldLabel>
          <Input
            id="confirm-password"
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </Field>
      )}
    </>
  );
}
