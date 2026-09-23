import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu, Bell } from 'lucide-react';
import Sidebar from './Sidebar';
import { FilterProvider } from '@/lib/FilterContext';

const TITLES = {
  '/': 'نمای کلی بازار',
  '/map': 'نقشه هوشمند توزیع',
  '/products': 'تحلیل محصولات',
  '/brands': 'تحلیل برند',
  '/stores': 'تحلیل فروشگاه',
  '/shelf-analysis': 'تحلیل تصویر قفسه',
  '/unknown': 'شناسایی محصولات جدید',
  '/opportunities': 'فرصت‌های بازار',
  '/reports': 'گزارش‌ها',
  '/settings': 'تنظیمات',
};

function pageTitle(pathname) {
  if (TITLES[pathname]) return TITLES[pathname];
  if (pathname.startsWith('/products/')) return 'هوشمندی محصول';
  if (pathname.startsWith('/stores/')) return 'هوشمندی فروشگاه';
  return 'پایش بازار';
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  return (
    <FilterProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Topbar */}
          <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-4 lg:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition hover:bg-muted lg:hidden"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div>
                <h1 className="text-sm font-bold text-foreground sm:text-base">{pageTitle(location.pathname)}</h1>
                <p className="hidden text-[11px] text-muted-foreground sm:block">سامانه هوشمند پایش بازار و قفسه فروشگاه‌ها</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-medium text-success sm:flex">
                <span className="h-1.5 w-1.5 rounded-full bg-success" />
                داده‌های زنده
              </span>
              <button type="button" className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition hover:bg-muted">
                <Bell className="h-4 w-4" />
                <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-brand" />
              </button>
              <div className="flex items-center gap-2.5 rounded-lg border border-border py-1 pr-1 pl-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
                  ر
                </div>
                <div className="hidden text-right leading-tight sm:block">
                  <p className="text-xs font-semibold text-foreground">رضا محمدی</p>
                  <p className="text-[10px] text-muted-foreground">مدیر فروش</p>
                </div>
              </div>
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 overflow-y-auto px-4 py-5 lg:px-6 lg:py-6 scrollbar-thin">
            <Outlet />
          </main>
        </div>
      </div>
    </FilterProvider>
  );
}