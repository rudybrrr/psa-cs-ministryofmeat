import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export function IconOverview(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </IconBase>
  );
}

export function IconRecovery(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 3v4" />
      <path d="M12 17v4" />
      <path d="M3 12h4" />
      <path d="M17 12h4" />
      <circle cx="12" cy="12" r="4" />
    </IconBase>
  );
}

export function IconContainers(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 7h16v12H4z" />
      <path d="M8 7V5h8v2" />
      <path d="M8 11h8" />
      <path d="M8 15h5" />
    </IconBase>
  );
}

export function IconCarrier(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M3 17h18" />
      <path d="M5 17l2-8h10l2 8" />
      <circle cx="7.5" cy="17" r="1.5" />
      <circle cx="16.5" cy="17" r="1.5" />
    </IconBase>
  );
}

export function IconEvidence(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M9 3h6l3 3v15H6V3z" />
      <path d="M9 3v3h6" />
      <path d="M9 13h6" />
      <path d="M9 17h4" />
    </IconBase>
  );
}

export function IconRisk(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 9v4" />
      <circle cx="12" cy="17" r="0.5" fill="currentColor" />
      <path d="M10.3 4.5 2.5 18a1.5 1.5 0 0 0 1.3 2.2h16.4a1.5 1.5 0 0 0 1.3-2.2L13.7 4.5a1.5 1.5 0 0 0-2.6 0z" />
    </IconBase>
  );
}

export function IconCapacity(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <rect x="7" y="12" width="3" height="7" />
      <rect x="12" y="8" width="3" height="11" />
      <rect x="17" y="14" width="3" height="5" />
    </IconBase>
  );
}

export function IconPreserved(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M20 6 9 17l-5-5" />
    </IconBase>
  );
}

export function IconRollover(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M7 7h10" />
      <path d="M7 12h7" />
      <path d="M7 17h4" />
      <path d="M17 7v10" />
      <path d="M14 17h6" />
    </IconBase>
  );
}
