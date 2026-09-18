import "./globals.css";

export const metadata = {
  title: "Polymarket Edge Scanner",
  description: "Where proven Polymarket winners are positioned right now. Powered by Nansen.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
