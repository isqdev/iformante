"use client";

import { useEffect, useId, useRef, type RefObject } from "react";
import type { CallPlayer } from "@/lib/call-player";
import type { CallState } from "../../hooks/useCall";

// Reconstructed from the user-provided call portrait. Each part is an editable
// vector; this detailed character intentionally has no dependency on BrandLogo.
export function InformanteAvatar({ state, player }: { state: CallState; player: RefObject<CallPlayer | null> }) {
  const id = useId().replace(/:/g, "");
  const head = useRef<SVGGElement>(null);
  const body = useRef<SVGGElement>(null);
  const leftCoat = useRef<SVGGElement>(null);
  const rightCoat = useRef<SVGGElement>(null);
  const coatHem = useRef<SVGGElement>(null);
  const eyes = useRef<SVGGElement>(null);
  const mouth = useRef<SVGPathElement>(null);
  const mouthClip = useRef<SVGPathElement>(null);
  const mouthInterior = useRef<SVGGElement>(null);
  const currentState = useRef(state);
  useEffect(() => { currentState.current = state; }, [state]);

  useEffect(() => {
    let raf = 0;
    let opening = 0;
    let rounding = 0;
    const started = performance.now();
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const animate = (now: number) => {
      const t = (now - started) / 1000;
      const frame = player.current?.frame;
      const speaking = currentState.current === "speaking" && frame?.speaking;
      const phoneme = (frame?.phoneme ?? "").replace(/[ˈˌː]/g, "");
      const closed = /^(p|b|m|_|\^|\$|\s)$/.test(phoneme);
      const round = /[ouɔʊɒ]/.test(phoneme);
      const target = speaking && !closed ? Math.min(1, Math.max(phoneme ? 0.18 : 0, (frame?.level ?? 0) * 7)) : 0;
      opening += (target - opening) * (target > opening ? 0.35 : 0.5);
      rounding += ((speaking && round ? 1 : 0) - rounding) * 0.28;
      const width = 62 - rounding * 22;
      const height = opening * 34;
      const shape = `M ${-width} -8 Q ${-width * 0.05} ${2 - height * 0.25} ${width} -8 Q ${width * 0.28} ${16 + height} ${-width} -8 Z`;
      mouth.current?.setAttribute("d", shape);
      mouthClip.current?.setAttribute("d", shape);
      mouthInterior.current?.setAttribute("opacity", String(Math.min(1, opening * 8)));
      const listening = currentState.current === "recording";
      const reduced = preference.matches;
      const resting = !listening && !speaking;
      const nod = reduced ? 0 : listening ? Math.sin(t * 1.4) * 0.7 + Math.sin(t * 3) * 0.15 : speaking ? Math.sin(t * 1.9) * 0.25 : Math.sin(t * 0.7) * 1.2 + Math.sin(t * 0.36) * 0.35;
      const sway = reduced || !resting ? 0 : Math.sin(t * 0.45) * 2;
      head.current?.setAttribute("transform", `rotate(${nod} 654 734) translate(${sway} ${reduced ? 0 : Math.sin(t * 1.15) * (resting ? 5 : 1.5)})`);
      body.current?.setAttribute("transform", `translate(0 ${reduced ? 0 : Math.sin(t * 1.15) * (resting ? 2.4 : 0.8)})`);
      // The collar stays attached to the shoulders while the fabric follows
      // a slow breeze. Lower folds trail slightly behind the upper lapels.
      const breeze = (delay: number) => reduced ? 0 : Math.sin((t - delay) * 0.85) * 0.72 + Math.sin((t - delay) * 1.37) * 0.28;
      const leftWind = breeze(0);
      const rightWind = breeze(0.55);
      const hemWind = breeze(1.1);
      leftCoat.current?.setAttribute("transform", `translate(416 635) rotate(${leftWind * 0.85}) skewX(${leftWind * 0.25}) translate(-416 -635)`);
      rightCoat.current?.setAttribute("transform", `rotate(${rightWind * 0.75} 811 771)`);
      coatHem.current?.setAttribute("transform", `translate(718 949) rotate(${hemWind * 1.2}) skewX(${hemWind * 0.4}) translate(-718 -949)`);
      const blinkPhase = t % 5.3;
      const blink = !reduced && blinkPhase > 5.1 ? Math.max(0.05, Math.abs((blinkPhase - 5.2) * 10)) : 1;
      eyes.current?.setAttribute("transform", `translate(0 ${580 * (1 - blink)}) scale(1 ${blink})`);
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [player]);

  return (
    <svg viewBox="170 105 955 1040" role="img" aria-label="InFormante, personagem de chapéu vermelho e casaco verde" className="call-avatar" data-testid="call-avatar">
      <defs>
        <linearGradient id={`${id}-red`} x1="480" y1="180" x2="930" y2="540" gradientUnits="userSpaceOnUse"><stop stopColor="#ff2929" /><stop offset="0.55" stopColor="#ed1d22" /><stop offset="1" stopColor="#bd1016" /></linearGradient>
        <linearGradient id={`${id}-hat-shadow`} x1="605" y1="175" x2="800" y2="490" gradientUnits="userSpaceOnUse"><stop stopColor="#5b080a" /><stop offset="1" stopColor="#8e1116" /></linearGradient>
        <linearGradient id={`${id}-brim`} x1="390" y1="395" x2="911" y2="584" gradientUnits="userSpaceOnUse"><stop stopColor="#bf1015" /><stop offset="0.53" stopColor="#811010" /><stop offset="1" stopColor="#64100f" /></linearGradient>
        <linearGradient id={`${id}-skin`} x1="518" y1="489" x2="799" y2="803" gradientUnits="userSpaceOnUse"><stop stopColor="#f5ecdc" /><stop offset="0.7" stopColor="#f2e4cf" /><stop offset="1" stopColor="#e9d8c0" /></linearGradient>
        <linearGradient id={`${id}-skin-shadow`} x1="582" y1="518" x2="817" y2="659" gradientUnits="userSpaceOnUse"><stop stopColor="#998f7d" /><stop offset="0.5" stopColor="#d2c6b0" /><stop offset="1" stopColor="#6b695f" /></linearGradient>
        <linearGradient id={`${id}-coat`} x1="358" y1="712" x2="749" y2="1056" gradientUnits="userSpaceOnUse"><stop stopColor="#3e5531" /><stop offset="0.6" stopColor="#283923" /><stop offset="1" stopColor="#101c16" /></linearGradient>
        <linearGradient id={`${id}-right-coat`} x1="824" y1="782" x2="738" y2="1016" gradientUnits="userSpaceOnUse"><stop stopColor="#405536" /><stop offset="1" stopColor="#17261b" /></linearGradient>
        <linearGradient id={`${id}-ear`} x1="390" y1="466" x2="493" y2="586" gradientUnits="userSpaceOnUse"><stop stopColor="#fbf3e6" /><stop offset="1" stopColor="#ddcfb6" /></linearGradient>
        <radialGradient id={`${id}-ear-black`}><stop stopColor="#32332e" /><stop offset="1" stopColor="#171816" /></radialGradient>
        <clipPath id={`${id}-mouth-mask`}><path ref={mouthClip} d="M -62 -8 Q -3 2 62 -8 Q 17 16 -62 -8 Z" /></clipPath>
      </defs>
      <g ref={body}>
        <path d="M 432 616 L 518 680 670 813 689 872 726 918 816 762 869 803 929 850 864 910 886 1030 790 1050 718 1118 493 1010 335 833 226 855 338 761 329 632 Z" fill="#070b09" />
        <path d="M 640 778 L 821 718 L 842 807 L 737 1030 L 653 919 Z" fill="#000" />
        <g ref={leftCoat}>
          <path d="M 329 632 Q 374 618 416 625 L 365 642 561 737 659 808 718 1118 493 1010 336 832 226 855 338 761 Z" fill="#486738" />
          <path d="M 371 674 L 649 807 Q 638 926 702 1092 L 536 841 345 790 389 775 Z" fill={`url(#${id}-coat)`} />
          <path d="M 345 790 L 536 841 692 1090 493 1010 333 832 Z" fill="#040806" />
          <path d="M 650 811 Q 642 927 703 1096" fill="none" stroke="#63804a" strokeWidth="3" opacity="0.6" />
        </g>
        <g ref={coatHem}>
          <path d="M 797 949 L 886 1030 816 1044 718 1118 700 1082 739 1083 Z" fill="#47673a" />
          <path d="M 800 950 L 856 1016 813 1020 739 1083 Z" fill="#293c26" />
        </g>
        <g ref={rightCoat}>
          <path d="M 811 745 L 963 852 919 868 865 910 733 1012 Q 737 897 810 794 Z" fill="#49613b" />
          <path d="M 811 771 L 914 853 819 925 733 1012 Q 744 890 811 771 Z" fill={`url(#${id}-right-coat)`} />
        </g>
        <path d="M 657 806 L 674 831 680 875 725 916 678 916 669 884 Z" fill="#33352e" />
        <path d="M 663 813 L 680 813 683 868 Q 676 883 669 871 Z" fill="#151a16" />
      </g>
      <g ref={head}>
        <path d="M 432 408 L 516 429 853 576 867 613 827 721 746 813 Q 710 851 671 833 L 590 749 490 680 445 594 419 503 Z" fill="#090b09" />
        <path d="M 516 446 L 577 472 572 489 644 512 697 547 783 595 865 610 839 677 748 786 711 827 Q 692 841 671 833 L 670 809 590 746 576 640 519 589 Z" fill={`url(#${id}-skin)`} />
        <path d="M 516 448 L 514 589 569 641 582 734 496 661 486 611 465 595 484 476 Z" fill={`url(#${id}-skin)`} />
        <path d="M 575 484 L 639 507 704 550 669 537 582 512 558 556 552 610 566 506 Z" fill={`url(#${id}-skin-shadow)`} />
        <path d="M 582 514 Q 598 604 686 626 Q 714 637 763 621 L 775 625 775 710 790 657 Q 822 671 845 645 L 866 611 760 583 702 556 674 542 633 539 Z" fill="#0a0c0a" />
        <path d="M 789 657 L 777 710 832 677 849 635 Q 827 661 807 658 Z" fill={`url(#${id}-skin-shadow)`} />
        <g ref={eyes}>
          <path d="M 627 543 L 695 579 Q 683 592 661 586 Q 637 578 627 543 Z" fill="#fff7e8" />
          <path d="M 805 628 Q 822 618 828 610 L 852 610 Q 835 638 813 634 Z" fill="#fff8e9" />
        </g>
        <path d="M 518 445 L 518 589 571 640 587 739" fill="none" stroke="#131512" strokeWidth="6" />
        <path d="M 443 410 Q 475 414 501 455 L 515 518 496 611 457 627 436 607 422 487 Z" fill="#080a08" />
        <ellipse cx="451" cy="533" rx="61" ry="94" transform="rotate(-9 451 533)" fill="#131511" />
        <ellipse cx="441" cy="528" rx="54" ry="87" transform="rotate(-9 441 528)" fill="#7b776b" />
        <ellipse cx="436" cy="531" rx="49" ry="80" transform="rotate(-9 436 531)" fill={`url(#${id}-ear)`} />
        <ellipse cx="423" cy="526" rx="34" ry="57" transform="rotate(-9 423 526)" fill="#080a08" />
        <ellipse cx="417" cy="526" rx="24" ry="48" transform="rotate(-9 417 526)" fill={`url(#${id}-ear-black)`} />
        <path d="M 453 624 L 479 651 484 680 461 661 Z" fill="#2c302a" />
        <g transform="translate(694 728) rotate(18)">
          <path ref={mouth} data-testid="call-mouth" d="M -62 -8 Q -3 2 62 -8 Q 17 16 -62 -8 Z" fill="#0c0f0b" />
          <g ref={mouthInterior} opacity="0" clipPath={`url(#${id}-mouth-mask)`}>
            <path d="M -59 -10 Q -8 1 59 -10 L 59 -1 Q -7 11 -59 -1 Z" fill="#fff7e8" />
            <ellipse cx="10" cy="37" rx="35" ry="10" fill="#9d5149" />
          </g>
        </g>
        <path d="M 690 761 Q 716 770 730 767 Q 714 784 701 770 Z" fill="#161913" />
        <path d="M 393 366 L 410 323 416 323 491 193 Q 559 159 637 148 Q 718 165 817 210 Q 832 216 872 225 Q 895 231 899 248 Q 924 348 941 512 L 903 494 892 379 452 317 432 365 Z" fill={`url(#${id}-red)`} />
        <path d="M 514 292 L 556 188 Q 600 159 637 148 Q 711 177 793 260 Q 818 289 830 292 Q 845 290 872 246 L 893 381 Q 679 327 514 292 Z" fill={`url(#${id}-hat-shadow)`} />
        <path d="M 708 181 Q 753 202 794 225 Q 821 242 862 241 L 873 246 Q 847 291 831 293 Q 815 291 785 259 Z" fill="#030504" />
        <path d="M 451 316 Q 607 283 793 348 Q 864 371 913 406 L 940 511 Q 714 417 432 366 Z" fill="#030504" />
        <path d="M 394 366 Q 478 365 580 424 Q 788 543 944 586 L 967 596 873 486 Q 744 431 619 403 Q 508 375 431 366 Q 319 365 260 391 Q 236 403 253 426 Q 283 466 371 495 Q 285 435 267 404 Q 300 375 394 389 Q 502 389 649 478 Q 829 582 965 620 Q 1025 636 1061 640 Q 1041 654 916 665 Q 1055 663 1075 641 Q 1075 626 1017 578 L 940 511 938 493 873 473 966 596 Q 825 564 639 455 Q 487 368 394 366 Z" fill={`url(#${id}-red)`} />
        <path d="M 432 367 Q 588 386 756 433 L 873 473 966 596 Q 822 562 638 455 Q 509 379 432 367 Z" fill={`url(#${id}-brim)`} />
        <path d="M 267 405 Q 329 376 417 398 Q 564 430 700 511 Q 863 604 1035 638 Q 968 642 894 627 Q 740 583 624 512 Q 436 402 353 402 Q 301 399 267 405 Z" fill="#040605" />
        <path d="M 267 405 Q 312 462 371 495 Q 292 467 260 426 Z" fill="#9b1012" />
      </g>
    </svg>
  );
}
