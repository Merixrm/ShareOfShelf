import React from 'react';

const MAP = {
  'محرک رشد': { cls: 'bg-success/10 text-success', dot: 'bg-success' },
  'پایدار': { cls: 'bg-primary/10 text-primary', dot: 'bg-primary' },
  'نیازمند توجه': { cls: 'bg-destructive/10 text-destructive', dot: 'bg-destructive' },
  'شناسایی‌شده': { cls: 'bg-success/10 text-success', dot: 'bg-success' },
  'نیازمند بررسی': { cls: 'bg-warning/15 text-warning', dot: 'bg-warning' },
  'محصول ناشناخته': { cls: 'bg-destructive/10 text-destructive', dot: 'bg-destructive' },
  'تأیید شده': { cls: 'bg-success/10 text-success', dot: 'bg-success' },
  'تأیید جزئی': { cls: 'bg-warning/15 text-warning', dot: 'bg-warning' },
  'نامشخص': { cls: 'bg-muted text-muted-foreground', dot: 'bg-muted-foreground' },
  'بحرانی': { cls: 'bg-destructive/10 text-destructive', dot: 'bg-destructive' },
  'بالا': { cls: 'bg-warning/15 text-warning', dot: 'bg-warning' },
  'متوسط': { cls: 'bg-primary/10 text-primary', dot: 'bg-primary' },
};

export default function StatusBadge({ status }) {
  const m = MAP[status] || { cls: 'bg-muted text-muted-foreground', dot: 'bg-muted-foreground' };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${m.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {status}
    </span>
  );
}