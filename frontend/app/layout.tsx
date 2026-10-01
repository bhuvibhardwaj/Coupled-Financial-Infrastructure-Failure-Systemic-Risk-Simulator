import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Systemic Risk Simulator",
  description: "A small educational financial infrastructure cascade simulator",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
