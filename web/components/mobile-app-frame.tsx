"use client";

import { useEffect, useState, type ComponentProps, type CSSProperties } from "react";

type MobileAppFrameProps = ComponentProps<"main">;

/**
 * Single viewport-sized phone canvas for Discover, Characters and My Stories.
 * Pages supply their own content, but never their own frame geometry.
 */
export function MobileAppFrame({
  children,
  className,
  style,
  ...props
}: MobileAppFrameProps) {
  const [viewportHeight, setViewportHeight] = useState<number | null>(null);

  useEffect(() => {
    const viewport = window.visualViewport;
    const resize = () => setViewportHeight(viewport?.height ?? window.innerHeight);
    resize();
    viewport?.addEventListener("resize", resize);
    window.addEventListener("resize", resize);
    return () => {
      viewport?.removeEventListener("resize", resize);
      window.removeEventListener("resize", resize);
    };
  }, []);

  const frameStyle = viewportHeight === null
    ? style
    : ({ ...style, "--el-frame-height": `${viewportHeight}px` } as CSSProperties);

  return (
    <main
      {...props}
      className={["el-mobile-frame", className].filter(Boolean).join(" ")}
      style={frameStyle}
    >
      {children}
    </main>
  );
}
