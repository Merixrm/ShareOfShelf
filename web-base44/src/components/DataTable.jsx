import React, { useState, useMemo } from 'react';
import { Search, ChevronRight, ChevronLeft, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { toFa } from '@/lib/format';
import EmptyState from './EmptyState';

export default function DataTable({
  columns, data, pageSize = 8, searchable = true, searchPlaceholder = 'جستجو…',
  onRowClick, emptyTitle = 'موردی یافت نشد', emptyDescription = 'با تغییر فیلترها دوباره تلاش کنید.',
  initialSort = null,
}) {
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState(initialSort?.key ?? null);
  const [sortDir, setSortDir] = useState(initialSort?.dir ?? 'desc');
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    let rows = data;
    if (query && searchable) {
      const q = query.trim().toLowerCase();
      rows = rows.filter((r) =>
        columns.some((c) => {
          const v = c.searchValue ? c.searchValue(r) : c.value ? c.value(r) : r[c.key];
          return String(v ?? '').toLowerCase().includes(q);
        })
      );
    }
    if (sortKey) {
      const col = columns.find((c) => c.key === sortKey);
      rows = [...rows].sort((a, b) => {
        const av = col.sortValue ? col.sortValue(a) : col.value ? col.value(a) : a[sortKey];
        const bv = col.sortValue ? col.sortValue(b) : col.value ? col.value(b) : b[sortKey];
        if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av;
        return sortDir === 'asc'
          ? String(av ?? '').localeCompare(String(bv ?? ''), 'fa')
          : String(bv ?? '').localeCompare(String(av ?? ''), 'fa');
      });
    }
    return rows;
  }, [data, query, sortKey, sortDir, columns, searchable]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const pageRows = filtered.slice(currentPage * pageSize, currentPage * pageSize + pageSize);

  const toggleSort = (col) => {
    if (!col.sortable) return;
    if (sortKey === col.key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(col.key); setSortDir(col.defaultDir || 'desc'); }
    setPage(0);
  };

  return (
    <div className="space-y-3">
      {searchable && (
        <div className="relative max-w-xs">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(0); }}
            placeholder={searchPlaceholder}
            className="h-9 w-full rounded-lg border border-border bg-background pr-9 pl-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>
      )}
      <div className="overflow-x-auto rounded-xl border border-border scrollbar-thin">
        <table className="w-full text-right text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`whitespace-nowrap px-4 py-3 font-medium ${c.sortable ? 'cursor-pointer select-none hover:text-foreground' : ''} ${c.className || ''}`}
                  onClick={() => toggleSort(c)}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.header}
                    {c.sortable && (
                      sortKey === c.key ? (
                        sortDir === 'asc' ? <ArrowUp className="h-3 w-3 text-brand" /> : <ArrowDown className="h-3 w-3 text-brand" />
                      ) : <ArrowUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  <EmptyState title={emptyTitle} description={emptyDescription} />
                </td>
              </tr>
            ) : (
              pageRows.map((row, i) => (
                <tr
                  key={row.id ?? i}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`transition-colors ${onRowClick ? 'cursor-pointer hover:bg-muted/40' : ''}`}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={`px-4 py-3 align-middle ${c.cellClassName || ''}`}>
                      {c.render ? c.render(row) : (c.value ? c.value(row) : row[c.key])}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {filtered.length > pageSize && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            نمایش {toFa(currentPage * pageSize + 1)} تا {toFa(Math.min((currentPage + 1) * pageSize, filtered.length))} از {toFa(filtered.length)} مورد
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={currentPage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border transition hover:bg-muted disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <span className="px-2 font-medium text-foreground">{toFa(currentPage + 1)} / {toFa(totalPages)}</span>
            <button
              type="button"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border transition hover:bg-muted disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}