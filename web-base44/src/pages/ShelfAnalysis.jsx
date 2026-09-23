import React, { useEffect, useRef, useState } from 'react';
import { Upload, ScanLine, Loader2, Camera, CheckCircle2, AlertTriangle, HelpCircle, Layers, Eye, Package } from 'lucide-react';
import SectionCard from '@/components/SectionCard';
import KpiCard from '@/components/KpiCard';
import StatusBadge from '@/components/StatusBadge';
import DataTable from '@/components/DataTable';
import { toFa, faPct } from '@/lib/format';
import { uploadAndAnalyze, toDetections } from '@/lib/shelfApi';

const BOX_COLOR = { 'شناسایی‌شده': '#16a34a', 'نیازمند بررسی': '#d97706', 'محصول ناشناخته': '#dc2626' };

export default function ShelfAnalysis() {
  const [stage, setStage] = useState('idle'); // idle | processing | done | error
  const [progress, setProgress] = useState({ done: 0, total: 0, stage: 'detecting' });
  const [detections, setDetections] = useState([]);
  const [shareOfShelf, setShareOfShelf] = useState([]);
  const [error, setError] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const fileInputRef = useRef(null);
  const objectUrlRef = useRef(null);

  useEffect(() => () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
  }, []);

  const handleFile = async (file) => {
    if (!file) return;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    setImageUrl(url);
    setError(null);
    setStage('processing');
    setProgress({ done: 0, total: 0, stage: 'detecting' });

    try {
      const session = await uploadAndAnalyze(file, (s) => {
        setProgress({ done: s.done, total: s.total, stage: s.stage });
      });
      setDetections(toDetections(session));
      setShareOfShelf(session.share_of_shelf);
      setStage('done');
    } catch (e) {
      setError(e.message);
      setStage('error');
    }
  };

  const stepIndex = { detecting: 0, classifying: 2, done: 4 }[progress.stage] ?? 0;
  const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : (stepIndex >= 2 ? 15 : 0);
  const steps = ['پیش‌پردازش تصویر', 'تشخیص اشیاء', 'طبقه‌بندی SKU', 'محاسبه سهم قفسه'];

  const detectedCount = detections.filter((d) => d.status !== 'محصول ناشناخته').length;
  const unknownCount = detections.filter((d) => d.status === 'محصول ناشناخته').length;
  const totalFacings = shareOfShelf.reduce((sum, r) => sum + r.facings, 0);

  const byBrand = {};
  detections.forEach((d) => {
    if (!d.crop) return;
    byBrand[d.crop.brand] = (byBrand[d.crop.brand] || 0) + 1;
  });
  const brandList = Object.entries(byBrand).map(([b, c]) => ({ b, c }));

  const columns = [
    { key: 'crop', header: 'تصویر برش‌خورده', render: (d) => (
      <img src={d.cropUrl} alt="" className="h-9 w-9 rounded-lg object-cover" />
    ) },
    { key: 'product', header: 'محصول', value: (d) => d.crop?.flavor || 'ناشناخته', render: (d) => <span className="font-medium text-foreground">{d.crop ? `${d.crop.flavor}` : 'نامشخص'}</span> },
    { key: 'brand', header: 'برند', value: (d) => d.crop?.brand || '—', render: (d) => d.crop?.brand || <span className="text-muted-foreground">—</span> },
    { key: 'flavor', header: 'طعم', value: (d) => d.crop?.flavor || '—', render: (d) => d.crop?.flavor || '—' },
    { key: 'size', header: 'سایز', value: (d) => d.crop?.size || '—', render: (d) => d.crop?.size || '—' },
    { key: 'conf', header: 'اطمینان مدل', sortable: true, value: (d) => d.confidence, render: (d) => (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full" style={{ width: `${d.confidence * 100}%`, backgroundColor: d.confidence > 0.8 ? '#16a34a' : '#d97706' }} />
        </div>
        <span className="text-xs font-medium text-foreground">{faPct(d.confidence * 100, 0)}</span>
      </div>
    ) },
    { key: 'status', header: 'وضعیت', sortable: true, value: (d) => d.status, render: (d) => <StatusBadge status={d.status} /> },
  ];

  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-r-2 border-brand p-5">
          <h2 className="text-lg font-bold text-foreground">تحلیل تصویر قفسه</h2>
          <p className="mt-1.5 max-w-3xl text-sm text-muted-foreground">
            هوش مصنوعی یک عکس خام از قفسه را به داده‌های ساختاریافته خرده‌فروشی تبدیل می‌کند: تشخیص محصول، شناسایی SKU، شمارش facings و محاسبه سهم قفسه.
          </p>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {stage === 'idle' && (
        <div className="rounded-xl border-2 border-dashed border-border bg-card p-10">
          <div className="mx-auto flex max-w-md flex-col items-center text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand/10 text-brand">
              <Upload className="h-8 w-8" />
            </div>
            <h3 className="text-base font-bold text-foreground">بارگذاری تصویر قفسه</h3>
            <p className="mt-1.5 text-xs text-muted-foreground">یک عکس از قفسه محصولات را برای تحلیل هوشمند بارگذاری کنید</p>
            <button onClick={() => fileInputRef.current?.click()} className="mt-5 flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand/90">
              <ScanLine className="h-4 w-4" /> انتخاب و تحلیل تصویر
            </button>
          </div>
        </div>
      )}

      {stage === 'error' && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-10">
          <div className="mx-auto flex max-w-md flex-col items-center text-center">
            <AlertTriangle className="h-10 w-10 text-destructive" />
            <h3 className="mt-3 text-base font-bold text-foreground">تحلیل ناموفق بود</h3>
            <p className="mt-1.5 text-xs text-muted-foreground">{error}</p>
            <button onClick={() => setStage('idle')} className="mt-5 flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand/90">
              <Upload className="h-4 w-4" /> تلاش دوباره
            </button>
          </div>
        </div>
      )}

      {stage === 'processing' && (
        <div className="rounded-xl border border-border bg-card p-10">
          <div className="mx-auto flex max-w-md flex-col items-center text-center">
            <div className="relative mb-5">
              <Loader2 className="h-14 w-14 animate-spin text-brand" />
            </div>
            <h3 className="flex items-center gap-2 text-base font-bold text-foreground">
              <Camera className="h-4 w-4 text-brand" /> در حال تحلیل تصویر قفسه…
            </h3>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {progress.total ? `${toFa(progress.done)} از ${toFa(progress.total)} شیء طبقه‌بندی شد` : 'مدل بینایی ماشین در حال شناسایی محصولات است'}
            </p>
            <div className="mt-5 w-full">
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-brand transition-all duration-150" style={{ width: `${pct}%` }} />
              </div>
              <div className="mt-3 space-y-1.5">
                {steps.map((s, i) => (
                  <div key={s} className={`flex items-center gap-2 text-xs ${stepIndex > i ? 'text-foreground' : 'text-muted-foreground/50'}`}>
                    {stepIndex > i ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    {s}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {stage === 'done' && (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <SectionCard title="تصویر تحلیل‌شده" subtitle="تصویر بارگذاری‌شده شما" className="lg:col-span-2" bodyClassName="p-3">
              <div className="relative overflow-hidden rounded-lg">
                <img src={imageUrl} alt="قفسه تحلیل‌شده" className="w-full rounded-lg" />
                {detections.map((d) => (
                  <div
                    key={d.id}
                    className="absolute rounded transition hover:opacity-100"
                    style={{
                      left: `${d.x}%`, top: `${d.y}%`, width: `${d.w}%`, height: `${d.h}%`,
                      border: `2px solid ${BOX_COLOR[d.status]}`,
                      boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
                      opacity: 0.9,
                    }}
                  >
                    <span className="absolute -top-0.5 right-0 rounded-bl px-1 text-[8px] font-bold text-white" style={{ backgroundColor: BOX_COLOR[d.status] }}>
                      {faPct(d.confidence * 100, 0)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-2 flex items-center gap-3 px-1 text-[10px] text-muted-foreground">
                {Object.entries(BOX_COLOR).map(([s, c]) => (
                  <span key={s} className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: c }} /> {s}</span>
                ))}
              </div>
            </SectionCard>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <KpiCard label="محصولات شناسایی‌شده" value={detectedCount} icon={Package} accent />
                <KpiCard label="محصولات ناشناخته" value={unknownCount} icon={HelpCircle} />
                <KpiCard label="کل facings" value={totalFacings} icon={Layers} />
                <KpiCard label="کل تشخیص‌ها" value={detections.length} icon={Eye} />
              </div>
              <SectionCard title="برندهای موجود" subtitle="در این قفسه">
                <div className="space-y-2">
                  {brandList.length === 0 && (
                    <p className="text-xs text-muted-foreground">برندی با اطمینان کافی شناسایی نشد</p>
                  )}
                  {brandList.map(({ b, c }) => (
                    <div key={b} className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground">{b}</span>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-foreground">{toFa(c)} facing</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-sm font-bold text-foreground">نتایج تشخیص</h3>
            <DataTable
              columns={columns}
              data={detections}
              pageSize={7}
              initialSort={{ key: 'conf', dir: 'desc' }}
              searchPlaceholder="جستجوی محصول یا برند…"
              emptyTitle="تشخیصی یافت نشد"
            />
          </div>

          <button onClick={() => setStage('idle')} className="flex items-center gap-2 text-xs font-medium text-brand hover:underline">
            <Upload className="h-3.5 w-3.5" /> تحلیل تصویر جدید
          </button>
        </>
      )}
    </div>
  );
}
