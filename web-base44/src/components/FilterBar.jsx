import React, { useMemo } from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { useFilters } from '@/lib/FilterContext';
import { BRANDS, FLAVORS, SIZES, products } from '@/lib/mockData';

const PERIODS = [
  { value: 'all', label: 'کل بازه' },
  { value: '7', label: '۷ روز اخیر' },
  { value: '30', label: '۳۰ روز اخیر' },
  { value: '90', label: '۹۰ روز اخیر' },
];

const ALL = '__all__';

export default function FilterBar({ show = ['brand', 'flavor', 'size', 'sku', 'period'], compact = false }) {
  const { filters, setFilter, setMany, reset } = useFilters();

  const periodValue = useMemo(() => {
    if (!filters.dateFrom && !filters.dateTo) return 'all';
    return '90';
  }, [filters.dateFrom, filters.dateTo]);

  const setPeriod = (val) => {
    if (val === 'all') { setMany({ dateFrom: null, dateTo: null }); return; }
    const days = Number(val);
    const from = new Date(Date.now() - days * 86400000).toISOString();
    setMany({ dateFrom: from, dateTo: new Date().toISOString() });
  };

  return (
    <div className={`flex flex-wrap items-center gap-2 ${compact ? '' : 'rounded-xl border border-border bg-card p-3'}`}>
      {show.includes('brand') && (
        <Field label="برند">
          <Select value={filters.brandId || ALL} onValueChange={(v) => setFilter('brandId', v === ALL ? null : v)}>
            <SelectTrigger className="h-9 w-[150px]"><SelectValue placeholder="همه برندها" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>همه برندها</SelectItem>
              {BRANDS.map((b) => (
                <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}
      {show.includes('flavor') && (
        <Field label="طعم">
          <Select value={filters.flavor || ALL} onValueChange={(v) => setFilter('flavor', v === ALL ? null : v)}>
            <SelectTrigger className="h-9 w-[130px]"><SelectValue placeholder="همه طعم‌ها" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>همه طعم‌ها</SelectItem>
              {FLAVORS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
      )}
      {show.includes('size') && (
        <Field label="سایز">
          <Select value={filters.size || ALL} onValueChange={(v) => setFilter('size', v === ALL ? null : v)}>
            <SelectTrigger className="h-9 w-[140px]"><SelectValue placeholder="همه سایزها" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>همه سایزها</SelectItem>
              {SIZES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
      )}
      {show.includes('sku') && (
        <Field label="SKU">
          <Select value={filters.sku || ALL} onValueChange={(v) => setFilter('sku', v === ALL ? null : v)}>
            <SelectTrigger className="h-9 w-[170px]"><SelectValue placeholder="همه SKUها" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>همه SKUها</SelectItem>
              {products.map((p) => (
                <SelectItem key={p.id} value={p.sku}>
                  {p.sku} — {p.brand} {p.flavor}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}
      {show.includes('period') && (
        <Field label="بازه زمانی">
          <Select value={periodValue} onValueChange={setPeriod}>
            <SelectTrigger className="h-9 w-[130px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
      )}
      <Button variant="outline" size="sm" className="h-9 gap-1.5 text-xs" onClick={reset}>
        <RotateCcw className="h-3.5 w-3.5" />
        پاک کردن فیلترها
      </Button>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="px-1 text-[10px] font-medium text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}