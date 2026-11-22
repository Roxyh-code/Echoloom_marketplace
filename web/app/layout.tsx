import type { Metadata } from "next";

import "./globals.css";
import "./editorial-global.css";
import { AppChrome } from "@/components/app-chrome";
export const metadata: Metadata = {
  title: "EchoLoom Marketplace · Interactive character stories",
  description:
    "Cast two characters into a new story. Original characters, interactive scenes and creator payouts.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
