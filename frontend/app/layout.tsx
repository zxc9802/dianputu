import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "商品详情图生成智能体",
  description: "护肤美妆商品详情图生成 MVP"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
