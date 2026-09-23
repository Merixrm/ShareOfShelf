import { toFa } from './format';

// ============================================================================
// Mock data engine for the Retail Shelf Intelligence platform.
// Deterministic (seeded) so charts/maps/tables stay stable across renders.
// ============================================================================

function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(73);
const rand = () => rng();
const rint = (min, max) => Math.floor(rand() * (max - min + 1)) + min;
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const chance = (p) => rand() < p;

// ----------------------------------------------------------------------------
// Reference data
// ----------------------------------------------------------------------------
export const BRANDS = [
  { id: 'sunich', name: 'سن ایچ', short: 'Sunich', color: '#2f6fed' },
  { id: 'sunstar', name: 'سان استار', short: 'Sun Star', color: '#dc2626' },
  { id: 'golshan', name: 'گلشن', short: 'Golshan', color: '#16a34a' },
];

export const FLAVORS = [
  'سیب', 'پرتقال', 'هلو', 'آلبالو', 'آناناس', 'پیناکولادا', 'انبه', 'انار', 'میکس',
];

export const SIZES = ['250 میلی‌لیتر', '750 میلی‌لیتر', '1 لیتر'];

const FLAVOR_CODE = {
  'سیب': 'APP', 'پرتقال': 'ORG', 'هلو': 'PCH', 'آلبالو': 'CHY', 'آناناس': 'PIN',
  'پیناکولادا': 'PNC', 'انبه': 'MNG', 'انار': 'POM', 'میکس': 'MIX',
};
const SIZE_CODE = { '250 میلی‌لیتر': '025', '750 میلی‌لیتر': '075', '1 لیتر': '100' };
const SIZE_FACING_AREA = { '250 میلی‌لیتر': 120, '750 میلی‌لیتر': 270, '1 لیتر': 360 };

const BRAND_FLAVORS = {
  sunich: ['سیب', 'پرتقال', 'هلو', 'آلبالو', 'آناناس', 'پیناکولادا', 'انبه', 'انار', 'میکس'],
  sunstar: ['سیب', 'پرتقال', 'هلو', 'انبه', 'میکس'],
  golshan: ['پرتقال', 'آلبالو', 'انار', 'انبه', 'میکس'],
};
const BRAND_SIZES = {
  sunich: ['250 میلی‌لیتر', '750 میلی‌لیتر', '1 لیتر'],
  sunstar: ['250 میلی‌لیتر', '1 لیتر'],
  golshan: ['250 میلی‌لیتر', '750 میلی‌لیتر'],
};

const FLAVOR_HEX = {
  'سیب': '#7fb069', 'پرتقال': '#f5933b', 'هلو': '#f6b59a', 'آلبالو': '#b9302f',
  'آناناس': '#f2d34a', 'پیناکولادا': '#efe2c0', 'انبه': '#f6a12e', 'انار': '#a32638', 'میکس': '#8b5cf6',
};

// ----------------------------------------------------------------------------
// Products
// ----------------------------------------------------------------------------
let pSeq = 0;
export const products = (() => {
  const list = [];
  BRANDS.forEach((b) => {
    BRAND_FLAVORS[b.id].forEach((flavor) => {
      BRAND_SIZES[b.id].forEach((size) => {
        pSeq += 1;
        const sku = `${b.short.slice(0, 2).toUpperCase()}-${FLAVOR_CODE[flavor]}-${SIZE_CODE[size]}`;
        list.push({
          id: `P${String(pSeq).padStart(3, '0')}`,
          sku,
          brand: b.name,
          brandId: b.id,
          flavor,
          size,
          color: b.color,
          flavorColor: FLAVOR_HEX[flavor],
          active: chance(0.92),
        });
      });
    });
  });
  return list;
})();

export const productById = Object.fromEntries(products.map((p) => [p.id, p]));
export const productBySku = Object.fromEntries(products.map((p) => [p.sku, p]));
export const brandById = Object.fromEntries(BRANDS.map((b) => [b.id, b]));
export const brandByName = Object.fromEntries(BRANDS.map((b) => [b.name, b]));

// ----------------------------------------------------------------------------
// Stores — distributed around Mashhad (36.2972, 59.6062)
// ----------------------------------------------------------------------------
const MASHHAD = { lat: 36.2972, lng: 59.6062 };

