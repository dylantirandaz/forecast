"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard,
  HelpCircle,
  FileSearch,
  History,
  Target,
  TrendingUp,
  FlaskConical,
  Receipt,
  ClipboardCheck,
  RotateCcw,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/questions", label: "Questions", icon: HelpCircle },
  { href: "/evidence", label: "Evidence", icon: FileSearch },
  { href: "/backtests", label: "Backtests", icon: History },
  { href: "/calibration", label: "Calibration", icon: Target },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/costs", label: "Costs", icon: Receipt },
];

const evalItems = [
  { href: "/eval", label: "Dashboard", icon: ClipboardCheck },
  { href: "/eval/replay", label: "Replay Viewer", icon: RotateCcw },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-surface-border bg-surface">
      {/* Brand */}
      <div className="flex h-16 items-center gap-3 border-b border-surface-border px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
          <TrendingUp className="h-4 w-4 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-gray-100">NYC Housing</h1>
          <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500">
            Forecast System
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                active ? "sidebar-link-active" : "sidebar-link"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}

        {/* Evaluation section */}
        <div className="pt-4">
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
            Evaluation
          </p>
          {evalItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  active ? "sidebar-link-active" : "sidebar-link"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-surface-border px-5 py-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-accent-positive animate-pulse-slow" />
          <span className="text-xs text-gray-500">Model Online</span>
        </div>
        <p className="mt-1 text-[10px] text-gray-600">v0.1.0 — Last sync 2m ago</p>
      </div>
    </aside>
  );
}
