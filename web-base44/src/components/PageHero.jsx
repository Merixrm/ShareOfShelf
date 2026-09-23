import React from 'react';

export default function PageHero({ title, subtitle, children }) {
  return (
    <div className="mb-5 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="border-r-2 border-brand pr-3">
          <h2 className="text-lg font-bold text-foreground sm:text-xl">{title}</h2>
          {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>}
        </div>
        {children && <div className="w-full lg:w-auto">{children}</div>}
      </div>
    </div>
  );
}