const DISTRICTS = [
  { name: 'احمدآباد', lat: 36.3185, lng: 59.5891 },
  { name: 'پیروزی', lat: 36.3322, lng: 59.6253 },
  { name: 'سجاد', lat: 36.3489, lng: 59.6088 },
  { name: 'وکیل‌آباد', lat: 36.3178, lng: 59.6442 },
  { name: 'هاشمیه', lat: 36.3024, lng: 59.5701 },
  { name: 'فرامرز', lat: 36.2887, lng: 59.6333 },
  { name: 'شریعتی', lat: 36.3055, lng: 59.6055 },
  { name: 'فرهنگ', lat: 36.2912, lng: 59.5878 },
  { name: 'سناباد', lat: 36.2819, lng: 59.6212 },
  { name: 'خواجه ربیع', lat: 36.2733, lng: 59.5834 },
  { name: 'کوهسنگی', lat: 36.3011, lng: 59.6612 },
  { name: 'طلاب', lat: 36.2658, lng: 59.6101 },
  { name: 'قاسم‌آباد', lat: 36.3247, lng: 59.5765 },
  { name: 'عشرت‌آباد', lat: 36.2843, lng: 59.5499 },
  { name: 'ملک‌آباد', lat: 36.3389, lng: 59.6333 },
  { name: 'نواب صفوی', lat: 36.2978, lng: 59.5968 },
  { name: 'شیخ بهایی', lat: 36.3112, lng: 59.6498 },
  { name: 'سعادت‌آباد', lat: 36.2766, lng: 59.6377 },
  { name: 'امام رضا', lat: 36.2888, lng: 59.6155 },
  { name: 'پارک ملت', lat: 36.3098, lng: 59.5533 },
  { name: 'هرنگ', lat: 36.3265, lng: 59.6601 },
  { name: 'هفت تیر', lat: 36.2995, lng: 59.5712 },
  { name: 'بلوار وکیل', lat: 36.3221, lng: 59.6512 },
  { name: 'گلبهار', lat: 36.3412, lng: 59.5401 },
  { name: 'چالیک', lat: 36.2689, lng: 59.6488 },
  { name: 'فردیس', lat: 36.2866, lng: 59.5588 },
  { name: 'خیام', lat: 36.2933, lng: 59.6012 },
  { name: 'ملاصدرا', lat: 36.3155, lng: 59.6266 },
];

const STORE_PREFIXES = ['هایپرمارکت', 'سوپرمارکت', 'مینی‌مارکت', 'فروشگاه', 'هایپر'];
const STORE_SUFFIXES = ['رفاه', 'افشار', 'کهن‌مو', 'علی‌آبادی', 'ستاره', 'آرمان', 'پاسارگاد', 'نوین', 'طلوع', 'برکت', 'مهدی', 'پرومکس', 'گندم', 'زرگر', 'حسن‌زاده', 'کوروش', 'نماز', 'شهرداری', 'آفتاب', 'زرشک', 'مهر', 'دانش', 'سلامت', 'دلتا'];

export const stores = DISTRICTS.map((d, i) => {
  const jitter = 0.0045;
  const lat = d.lat + (rand() - 0.5) * jitter * 2;
  const lng = d.lng + (rand() - 0.5) * jitter * 2;
  const name = `${pick(STORE_PREFIXES)} ${pick(STORE_SUFFIXES)}`;
  return {
    id: `S${String(i + 1).padStart(2, '0')}`,
    name: `${name} ${i + 1}`,
    bareName: `${name}`,
    district: d.name,
    latitude: lat,
    longitude: lng,
    address: `مشهد، ${d.name}، ${pick(['بلوار اصلی', 'خیابان فرعی', 'میدان مرکزی', 'نبش کوچه'])} ${toFa(i + 3)}`,
  };
});

export const storeById = Object.fromEntries(stores.map((s) => [s.id, s]));

// ----------------------------------------------------------------------------
// Observations — multiple weekly snapshots per carried (store, product)
// ----------------------------------------------------------------------------
const NOW = new Date('2026-09-09T09:00:00').getTime();

function daysAgoIso(days) {
  return new Date(NOW - days * 86400000).toISOString();
}

// Which products does each store carry? (creates realistic distribution gaps)
const storeAssortment = stores.map((s) => {
  const primary = pick(BRANDS).id;
  const secondary = pick(BRANDS.filter((b) => b.id !== primary)).id;
  const carried = new Set();
  products.forEach((p) => {
    let prob = 0.12;
    if (p.brandId === primary) prob = 0.82;
    else if (p.brandId === secondary) prob = 0.4;
    if (chance(prob)) carried.add(p.id);
  });
  return { storeId: s.id, primary, secondary, carried };
});

