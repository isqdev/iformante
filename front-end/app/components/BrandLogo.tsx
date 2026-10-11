import Image from "next/image";
import { cn } from "@/lib/utils";

export function BrandLogo({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <Image
      src="/branding/informante-mark-v2.png"
      alt=""
      width={size}
      height={size}
      className={cn("shrink-0 object-contain drop-shadow-[0_2px_2px_rgb(0_0_0/0.12)]", className)}
    />
  );
}
