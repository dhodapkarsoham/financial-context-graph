import type { Metadata } from "next";
import { Provider } from "@/components/Provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Financial Services Context Graph",
  description: "Investment management, trading, compliance, and risk assessment",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
