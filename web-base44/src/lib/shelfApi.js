// Client for the local read-only detection API (shelf_api.py) — turns an
// uploaded shelf photo into real per-SKU boxes, statuses and share-of-shelf
// numbers, in the same shape ShelfAnalysis.jsx used to get from mock data.
//
// An absolute URL is required, not a relative `/api/...` fetch: the Base44
// vite plugin installs its own dev-server proxy on the "/api" prefix pointing
// at the Base44 backend, so a same-origin call would be silently swallowed by
// that proxy under `base44 dev`. See shelf_api.py's docstring for the server side.
import { brandById } from './mockData';

export const API_BASE = import.meta.env.VITE_SHELF_API_URL || 'http://127.0.0.1:8001';

// KB label vocabulary -> the app's existing Persian vocabulary (mockData.js),
// so a real detection is a first-class citizen everywhere else in the app.
const KB_FLAVOR_FA = {
  apple: 'سیب', orange: 'پرتقال', peach: 'هلو', cherry: 'آلبالو',
  pineapple: 'آناناس', pinacolada: 'پیناکولادا', mango: 'انبه',
  pomegranate: 'انار', mix: 'میکس',
};
const KB_SIZE_FA = { '1L': '1 لیتر', '750ml': '750 میلی‌لیتر' };

const STATUS_FA = {
  identified: 'شناسایی‌شده',
  unknown: 'محصول ناشناخته',
  low_confidence: 'نیازمند بررسی',
};

// "sunich_1L_apple" -> { brand, flavor, size } | null (null when the label
// isn't a real SKU, i.e. status is unknown/low_confidence).
function parseProductLabel(label) {
  const [brandId, sizeKey, ...rest] = label.split('_');
  const brand = brandById[brandId];
  const flavor = KB_FLAVOR_FA[rest.join('_')];
  const size = KB_SIZE_FA[sizeKey];
  if (!brand || !flavor || !size) return null;
  return { brand: brand.name, flavor, size };
}

async function apiFetch(path, options) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch {
    throw new Error(
      'به سرور تشخیص محصول متصل نشد. مطمئن شوید «python shelf_api.py» در حال اجراست.'
    );
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `خطای سرور (${res.status})`);
  }
  return res.json();
}

async function upload(file) {
  const { path } = await apiFetch(`/api/upload?name=${encodeURIComponent(file.name)}`, {
    method: 'POST',
    body: file,
  });
  return path;
}

async function detect(imagePath) {
  const { session } = await apiFetch('/api/detect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imagePath, tta: true }),
  });
  return session;
}

function pollSession(sessionId, onProgress) {
  return new Promise((resolve, reject) => {
    const tick = async () => {
      let session;
      try {
        session = await apiFetch(`/api/session/${sessionId}`);
      } catch (e) {
        return reject(e);
      }
      onProgress?.(session);
      if (session.status === 'ready') return resolve(session);
      if (session.status === 'error') return reject(new Error(session.error || 'تحلیل ناموفق بود.'));
      setTimeout(tick, 600);
    };
    tick();
  });
}

/**
 * Upload `file`, run real detection + classification, and resolve with the
 * finished session. `onProgress(session)` fires on every poll tick so the UI
 * can show real done/total counts instead of a simulated timer.
 */
export async function uploadAndAnalyze(file, onProgress) {
  const imagePath = await upload(file);
  const sessionId = await detect(imagePath);
  return pollSession(sessionId, onProgress);
}

// session.crops -> the detection shape ShelfAnalysis.jsx renders (percent-based
// box, status, and a resolved product or null for unknown/low_confidence rows).
export function toDetections(session) {
  const { width, height } = session;
  return session.crops.map((c) => {
    const [x1, y1, x2, y2] = c.box;
    return {
      id: c.id,
      x: (x1 / width) * 100,
      y: (y1 / height) * 100,
      w: ((x2 - x1) / width) * 100,
      h: ((y2 - y1) / height) * 100,
      confidence: c.score,
      status: STATUS_FA[c.status],
      cropUrl: `${API_BASE}${c.url}`,
      crop: c.status === 'identified' ? parseProductLabel(c.predicted) : null,
    };
  });
}
