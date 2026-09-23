import React, { useMemo, useState } from 'react';
import { FileText, Award, Package, Store, Map as MapIcon, BarChart3, FileSpreadsheet, FileBarChart, CheckCircle2, Loader2, Download } from 'lucide-react';
import { useFilters } from '@/lib/FilterContext';
import { shareOfShelfData, brandPresenceData, marketCoverageData, areaStrengthData } from '@/lib/mockData';
import PageHero from '@/components/PageHero';
import FilterBar from '@/components/FilterBar';
import SectionCard from '@/components/SectionCard';
import { toFa, faPct, faDateLong } from '@/lib/format';

const REPORT_TYPES = [
  { id: 'sos', name: 'سهم قفسه', desc: 'سهم هر برند از فضای قفسه و facings', icon: BarChart3 },
  { id: 'brand', name: 'وضعیت برند', desc: 'عملکرد و پوشش هر برند', icon: Award },
  { id: 'product', name: 'وضعیت محصول', desc: 'آمار و وضعیت محصولات در بازار', icon: Package },
  { id: 'coverage', name: 'پوشش فروشگاه‌ها', desc: 'نرخ حضور برندها در فروشگاه‌ها', icon: Store },
  { id: 'geo', name: 'پراکندگی جغرافیایی', desc: 'تراکم مشاهدات در مناطق', icon: MapIcon },
  { id: 'compare', name: 'مقایسه رقبا', desc: 'مقایسه برندها در کنار هم', icon: FileText },
];

export default function Reports() {
  const { filters } = useFilters();
  const [type, setType] = useState('sos');
  const [exporting, setExporting] = useState(null);

  const sos = useMemo(() => shareOfShelfData(filters), [filters]);
  const presence = useMemo(() => brandPresenceData(filters), [filters]);
  const coverage = useMemo(() => marketCoverageData(filters), [filters]);
  const areas = useMemo(() => areaStrengthData(filters), [filters]);

  const handleExport = (fmt) => {
    setExporting(fmt);
    setTimeout(() => setExporting('done'), 1600);
  };

  return (
    <div className="space-y-5">
      <PageHero title="گزارش‌ها" subtitle="تولید گزارش‌های حرفه‌ای از سهم قفسه، وضعیت برند/محصول، پوشش و پراکندگی جغرافیایی با امکان خروجی Excel و PDF.">
        <FilterBar show={['brand', 'flavor', 'size', 'sku', 'period']} compact />
      </PageHero>

      {/* Report types */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {REPORT_TYPES.map((r) => (
          <button
            key={r.id}
            onClick={() => setType(r.id)}
            className={`flex items-start gap-3 rounded-xl border p-4 text-right transition ${type === r.id ? 'border-brand bg-brand/5 shadow-sm' : 'border-border bg-card hover:border-border/80'}`}
          >
            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${type === r.id ? 'bg-brand text-brand-foreground' : 'bg-muted text-muted-foreground'}`}>
              <r.icon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground">{r.name}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{r.desc}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Preview + export */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SectionCard
          title={`پیش‌نمایش: ${REPORT_TYPES.find((r) => r.id === type)?.name}`}
          subtitle={`داده‌های مربوط به ${faDateLong(new Date().toISOString())}`}
          className="lg:col-span-2"
          actions={
            <div className="flex items-center gap-2">
              <button onClick={() => handleExport('excel')} disabled={!!exporting} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted disabled:opacity-60">
                {exporting === 'excel' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : exporting === 'done' ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <FileSpreadsheet className="h-3.5 w-3.5 text-success" />}
                Excel
              </button>
              <button onClick={() => handleExport('pdf')} disabled={!!exporting} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted disabled:opacity-60">
                {exporting === 'pdf' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : exporting === 'done' ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <FileBarChart className="h-3.5 w-3.5 text-destructive" />}
                PDF
              </button>
            </div>
          }
        >
          {exporting === 'done' && (
            <div className="mb-3 flex items-center gap-2 rounded-lg bg-success/10 px-3 py-2 text-xs font-medium text-success">
              <CheckCircle2 className="h-4 w-4" /> فایل خروجی آماده شد.
            </div>
          )}
          <PreviewTable type={type} sos={sos} presence={presence} coverage={coverage} areas={areas} />
        </SectionCard>

        <SectionCard title="اطلاعات گزارش" subtitle="پارامترهای خروجی">
          <div className="space-y-3 text-xs">
            <InfoRow label="نوع گزارش" value={REPORT_TYPES.find((r) => r.id === type)?.name} />
            <InfoRow label="قالب خروجی" value="Excel / PDF" />
            <InfoRow label="بازه زمانی" value={filters.dateFrom ? faDateLong(filters.dateFrom) : 'کل بازه'} />
            <InfoRow label="تاریخ تولید" value={faDateLong(new Date().toISOString())} />
            <div className="border-t border-border pt-3">
              <button onClick={() => handleExport('pdf')} className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand/90">
                <Download className="h-4 w-4" /> دانلود گزارش
              </button>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function PreviewTable({ type, sos, presence, coverage, areas }) {
  let head = [], rows = [];
  if (type === 'sos') {
    head = ['برند', 'facings', 'سهم facing', 'فضای قفسه', 'سهم فضا'];
    rows = sos.map((s) => [s.brand, toFa(s.facings), faPct(s.facingsPct), toFa(s.area), faPct(s.areaPct)]);
  } else if (type === 'brand' || type === 'compare') {
    head = ['برند', 'فروشگاه‌ها', 'مشاهدات'];
    rows = presence.map((p) => [p.brand, toFa(p.stores), toFa(p.observations)]);
  } else if (type === 'coverage') {
    head = ['برند', 'فروشگاه‌ها', 'پوشش'];
    rows = coverage.map((c) => [c.brand, toFa(c.stores), faPct(c.coverage)]);
  } else if (type === 'geo') {
    head = ['منطقه', 'مشاهدات', 'فروشگاه‌ها'];
    rows = areas.slice(0, 12).map((a) => [a.district, toFa(a.count), toFa(a.stores)]);
  } else {
    head = ['برند', 'facings', 'سهم facing'];
    rows = sos.map((s) => [s.brand, toFa(s.facings), faPct(s.facingsPct)]);
  }
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className="w-full text-right text-xs">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-muted-foreground">
            {head.map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => <td key={j} className={`px-3 py-2 ${j === 0 ? 'font-semibold text-foreground' : 'text-foreground'}`}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}