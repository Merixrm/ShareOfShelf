import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Store } from 'lucide-react';
import { useFilters } from '@/lib/FilterContext';
import { stores, observations, productById, BRANDS, brandById } from '@/lib/mockData';
import FilterBar from '@/components/FilterBar';
import PageHero from '@/components/PageHero';
import DataTable from '@/components/DataTable';
import { toFa, faDate } from '@/lib/format';

export default function Stores() {
  const { filters } = useFilters();
  const navigate = useNavigate();

  const stats = useMemo(() => {
    return stores
      .map((s) => {
        const obs = observations.filter((o) => {
          if (o.store_id !== s.id) return false;
          const p = productById[o.product_id];
          if (!p) return false;
          if (filters.brandId && p.brandId !== filters.brandId) return false;
          if (filters.flavor && p.flavor !== filters.flavor) return false;
          if (filters.size && p.size !== filters.size) return false;
          if (filters.sku && p.id !== filters.sku && p.sku !== filters.sku) return false;
          if (filters.dateFrom && o.observed_at < filters.dateFrom) return false;
          if (filters.dateTo && o.observed_at > filters.dateTo) return false;
          return true;
        });
        const productIds = new Set(obs.map((o) => o.product_id));
        const brandIds = new Set([...productIds].map((id) => productById[id]?.brandId).filter(Boolean));
        const byBrand = {};
        obs.forEach((o) => {
          const p = productById[o.product_id];
          if (!p) return;
          byBrand[p.brandId] = (byBrand[p.brandId] || 0) + o.detected_count;
        });
        const dominantId = Object.entries(byBrand).sort((a, b) => b[1] - a[1])[0]?.[0];
        const last = obs.length ? obs.sort((a, b) => +new Date(b.observed_at) - +new Date(a.observed_at))[0].observed_at : null;
        return {
          id: s.id, store: s, district: s.district,
          brands: brandIds.size, products: productIds.size, observations: obs.length,
          dominant: dominantId ? brandById[dominantId]?.name : '—',
          dominantColor: dominantId ? brandById[dominantId]?.color : '#94a3b8',
          last,
        };
      })
      .filter((r) => (filters.brandId || filters.flavor || filters.size || filters.sku ? r.observations > 0 : true));
  }, [filters]);

  const columns = [
    { key: 'name', header: 'نام فروشگاه', sortable: true, value: (r) => r.store.name,
      render: (r) => (
        <div>
          <p className="font-semibold text-foreground">{r.store.name}</p>
          <p className="text-[10px] text-muted-foreground">{r.store.address}</p>
        </div>
      ) },
    { key: 'district', header: 'منطقه', sortable: true, value: (r) => r.district },
    { key: 'brands', header: 'برندها', sortable: true, value: (r) => r.brands,
      render: (r) => <span className="font-semibold text-foreground">{toFa(r.brands)}</span> },
    { key: 'products', header: 'محصولات', sortable: true, value: (r) => r.products,
      render: (r) => toFa(r.products) },
    { key: 'observations', header: 'مشاهدات', sortable: true, value: (r) => r.observations,
      render: (r) => toFa(r.observations) },
    { key: 'dominant', header: 'برند غالب', sortable: true, value: (r) => r.dominant,
      render: (r) => (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: r.dominantColor }} />
          {r.dominant}
        </span>
      ) },
    { key: 'last', header: 'آخرین بازدید', sortable: true, value: (r) => (r.last ? +new Date(r.last) : 0),
      render: (r) => <span className="text-xs text-muted-foreground">{r.last ? faDate(r.last) : '—'}</span> },
  ];

  return (
    <div className="space-y-5">
      <PageHero title="تحلیل فروشگاه" subtitle="دایرکتوری فروشگاه‌های پایش‌شده. برای مشاهده هوشمندی هر فروشگاه روی ردیف کلیک کنید.">
        <FilterBar show={['brand', 'flavor', 'size', 'sku', 'period']} />
      </PageHero>

      <div className="rounded-xl border border-border bg-card p-4">
        <DataTable
          columns={columns}
          data={stats}
          pageSize={9}
          initialSort={{ key: 'observations', dir: 'desc' }}
          searchPlaceholder="جستجوی نام فروشگاه یا منطقه…"
          onRowClick={(r) => navigate(`/stores/${r.id}`)}
          emptyTitle="فروشگاهی یافت نشد"
          emptyDescription="فیلترها را تغییر دهید."
        />
      </div>
    </div>
  );
}