let obsSeq = 0;
export const observations = (() => {
  const list = [];
  storeAssortment.forEach(({ storeId, carried }) => {
    carried.forEach((pid) => {
      const baseCount = rint(2, 7);
      const trend = pick([1, 1, 1, 1.25, 0.8, 1.1]); // gentle trend multiplier
      const weeks = rint(3, 4);
      for (let w = 0; w < weeks; w++) {
        const days = rint(2, 86);
        const count = Math.max(1, Math.round(baseCount * Math.pow(trend, w) * (0.85 + rand() * 0.3)));
        list.push({
          id: `O${String(++obsSeq).padStart(5, '0')}`,
          product_id: pid,
          store_id: storeId,
          detected_count: count,
          confidence: +(0.78 + rand() * 0.21).toFixed(2),
          shelf_area: Math.round(SIZE_FACING_AREA[productById[pid].size] * count * (0.92 + rand() * 0.16)),
          observed_at: daysAgoIso(days),
        });
      }
    });
  });
  return list;
})();

export const obsByProduct = observations.reduce((acc, o) => {
  (acc[o.product_id] ||= []).push(o);
  return acc;
}, {});
export const obsByStore = observations.reduce((acc, o) => {
  (acc[o.store_id] ||= []).push(o);
  return acc;
}, {});

// ----------------------------------------------------------------------------
// Filtering — central to "filters actually update everything"
// ----------------------------------------------------------------------------
export const ALL_FILTERS = { brandId: null, flavor: null, size: null, sku: null, dateFrom: null, dateTo: null };

export function getFilteredObservations(f = ALL_FILTERS) {
  return observations.filter((o) => {
    const p = productById[o.product_id];
    if (!p) return false;
    if (f.brandId && p.brandId !== f.brandId) return false;
    if (f.flavor && p.flavor !== f.flavor) return false;
    if (f.size && p.size !== f.size) return false;
    if (f.sku && p.id !== f.sku && p.sku !== f.sku) return false;
    if (f.dateFrom && o.observed_at < f.dateFrom) return false;
    if (f.dateTo && o.observed_at > f.dateTo) return false;
    return true;
  });
}

// Distinct (product,store) pairs present in a filtered observation set
function carriedPairs(obs) {
  const seen = new Map(); // key -> {pid, sid, count, area, last, conf}
  obs.forEach((o) => {
    const key = `${o.product_id}|${o.store_id}`;
    const cur = seen.get(key);
    if (!cur) {
      seen.set(key, {
        pid: o.product_id, sid: o.store_id, count: o.detected_count, area: o.shelf_area, last: o.observed_at, conf: o.confidence,
      });
    } else {
      cur.count += o.detected_count;
      cur.area += o.shelf_area;
      if (o.observed_at > cur.last) { cur.last = o.observed_at; cur.conf = o.confidence; }
    }
  });
  return [...seen.values()];
}

// ----------------------------------------------------------------------------
// KPIs
// ----------------------------------------------------------------------------
export function computeKpis(f = ALL_FILTERS) {
  const obs = getFilteredObservations(f);
  const productIds = new Set(obs.map((o) => o.product_id));
  const storeIds = new Set(obs.map((o) => o.store_id));
  const totalArea = obs.reduce((s, o) => s + o.shelf_area, 0);
  const totalFacings = obs.reduce((s, o) => s + o.detected_count, 0);
  const avgSos = totalFacings ? totalArea / (totalFacings * 240) : 0; // normalized share index 0..1
  const regions = new Set([...storeIds].map((id) => storeById[id]?.district).filter(Boolean));

  // previous period: same window shifted back by its length
  const dates = obs.map((o) => +new Date(o.observed_at));
  let prevCount = 0;
  if (dates.length) {
    const min = Math.min(...dates);
    const max = Math.max(...dates);
    const span = Math.max(1, max - min);
    const prevObs = observations.filter((o) => {
      const t = +new Date(o.observed_at);
      return t >= min - span && t < min && matchesFilter(o, f);
    });
    prevCount = prevObs.length;
  }
  const delta = prevCount ? ((obs.length - prevCount) / prevCount) * 100 : 0;

  return {
    products: productIds.size,
    skus: productIds.size,
    stores: storeIds.size,
    observations: obs.length,
    avgSos: avgSos * 100,
    regions: regions.size,
    deltaPct: delta,
    totalArea,
    totalFacings,
  };
}

