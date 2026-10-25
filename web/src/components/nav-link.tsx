"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

type NavLinkProps = { href: string; children: React.ReactNode };

/**
 * Header link, highlighted when its section is open (server pages count as "Racks").
 * The current path is only known per request, so the highlight streams in inside
 * <Suspense>; the prerendered shell shows the plain link.
 */
export function NavLink(props: NavLinkProps) {
  return (
    <Suspense fallback={<StyledLink {...props} active={false} />}>
      <ActiveAwareLink {...props} />
    </Suspense>
  );
}

function ActiveAwareLink(props: NavLinkProps) {
  const pathname = usePathname();
  const active =
    props.href === "/"
      ? pathname === "/" || pathname.startsWith("/servers")
      : pathname.startsWith(props.href);
  return <StyledLink {...props} active={active} />;
}

function StyledLink({ href, children, active }: NavLinkProps & { active: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-md px-3 py-1.5 ${active ? "bg-page font-medium text-ink" : "text-ink-2 hover:text-ink"}`}
    >
      {children}
    </Link>
  );
}
