// Persian locale helpers: digits, numbers, percentages, Jalali dates

const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

export const toFa = (val) => {
  if (val === null || val === undefined || val === '') return '';
  return String(val).replace(/[0-9]/g, (d) => FA_DIGITS[+d]);
};

export const faNum = (n, dec = 0) => {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  const num = Number(n);
  const formatted = num.toLocaleString('en-US', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return toFa(formatted);
};

export const faPct = (n, dec = 1) => {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${toFa(Number(n).toFixed(dec))}٪`;
};

export const faCompact = (n) => {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  const num = Number(n);
  if (Math.abs(num) >= 1000) {
    return `${toFa((num / 1000).toFixed(1))} هزار`;
  }
  return faNum(num);
};

// Jalali (Solar Hijri) date conversion — standard algorithm
function div(a, b) { return Math.trunc(a / b); }
function mod(a, b) { return a - Math.trunc(a / b) * b; }

function toJalaali(gy, gm, gd) {
  let sal_a, sal_b, gy2, days, jy, jm, jd;
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  gy2 = gm > 2 ? gy + 1 : gy;
  days = 355666 + 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) + gd + g_d_m[gm - 1];
  jy = -1595 + 33 * Math.floor(days / 12053);
  days = mod(days, 12053);
  jy += 4 * Math.floor(days / 1461);
  days = mod(days, 1461);
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = mod(days - 1, 365);
  }
  if (days < 186) {
    jm = 1 + Math.floor(days / 31);
    jd = 1 + mod(days, 31);
  } else {
    jm = 7 + Math.floor((days - 186) / 30);
    jd = 1 + mod(days - 186, 30);
  }
  return { jy, jm, jd };
}

const J_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];

export const faDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const { jy, jm, jd } = toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  return `${toFa(jy)}/${toFa(String(jm).padStart(2, '0'))}/${toFa(String(jd).padStart(2, '0'))}`;
};

export const faDateLong = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const { jy, jm, jd } = toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  return `${toFa(jd)} ${J_MONTHS[jm - 1]} ${toFa(jy)}`;
};

export const faDateTime = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${faDate(iso)} - ${toFa(hh)}:${toFa(mm)}`;
};

export const relativeDaysLabel = (iso) => {
  if (!iso) return '—';
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 86400000);
  if (diff <= 0) return 'امروز';
  if (diff === 1) return 'دیروز';
  if (diff < 7) return `${toFa(diff)} روز پیش`;
  if (diff < 30) return `${toFa(Math.floor(diff / 7))} هفته پیش`;
  return `${toFa(Math.floor(diff / 30))} ماه پیش`;
};