function matchesFilter(o, f) {
  const p = productById[o.product_id];
  if (!p) return false;
  if (f.brandId && p.brandId !== f.brandId) return false;
  if (f.flavor && p.flavor !== f.flavor) return false;
  if (f.size && p.size !== f.size) return false;
  if (f.sku && p.id !== f.sku && p.sku !== f.sku) return false;
  return true;
}

// ----------------------------------------------------------------------------
// Brand analytics
// ----------------------------------------------------------------------------
export function brandPresenceData(f = ALL_FILTERS) {
  const obs = getFilteredObservations(f);
  const byBrand = {};
  BRANDS.forEach((b) => { byBrand[b.id] = { brand: b.name, color: b.color, stores: new Set(), observations: 0 }; });
  obs.forEach((o) => {
    const p = productById[o.product_id];
    const row = byBrand[p.brandId];
    if (!row) return;
    row.observations += 1;
    row.stores.add(o.store_id);
  });
  return Object.values(byBrand).map((r) => ({ ...r, stores: r.stores.size })).sort((a, b) => b.observations - a.observations);
}

export function shareOfShelfData(f = ALL_FILTERS) {
  const obs = getFilteredObservations(f);
  const byBrand = {};
  BRANDS.forEach((b) => { byBrand[b.id] = { brand: b.name, color: b.color, facings: 0, area: 0 }; });
  obs.forEach((o) => {
    const p = productById[o.product_id];
    const row = byBrand[p.brandId];
    if (!row) return;
    row.facings += o.detected_count;
    row.area += o.shelf_area;
  });
  const totalFacings = Object.values(byBrand).reduce((s, r) => s + r.facings, 0);
  const totalArea = Object.values(byBrand).reduce((s, r) => s + r.area, 0);
  return Object.values(byBrand).map((r) => ({
    brand: r.brand,
    color: r.color,
    facings: r.facings,
    area: r.area,
    facingsPct: totalFacings ? (r.facings / totalFacings) * 100 : 0,
    areaPct: totalArea ? (r.area / totalArea) * 100 : 0,
  })).sort((a, b) => b.facings - a.facings);
}

export function marketCoverageData(f = ALL_FILTERS) {
  const obs = getFilteredObservations(f);
  const totalStores = new Set(obs.map((o) => o.store_id)).size || stores.length;
  const byBrand = {};
  BRANDS.forEach((b) => { byBrand[b.id] = { brand: b.name, color: b.color, stores: new Set() }; });
  obs.forEach((o) => {
    const p = productById[o.product_id];
    byBrand[p.brandId]?.stores.add(o.store_id);
  });
  return Object.values(byBrand).map((r) => ({
    brand: r.brand, color: r.color, stores: r.stores.size, coverage: totalStores ? (r.stores.size / totalStores) * 100 : 0,
  })).sort((a, b) => b.coverage - a.coverage);
}

// Weekly trend for a brand (or all) over last 12 weeks
export function brandTrendData(f = ALL_FILTERS, brandId = null) {
  const weeks = 12;
  const buckets = Array.from({ length: weeks }, (_, i) => ({
    label: `${toFa(weeks - i)}` + ' هفته پیش',
    key: weeks - 1 - i,
    byBrand: {},
    total: 0,
  }));
  observations.forEach((o) => {
    const p = productById[o.product_id];
    if (!p) return;
    if (f.brandId && p.brandId !== f.brandId) return;
    if (f.flavor && p.flavor !== f.flavor) return;
    if (f.size && p.size !== f.size) return;
    if (f.sku && p.id !== f.sku && p.sku !== f.sku) return;
    const daysAgo = Math.floor((NOW - new Date(o.observed_at).getTime()) / 86400000);
    const w = Math.floor(daysAgo / 7);
    if (w < 0 || w >= weeks) return;
    const idx = weeks - 1 - w;
    buckets[idx].total += o.detected_count;
    buckets[idx].byBrand[p.brandId] = (buckets[idx].byBrand[p.brandId] || 0) + o.detected_count;
  });
  const series = BRANDS.map((b) => ({ name: b.name, color: b.color, data: buckets.map((bk) => bk.byBrand[b.id] || 0) }));
  return { labels: buckets.map((b) => b.label), series, total: buckets.map((b) => b.total) };
}

