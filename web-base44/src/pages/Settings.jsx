import React, { useState } from 'react';
import { User, Bell, Palette, Shield, Info, Check, Moon, Sun, Globe } from 'lucide-react';
import SectionCard from '@/components/SectionCard';

export default function Settings() {
  const [notif, setNotif] = useState({ reports: true, alerts: true, weekly: false });
  const [theme, setTheme] = useState('light');
  const [lang, setLang] = useState('fa');

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="border-r-2 border-brand pr-3">
          <h2 className="text-lg font-bold text-foreground">تنظیمات</h2>
          <p className="mt-1 text-sm text-muted-foreground">مدیریت حساب، ترجیحات و اعلان‌های سامانه</p>
        </div>
      </div>

      {/* Account */}
      <SectionCard title="حساب کاربری" subtitle="اطلاعات حساب شما">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">ر</div>
          <div className="flex-1">
            <p className="text-sm font-bold text-foreground">رضا محمدی</p>
            <p className="text-xs text-muted-foreground">reza.mohammadi@retail-analytics.ir</p>
            <p className="mt-1 inline-block rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand">مدیر فروش</p>
          </div>
        </div>
      </SectionCard>

      {/* Preferences */}
      <SectionCard title="ترجیحات" subtitle="ظاهر و زبان سامانه">
        <div className="space-y-4">
          <Row icon={theme === 'dark' ? Moon : Sun} label="پوسته" desc="حالت روشن یا تیره">
            <div className="inline-flex rounded-lg border border-border p-0.5">
              {['light', 'dark'].map((t) => (
                <button key={t} onClick={() => setTheme(t)} className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${theme === t ? 'bg-brand text-brand-foreground' : 'text-muted-foreground'}`}>
                  {t === 'light' ? 'روشن' : 'تیره'}
                </button>
              ))}
            </div>
          </Row>
          <Row icon={Globe} label="زبان" desc="زبان نمایش سامانه">
            <div className="inline-flex rounded-lg border border-border p-0.5">
              {[{ id: 'fa', label: 'فارسی' }, { id: 'en', label: 'English' }].map((l) => (
                <button key={l.id} onClick={() => setLang(l.id)} className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${lang === l.id ? 'bg-brand text-brand-foreground' : 'text-muted-foreground'}`}>{l.label}</button>
              ))}
            </div>
          </Row>
        </div>
      </SectionCard>

      {/* Notifications */}
      <SectionCard title="اعلان‌ها" subtitle="مدیریت اعلان‌های سامانه">
        <div className="space-y-1">
          <ToggleRow icon={Bell} label="گزارش‌های جدید" desc="اطلاع‌رسانی پس از تولید گزارش" on={notif.reports} onChange={(v) => setNotif((n) => ({ ...n, reports: v }))} />
          <ToggleRow icon={Shield} label="هشدارهای توزیع" desc="اطلاع از شکاف‌های توزیع بحرانی" on={notif.alerts} onChange={(v) => setNotif((n) => ({ ...n, alerts: v }))} />
          <ToggleRow icon={Info} label="خلاصه هفتگی" desc="گزارش جمع‌بندی هر هفته" on={notif.weekly} onChange={(v) => setNotif((n) => ({ ...n, weekly: v }))} />
        </div>
      </SectionCard>

      <p className="pb-2 text-center text-[11px] text-muted-foreground">سامانه هوشمند پایش بازار و قفسه فروشگاه‌ها · نسخه ۱.۰.۰</p>
    </div>
  );
}

function Row({ icon: Icon, label, desc, children }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-muted-foreground"><Icon className="h-4 w-4" /></div>
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-[11px] text-muted-foreground">{desc}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function ToggleRow({ icon: Icon, label, desc, on, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-3 last:border-0">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-muted-foreground"><Icon className="h-4 w-4" /></div>
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-[11px] text-muted-foreground">{desc}</p>
        </div>
      </div>
      <button onClick={() => onChange(!on)} className={`relative h-6 w-11 rounded-full transition ${on ? 'bg-brand' : 'bg-muted'}`}>
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${on ? 'right-0.5' : 'right-[22px]'}`} />
      </button>
    </div>
  );
}