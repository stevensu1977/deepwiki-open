import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "next-themes";

// Use system fonts instead of Google Fonts to avoid Turbopack issues
const geistSans = {
  variable: "--font-geist-sans",
  className: "font-sans"
};

const geistMono = {
  variable: "--font-geist-mono",
  className: "font-mono"
};

export const metadata: Metadata = {
  title: "Deepwiki Open Source | Sheing Ng",
  description: "Created by Sheing Ng",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider attribute="class">{children}</ThemeProvider>
      </body>
    </html>
  );
}
