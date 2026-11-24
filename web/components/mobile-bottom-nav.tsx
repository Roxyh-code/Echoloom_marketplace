"use client";

import Link from "next/link";

type Section = "discover" | "characters" | "stories";

const sections = [
  { id: "discover", label: "Discover", href: "/marketplace" },
  { id: "characters", label: "Characters", href: "/rehearsal?view=characters" },
  { id: "stories", label: "My stories", href: "/rehearsal" },
] as const;

function NavigationIcon({ section }: { section: Section }) {
  const paths: Record<Section, React.ReactNode> = {
    discover: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2.5 5-4.5 2 2.5-5 4.5-2Z" /></>,
    characters: <><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1ZM12 5v15" /></>,
    stories: <><path d="m4 20 4.5-1 11-11a2.2 2.2 0 0 0-3.1-3.1l-11 11L4 20ZM14.5 6.5l3 3" /></>,
  };
  return (
    <svg width={21} height={21} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[section]}
    </svg>
  );
}

/** Consistent nav order and icons across Marketplace, public previews and Story Studio.
 *
 * Story Studio keeps its in-page navigation callbacks (to preserve draft state
 * and existing history logic). Other pages use the equivalent Next.js routes.
 */
export function MobileBottomNav({
  active,
  variant = "marketplace",
  onCharacters,
  onStories,
}: {
  active: Section;
  variant?: "marketplace" | "studio";
  onCharacters?: () => void;
  onStories?: () => void;
}) {
  return (
    <nav className={variant === "studio" ? "rh-nav el-mobile-nav" : "em-bottom-nav el-mobile-nav"}
      aria-label="Primary navigation">
      {sections.map((item) => {
        const selected = item.id === active;
        const contents = <><NavigationIcon section={item.id} /><span>{item.label}</span></>;
        const onClick = item.id === "characters" ? onCharacters
          : item.id === "stories" ? onStories : undefined;
        return onClick ? (
          <button key={item.id} type="button" className={selected ? "active" : undefined}
            aria-current={selected ? "page" : undefined} onClick={onClick}>
            {contents}
          </button>
        ) : (
          <Link key={item.id} href={item.href} className={selected ? "active" : undefined}
            aria-current={selected ? "page" : undefined}>
            {contents}
          </Link>
        );
      })}
    </nav>
  );
}
