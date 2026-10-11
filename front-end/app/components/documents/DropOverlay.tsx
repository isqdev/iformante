import { Upload } from "lucide-react";
export function DropOverlay() {
  return (
    <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center bg-background/90 p-6 backdrop-blur-lg">
      <div className="flex w-full max-w-xl flex-col items-center gap-5 rounded-3xl border-2 border-dashed border-primary p-8 text-center motion-safe:animate-pulse">
        <Upload className="size-12 text-primary" />
        <h2 className="text-2xl font-semibold">Solte aqui sua fonte</h2>
        <p className="text-muted-foreground">
          Vamos preencher os dados para você revisar.
        </p>
      </div>
    </div>
  );
}