export function topProducts(f = ALL_FILTERS, n = 10) {
  const obs = getFilteredObservations(f);
  const byP = {};
  obs.forEach((o) => {
    const r = byP[o.product_id] ||= { product: productById[o.product_id], count: 0, stores: new Set(), last: '' };
    r.count += o.detected_count;
    r.stores.add(o.store_id);
    if (o.observed_at > r.last) r.last = o.observed_at;
  });
  return Object.values(byP)
    .map((r) => ({ product: r.product, count: r.count, stores: r.stores.size, last: r.last }))
    .sort((a, b) => b.count - a.count)
    .slice(0, n);
}

// ----------------------------------------------------------------------------
// Product intelligence
// ----------------------------------------------------------------------------
export function productDetail(productId) {
  const p = productById[productId];
  if (!p) return null;
  const obs = obsByProduct[productId] || [];
  const storeIds = new Set(obs.map((o) => o.store_id));
  const totalDetections = obs.reduce((s, o) => s + o.detected_count, 0);
  const storeObjs = [...storeIds].map((id) => storeById[id]).filter(Boolean);
  // share of shelf for this product = its area / total area in those stores
  let myArea = 0;
  const storeTotals = {};
  obs.forEach((o) => {
    myArea += o.shelf_area;
    storeTotals[o.store_id] = (storeTotals[o.store_id] || 0) + o.shelf_area;
  });
  const allStoreObs = observations.filter((o) => storeIds.has(o.store_id));
  const totalArea = allStoreObs.reduce((s, o) => s + o.shelf_area, 0);
  const sos = totalArea ? (myArea / totalArea) * 100 : 0;

  // trend (weekly counts)
  const weeks = 12;
  const trend = Array.from({ length: weeks }, () => 0);
  obs.forEach((o) => {
    const daysAgo = Math.floor((NOW - new Date(o.observed_at).getTime()) / 86400000);
    const w = Math.floor(daysAgo / 7);
    if (w >= 0 && w < weeks) trend[weeks - 1 - w] += o.detected_count;
  });

  // competitors: other products co-occurring in same stores, ranked
  const compStores = new Set(obs.map((o) => o.store_id));
  const compCount = {};
  allStoreObs.forEach((o) => {
    if (o.product_id === productId) return;
    const op = productById[o.product_id];
    if (!op) return;
    compCount[o.product_id] ||= { product: op, stores: new Set() };
    compCount[o.product_id].stores.add(o.store_id);
  });
  const competitors = Object.values(compCount)
    .map((r) => ({ product: r.product, stores: r.stores.size }))
    .sort((a, b) => b.stores - a.stores)
    .slice(0, 6);

  const recent = [...obs].sort((a, b) => +new Date(b.observed_at) - +new Date(a.observed_at)).slice(0, 6);

  // status
  const status = sos > 12 ? 'محرک رشد' : sos > 5 ? 'پایدار' : 'نیازمند توجه';

  return {
    product: p,
    storeCoverage: storeIds.size,
    geoPoints: storeObjs.map((s) => ({ ...s, product: p })),
    totalDetections,
    sos,
    trend,
    competitors,
    recent,
    status,
    lastSeen: recent[0]?.observed_at,
  };
}

