import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Open Wearables Docs Chat",
  description: "Chat with Open Wearables documentation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
