import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package } from 'lucide-react';
import { useFilters } from '@/lib/FilterContext';
import { products, observations, productById } from '@/lib/mockData';
import FilterBar from '@/components/FilterBar';
import PageHero from '@/components/PageHero';
import DataTable from '@/components/DataTable';
import ProductImage from '@/components/ProductImage';
import StatusBadge from '@/components/StatusBadge';
import { toFa, faPct, faDate } from '@/lib/format';

export default function Products() {
  const { filters } = useFilters();
  const navigate = useNavigate();

  const stats = useMemo(() => {
    const totalArea = observations.reduce((s, o) => s + o.shelf_area, 0);
    return products
      .filter((p) => {
        if (filters.brandId && p.brandId !== filters.brandId) return false;
        if (filters.flavor && p.flavor !== filters.flavor) return false;
        if (filters.size && p.size !== filters.size) return false;
        if (filters.sku && p.id !== filters.sku && p.sku !== filters.sku) return false;
        return true;
      })
      .map((p) => {
        const obs = observations.filter((o) => {
          if (o.product_id !== p.id) return false;
          if (filters.dateFrom && o.observed_at < filters.dateFrom) return false;
          if (filters.dateTo && o.observed_at > filters.dateTo) return false;
          return true;
        });
        const storeIds = new Set(obs.map((o) => o.store_id));
        const area = obs.reduce((s, o) => s + o.shelf_area, 0);
        const count = obs.reduce((s, o) => s + o.detected_count, 0);
        const last = obs.length ? obs.sort((a, b) => +new Date(b.observed_at) - +new Date(a.observed_at))[0].observed_at : null;
        const sos = totalArea ? (area / totalArea) * 100 : 0;
        const status = sos > 8 ? 'محرک رشد' : sos > 3 ? 'پایدار' : 'نیازمند توجه';
        return { id: p.id, product: p, stores: storeIds.size, observations: obs.length, count, area, sos, last, status };
      });
  }, [filters]);

  const columns = [
    {
      key: 'image', header: 'تصویر', sortable: false,
      render: (r) => <ProductImage product={r.product} size={38} />,
    },
    { key: 'brand', header: 'برند', sortable: true, value: (r) => r.product.brand,
      render: (r) => <span className="font-medium text-foreground">{r.product.brand}</span> },
    { key: 'sku', header: 'SKU', sortable: true, value: (r) => r.product.sku,
      render: (r) => <span className="font-mono text-xs text-muted-foreground ltr-nums">{r.product.sku}</span> },
    { key: 'flavor', header: 'طعم', sortable: true, value: (r) => r.product.flavor },
    { key: 'size', header: 'سایز', sortable: true, value: (r) => r.product.size },
    { key: 'stores', header: 'فروشگاه‌ها', sortable: true, value: (r) => r.stores,
      render: (r) => <span className="font-semibold text-foreground">{toFa(r.stores)}</span> },
    { key: 'count', header: 'مشاهدات', sortable: true, value: (r) => r.count,
      render: (r) => <span className="text-foreground">{toFa(r.count)}</span> },
    { key: 'sos', header: 'سهم قفسه', sortable: true, value: (r) => r.sos,
      render: (r) => (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-14 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-brand" style={{ width: `${Math.min(100, r.sos * 6)}%` }} />
          </div>
          <span className="text-xs font-medium text-foreground">{faPct(r.sos)}</span>
        </div>
      ) },
    { key: 'last', header: 'آخرین مشاهده', sortable: true, value: (r) => (r.last ? +new Date(r.last) : 0),
      render: (r) => <span className="text-xs text-muted-foreground">{r.last ? faDate(r.last) : '—'}</span> },
    { key: 'status', header: 'وضعیت', sortable: true, value: (r) => r.status,
      render: (r) => <StatusBadge status={r.status} /> },
  ];

  return (
    <div className="space-y-5">
      <PageHero title="تحلیل محصولات" subtitle="جدول جستجوپذیر محصولات شناسایی‌شده با قابلیت مرتب‌سازی. برای مشاهده هوشمندی کامل هر محصول روی ردیف کلیک کنید.">
        <FilterBar show={['brand', 'flavor', 'size', 'sku', 'period']} />
      </PageHero>

      <div className="rounded-xl border border-border bg-card p-4">
        <DataTable
          columns={columns}
          data={stats}
          pageSize={9}
          initialSort={{ key: 'count', dir: 'desc' }}
          searchPlaceholder="جستجو بر اساس برند، طعم یا SKU…"
          onRowClick={(r) => navigate(`/products/${r.id}`)}
          emptyTitle="محصولی یافت نشد"
          emptyDescription="فیلترها را تغییر دهید یا عبارت دیگری جستجو کنید."
        />
      </div>
    </div>
  );
}