// ----------------------------------------------------------------------------
// Store intelligence
// ----------------------------------------------------------------------------
export function storeDetail(storeId) {
  const s = storeById[storeId];
  if (!s) return null;
  const obs = obsByStore[storeId] || [];
  const productIds = new Set(obs.map((o) => o.product_id));
  const byBrand = {};
  BRANDS.forEach((b) => { byBrand[b.id] = { brand: b.name, color: b.color, facings: 0, area: 0, stores: 0 }; });
  obs.forEach((o) => {
    const p = productById[o.product_id];
    const r = byBrand[p.brandId];
    if (!r) return;
    r.facings += o.detected_count;
    r.area += o.shelf_area;
  });
  const totalFacings = Object.values(byBrand).reduce((a, r) => a + r.facings, 0);
  const totalArea = Object.values(byBrand).reduce((a, r) => a + r.area, 0);
  const sosByBrand = Object.values(byBrand).map((r) => ({
    brand: r.brand, color: r.color, facings: r.facings, area: r.area,
    facingsPct: totalFacings ? (r.facings / totalFacings) * 100 : 0,
    areaPct: totalArea ? (r.area / totalArea) * 100 : 0,
  })).filter((r) => r.facings > 0).sort((a, b) => b.facings - a.facings);

  const dominant = sosByBrand[0]?.brand || '—';
  const lastInspection = [...obs].sort((a, b) => +new Date(b.observed_at) - +new Date(a.observed_at))[0]?.observed_at;

  // missing products (from brands present in this store but products not detected)
  const presentBrands = new Set([...productIds].map((id) => productById[id]?.brandId));
  const missing = products.filter((p) => presentBrands.has(p.brandId) && !productIds.has(p.id));

  // distribution opportunities: products NOT here but common in nearby stores
  const nearby = nearbyStores(storeId, 6, 0.05);
  const oppByProduct = {};
  nearby.forEach((ns) => {
    (obsByStore[ns.id] || []).forEach((o) => {
      const p = productById[o.product_id];
      if (!p || productIds.has(o.product_id)) return;
      oppByProduct[o.product_id] ||= { product: p, count: 0, stores: new Set() };
      oppByProduct[o.product_id].count += o.detected_count;
      oppByProduct[o.product_id].stores.add(ns.name);
    });
  });
  const opportunities = Object.values(oppByProduct)
    .map((r) => ({ product: r.product, nearbyCount: r.count, nearbyStores: r.stores.size }))
    .filter((r) => r.nearbyCount >= 4)
    .sort((a, b) => b.nearbyCount - a.nearbyCount)
    .slice(0, 6);

  return {
    store: s,
    products: [...productIds].map((id) => productById[id]).filter(Boolean),
    brands: [...presentBrands].map((id) => brandById[id]).filter(Boolean),
    observationCount: obs.length,
    lastInspection,
    sosByBrand,
    dominant,
    missing,
    opportunities,
  };
}

export function nearbyStores(storeId, n = 5, maxKm = 8) {
  const s = storeById[storeId];
  if (!s) return [];
  return stores
    .filter((x) => x.id !== storeId)
    .map((x) => ({ ...x, dist: haversine(s.latitude, s.longitude, x.latitude, x.longitude) }))
    .filter((x) => x.dist <= maxKm)
    .sort((a, b) => a.dist - b.dist)
    .slice(0, n);
}

