import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "NYC Housing Forecast System",
  description:
    "Probabilistic forecasting platform for NYC housing market scenarios",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">
        <Providers>
          <Sidebar />
          <main className="ml-64 min-h-screen p-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
