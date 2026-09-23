import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Map, Package, Award, Store, ScanLine,
  HelpCircle, Target, FileText, Settings, ChevronLeft, X,
} from 'lucide-react';

const NAV = [
  { to: '/', label: 'نمای کلی', icon: LayoutDashboard, end: true },
  { to: '/map', label: 'نقشه توزیع', icon: Map },
  { to: '/products', label: 'محصولات', icon: Package },
  { to: '/brands', label: 'برندها', icon: Award },
  { to: '/stores', label: 'فروشگاه‌ها', icon: Store },
  { to: '/shelf-analysis', label: 'تحلیل قفسه', icon: ScanLine },
  { to: '/unknown', label: 'محصولات ناشناخته', icon: HelpCircle },
  { to: '/opportunities', label: 'فرصت‌های بازار', icon: Target },
  { to: '/reports', label: 'گزارش‌ها', icon: FileText },
];

export default function Sidebar({ open, onClose }) {
  const location = useLocation();

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-foreground/40 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 right-0 z-40 flex w-64 flex-col bg-sidebar text-sidebar-foreground transition-transform duration-300 lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Brand */}
        <div className="flex h-16 items-center gap-2.5 border-b border-sidebar-border px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-brand-foreground shadow-sm">
            <ScanLine className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold leading-tight text-white">پایش بازار</p>
            <p className="truncate text-[10px] text-sidebar-foreground/70">هوش قفسه فروشگاه</p>
          </div>
          <button type="button" onClick={onClose} className="text-sidebar-foreground/70 lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4 scrollbar-thin">
          {NAV.map((item) => {
            const active = item.end
              ? location.pathname === item.to
              : location.pathname.startsWith(item.to);
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  active
                    ? 'bg-sidebar-accent text-white font-semibold'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-white'
                }`}
              >
                <item.icon className={`h-4 w-4 shrink-0 ${active ? 'text-brand' : 'text-sidebar-foreground/70'}`} />
                <span className="flex-1">{item.label}</span>
                {active && <ChevronLeft className="h-4 w-4 text-brand" />}
              </NavLink>
            );
          })}
        </nav>

        {/* Footer settings */}
        <div className="border-t border-sidebar-border p-3">
          <NavLink
            to="/settings"
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                isActive ? 'bg-sidebar-accent text-white font-semibold' : 'text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-white'
              }`
            }
          >
            <Settings className="h-4 w-4 shrink-0 text-sidebar-foreground/70" />
            <span>تنظیمات</span>
          </NavLink>
        </div>
      </aside>
    </>
  );
}