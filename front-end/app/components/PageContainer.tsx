import type {ReactNode} from "react";
import {Card} from "@/components/ui/card";
import {cn} from "@/lib/utils";

export function PageContainer({children, className}: {children: ReactNode; className?: string}) {
  return <Card className={cn("m-2 h-[calc(100%-1rem)] min-w-0 gap-0 overflow-hidden rounded-lg border border-sidebar-border bg-sidebar py-0 shadow-sm ring-0 md:ml-0", className)}>{children}</Card>;
}
