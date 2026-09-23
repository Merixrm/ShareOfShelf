import React, { useMemo, useState } from 'react';
import { HelpCircle, Check, CheckCircle2, Sparkles, Search } from 'lucide-react';
import { unknownProducts } from '@/lib/mockData';
import PageHero from '@/components/PageHero';
import ProductImage from '@/components/ProductImage';
import StatusBadge from '@/components/StatusBadge';
import EmptyState from '@/components/EmptyState';
import { toFa, faPct, faDateLong } from '@/lib/format';

const TABS = ['همه', 'تأیید شده', 'تأیید جزئی', 'نامشخص'];

export default function UnknownProducts() {
  const [tab, setTab] = useState('همه');
  const [approved, setApproved] = useState({});
  const [query, setQuery] = useState('');

  const list = unknownProducts.map((u) => ({ ...u, status: approved[u.id] ? 'تأیید شده' : u.status }));
  const filtered = useMemo(() => {
    return list.filter((u) => {
      if (tab !== 'همه' && u.status !== tab) return false;
      if (query) {
        const q = query.trim();
        return (u.possibleBrand + u.possibleFlavor + u.possibleSize).includes(q);
      }
      return true;
    });
  }, [list, tab, query]);

  const approve = (id) => setApproved((p) => ({ ...p, [id]: true }));
  const verifiedCount = Object.keys(approved).length;

  return (
    <div className="space-y-5">
      <PageHero title="شناسایی محصولات جدید" subtitle="محصولاتی که هوش مصنوعی نمی‌تواند با اطمینان کامل شناسایی کند. تحلیلگر با بررسی و تأیید، آن‌ها را به پایگاه دانش محصول اضافه می‌کند.">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs">
          <Sparkles className="h-4 w-4 text-success" />
          <span className="text-muted-foreground">تأیید شده:</span>
          <span className="font-bold text-foreground">{toFa(verifiedCount)} محصول</span>
        </div>
      </PageHero>

      {/* Tabs + search */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border border-border p-0.5">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${tab === t ? 'bg-brand text-brand-foreground' : 'text-muted-foreground hover:text-foreground'}`}>{t}</button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجو…" className="h-9 w-56 rounded-lg border border-border bg-background pr-9 pl-3 text-sm focus:border-brand focus:outline-none" />
        </div>
      </div>

      {/* Cards */}
      {filtered.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((u) => (
            <div key={u.id} className="overflow-hidden rounded-xl border border-border bg-card">
              <div className="relative flex items-center justify-center bg-muted/60 py-4">
                <div className="grayscale"><ProductImage product={{ color: u.color, flavorColor: u.flavorColor, flavor: u.possibleFlavor, brand: u.possibleBrand }} size={72} /></div>
                <span className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-foreground/80 text-white"><HelpCircle className="h-4 w-4" /></span>
                <span className="absolute bottom-2 right-2 rounded bg-foreground/70 px-1.5 py-0.5 text-[9px] text-white">نمونه برش‌خورده</span>
              </div>
              <div className="space-y-2.5 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-foreground">محصول ناشناخته</span>
                  <StatusBadge status={u.status} />
                </div>
                <div className="grid grid-cols-2 gap-y-1.5 text-[11px]">
                  <span className="text-muted-foreground">برند احتمالی:</span><span className="font-medium text-foreground">{u.possibleBrand}</span>
                  <span className="text-muted-foreground">طعم احتمالی:</span><span className="font-medium text-foreground">{u.possibleFlavor}</span>
                  <span className="text-muted-foreground">سایز احتمالی:</span><span className="font-medium text-foreground">{u.possibleSize}</span>
                  <span className="text-muted-foreground">اولین مشاهده:</span><span className="font-medium text-foreground">{faDateLong(u.firstSeen)}</span>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>اطمینان مدل</span><span className="font-semibold text-foreground">{faPct(u.confidence * 100, 0)}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full" style={{ width: `${u.confidence * 100}%`, backgroundColor: u.confidence > 0.7 ? '#16a34a' : u.confidence > 0.55 ? '#d97706' : '#94a3b8' }} />
                  </div>
                </div>
                <button
                  onClick={() => approve(u.id)}
                  disabled={approved[u.id]}
                  className={`flex w-full items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition ${approved[u.id] ? 'bg-success/10 text-success' : 'bg-brand text-brand-foreground hover:bg-brand/90'}`}
                >
                  {approved[u.id] ? <><CheckCircle2 className="h-4 w-4" /> تأیید و افزودن به پایگاه دانش</> : <><Check className="h-4 w-4" /> تأیید محصول</>}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card"><EmptyState title="محصول ناشناخته‌ای یافت نشد" /></div>
      )}
    </div>
  );
}