function haversine(la1, lo1, la2, lo2) {
  const R = 6371;
  const dLat = ((la2 - la1) * Math.PI) / 180;
  const dLng = ((lo2 - lo1) * Math.PI) / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos((la1 * Math.PI) / 180) * Math.cos((la2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ----------------------------------------------------------------------------
// Map data
// ----------------------------------------------------------------------------
export function mapPoints(f = ALL_FILTERS) {
  const obs = getFilteredObservations(f);
  const byStore = {};
  obs.forEach((o) => {
    const p = productById[o.product_id];
    const s = storeById[o.store_id];
    if (!p || !s) return;
    const cur = byStore[o.store_id] ||= {
      store: s, lat: s.latitude, lng: s.longitude, observations: 0, products: new Set(), brands: new Set(),
      flavors: new Set(), sizes: new Set(), last: '', count: 0,
    };
    cur.observations += 1;
    cur.count += o.detected_count;
    cur.products.add(p.id);
    cur.brands.add(p.brand);
    cur.flavors.add(p.flavor);
    cur.sizes.add(p.size);
    if (o.observed_at > cur.last) cur.last = o.observed_at;
  });
  return Object.values(byStore).map((r) => ({
    ...r, products: r.products.size, brands: [...r.brands], flavors: [...r.flavors], sizes: [...r.sizes],
  }));
}

// ----------------------------------------------------------------------------
// Unknown products (AI cannot confidently recognize)
// ----------------------------------------------------------------------------
const UNKNOWN_STATUSES = ['تأیید شده', 'تأیید جزئی', 'نامشخص'];
export const unknownProducts = Array.from({ length: 9 }, (_, i) => {
  const b = pick(BRANDS);
  const flavor = pick(FLAVORS);
  const size = pick(SIZES);
  const conf = +(0.4 + rand() * 0.45).toFixed(2);
  return {
    id: `U${String(i + 1).padStart(2, '0')}`,
    color: b.color,
    flavorColor: FLAVOR_HEX[flavor],
    possibleBrand: b.name,
    possibleFlavor: flavor,
    possibleSize: size,
    confidence: conf,
    status: conf > 0.7 ? 'تأیید شده' : conf > 0.55 ? 'تأیید جزئی' : 'نامشخص',
    firstSeen: daysAgoIso(rint(1, 40)),
    storeId: pick(stores).id,
  };
});

// ----------------------------------------------------------------------------
// Shelf analyses (computer-vision results)
// ----------------------------------------------------------------------------
export const shelfAnalyses = (() => {
  const list = [];
  stores.slice(0, 10).forEach((s, idx) => {
    const detCount = rint(8, 18);
    const unknownCount = rint(0, 3);
    const detections = Array.from({ length: detCount }, (_, j) => {
      const known = chance(0.86);
      const p = known ? pick(products) : null;
      const x = Math.round((rand() * 70 + (j % 5) * 6));
      const y = Math.round((rand() * 60 + Math.floor(j / 5) * 22));
      const w = rint(7, 12);
      const h = rint(14, 22);
      return {
        id: `D${idx}-${j}`,
        crop: p,
        x, y, w, h,
        confidence: p ? +(0.78 + rand() * 0.21).toFixed(2) : +(0.4 + rand() * 0.25).toFixed(2),
        status: p ? (rand() > 0.12 ? 'شناسایی‌شده' : 'نیازمند بررسی') : 'محصول ناشناخته',
      };
    });
    list.push({
      id: `SA${String(idx + 1).padStart(2, '0')}`,
      storeId: s.id,
      storeName: s.name,
      analyzedAt: daysAgoIso(rint(1, 30)),
      detections,
      detectedCount: detCount,
      unknownCount,
      totalFacings: detections.reduce((a, d) => a + (d.crop ? 1 : 0), 0),
    });
  });
  return list;
})();

// ----------------------------------------------------------------------------
// Geographic opportunities (commercial insight cards)
// ----------------------------------------------------------------------------
export function opportunityInsights(f = ALL_FILTERS) {
  const insights = [];
  BRANDS.forEach((b) => {
    const obs = getFilteredObservations({ ...f, brandId: b.id });
    const myStores = new Set(obs.map((o) => o.store_id));
    const competitors = BRANDS.filter((x) => x.id !== b.id);
    // find districts where brand is weak but competitors strong
    const byDistrict = {};
    stores.forEach((s) => { byDistrict[s.district] = { district: s.district, mine: 0, comp: 0, stores: new Set() }; });
    obs.forEach((o) => { const s = storeById[o.store_id]; if (s) byDistrict[s.district].mine += o.detected_count; byDistrict[s.district].stores.add(o.store_id); });
    observations.forEach((o) => {
      const p = productById[o.product_id];
      if (!p || p.brandId === b.id) return;
      if (f.flavor && p.flavor !== f.flavor) return;
      if (f.size && p.size !== f.size) return;
      const s = storeById[o.store_id]; if (!s) return;
      byDistrict[s.district].comp += o.detected_count;
    });
    Object.values(byDistrict).forEach((d) => {
      if (d.comp > d.mine * 1.8 && d.comp > 10) {
        insights.push({
          id: `${b.id}-${d.district}`,
          brand: b.name,
          color: b.color,
          district: d.district,
          mine: d.mine,
          comp: d.comp,
          severity: d.mine === 0 ? 'بحرانی' : d.comp > d.mine * 3 ? 'بالا' : 'متوسط',
          text: `محصول‌های ${b.name} در منطقه ${d.district} حضور پایینی دارد، در حالی که رقبا در ${toFa(Math.min(d.stores.size, 12))} فروشگاه اطراف مشاهده شده‌اند.`,
        });
      }
    });
  });
  return insights.sort((a, b) => b.comp - a.mine - (a.comp - a.mine)).slice(0, 8);
}

// Hot/weak areas summary
export function areaStrengthData(f = ALL_FILTERS) {
  const byArea = {};
  stores.forEach((s) => { byArea[s.district] = { district: s.district, count: 0, stores: 0 }; });
  const obs = getFilteredObservations(f);
  const seen = new Set();
  obs.forEach((o) => {
    const s = storeById[o.store_id];
    if (!s) return;
    byArea[s.district].count += o.detected_count;
  });
  stores.forEach((s) => { byArea[s.district].stores += 1; });
  return Object.values(byArea).sort((a, b) => b.count - a.count);
}

export const MASHHAD_CENTER = MASHHAD;
export { toFa };