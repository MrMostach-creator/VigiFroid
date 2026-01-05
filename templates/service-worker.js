/* ==========================================================
   🧠 VigiFroid Service Worker — Hardened Precaching & Runtime
   Offline-first assets + safe page caching + image fallback
   ========================================================== */

const CACHE_VERSION = "{{ config.ASSET_VERSION }}";
const PRECACHE = `vf-precache-${CACHE_VERSION}`;
const RUNTIME  = `vf-runtime-${CACHE_VERSION}`;

const DB_NAME = "vigifroid-db";
const STORE_PENDING = "pending-operations";

// ⚠️ ما نكاشيوش صفحات auth
const AUTH_PATHS = [
  "/auth/login",
  "/auth/logout",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/welcome"
];

const PRECACHE_URLS = [
  "{{ url_for('main.index') }}",
  "/offline.html",
  "/static/lang/fr.json",
  "/static/lang/ar.json",
  "/static/lang/en.json",
  "/manifest.json",
  "{{ url_for('static', filename='css/app.min.css', v=config.ASSET_VERSION) }}",
  "{{ url_for('static', filename='js/app.min.js', v=config.ASSET_VERSION) }}",
  "{{ url_for('static', filename='images/vigifroid_icon.png', v=config.ASSET_VERSION) }}",
  "{{ url_for('static', filename='images/safran_icon.png', v=config.ASSET_VERSION) }}",
  "{{ url_for('static', filename='manifest.json', v=config.ASSET_VERSION) }}",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
  "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
];

// ========== IndexedDB utils ==========
function openDB() {
  return new Promise((res, rej) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;

      if (!db.objectStoreNames.contains(STORE_PENDING))
        db.createObjectStore(STORE_PENDING, { keyPath: "id", autoIncrement: true });

      if (!db.objectStoreNames.contains("lots"))
        db.createObjectStore("lots", { keyPath: "id" });

      if (!db.objectStoreNames.contains("logs"))
        db.createObjectStore("logs", { keyPath: "timestamp" });
    };
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}
function txComplete(tx) {
  return new Promise((res, rej) => {
    tx.oncomplete = () => res();
    tx.onerror = tx.onabort = () => rej(tx.error);
  });
}

// ========== Helpers ==========
function isAuthURL(u) {
  try {
    const p = new URL(u, self.location.origin).pathname;
    return AUTH_PATHS.some(ap => p.startsWith(ap));
  } catch { return false; }
}
function isSamePath(u1, u2) {
  try {
    const a = new URL(u1, self.location.origin);
    const b = new URL(u2, self.location.origin);
    return a.pathname === b.pathname;
  } catch { return false; }
}
function shouldCacheResponse(reqUrl, res) {
  try {
    if (!res || !res.ok) return false;
    if (res.redirected) return false;

    const url = new URL(res.url);
    if (url.origin !== self.location.origin) return true; // CDN ok

    // ما نخزّنش auth pages
    if (isAuthURL(url.href)) return false;

    // احترام no-store إلا كان
    const cc = (res.headers.get("Cache-Control") || "").toLowerCase();
    if (cc.includes("no-store")) return false;

    return true;
  } catch {
    return false;
  }
}

// ========== INSTALL ==========
self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const cache = await caches.open(PRECACHE);

    await Promise.allSettled(PRECACHE_URLS.map(async (rawUrl) => {
      try {
        const res = await fetch(rawUrl, { cache: "no-store", redirect: "follow" });
        const ok = res.ok && !res.redirected && isSamePath(rawUrl, res.url);
        if (ok) {
          await cache.put(rawUrl, res.clone());
          console.log("✅ Precached:", rawUrl);
        } else {
          console.warn("⏭️ Skip precache:", rawUrl, "→", res.status, res.url);
        }
      } catch (err) {
        console.warn("⚠️ Network skip:", rawUrl, err);
      }
    }));

    console.log("✅ Service Worker installed");
  })());

  self.skipWaiting();
});

// ========== ACTIVATE ==========
self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => (k !== PRECACHE && k !== RUNTIME) ? caches.delete(k) : null));
    await self.clients.claim();
    console.log("🔥 Service Worker activated");
  })());
});

// ========== FETCH ==========
self.addEventListener("fetch", event => {
  const req = event.request;

  // POST/PUT/DELETE ⇒ store offline
  if (["POST","PUT","DELETE"].includes(req.method)) {
    event.respondWith((async () => {
      try {
        return await fetch(req.clone());
      } catch {
        try {
          const body = await req.clone().json().catch(()=>({}));
          await savePendingOperation(req.url, req.method, body);
        } catch {}
        return new Response(JSON.stringify({ offline:true, saved:true }), {
          headers:{ "Content-Type":"application/json" }
        });
      }
    })());
    return;
  }

  // 📄 Pages (navigate/document): Network-first
  if (req.mode === "navigate" || req.destination === "document") {
    event.respondWith((async () => {
      const runtime = await caches.open(RUNTIME);
      const precache = await caches.open(PRECACHE);

      try {
        const net = await fetch(req);

        // ما نكاشيوش auth pages
        if (shouldCacheResponse(req.url, net)) {
          // نخزّن غير نفس-origin pages (باش ما نديرش مشاكل فـ keys)
          try { await runtime.put(req, net.clone()); } catch {}
        }

        return net;
      } catch {
        return (await runtime.match(req)) ||
               (await precache.match(req)) ||
               (await precache.match("/offline.html")) ||
               new Response("Offline", { status: 503 });
      }
    })());
    return;
  }

  // 🧩 Assets (css/js/images/fonts): Cache-first
  event.respondWith((async () => {
    const runtime = await caches.open(RUNTIME);
    const cached = await runtime.match(req);
    if (cached) return cached;

    try {
      const r = await fetch(req);
      if (shouldCacheResponse(req.url, r)) {
        try { await runtime.put(req, r.clone()); } catch {}
      }
      return r;
    } catch {
      // ✅ مهم: فالأوفلاين الصور ما خاصهاش ترجع offline.html
      if (req.destination === "image") {
        const precache = await caches.open(PRECACHE);
        return (await precache.match("/static/images/vigifroid_icon.png?v={{ config.ASSET_VERSION }}")) ||
               (await precache.match("/static/images/vigifroid_icon.png")) ||
               new Response("", { status: 504 });
      }

      const precache = await caches.open(PRECACHE);
      return (await precache.match("/offline.html")) || new Response("", { status: 504 });
    }
  })());
});

// ========== Save pending ops ==========
async function savePendingOperation(url, method, body) {
  const db = await openDB();
  const tx = db.transaction(STORE_PENDING, "readwrite");
  tx.objectStore(STORE_PENDING).add({ url, method, body, timestamp:new Date().toISOString() });
  await txComplete(tx);
  console.log("💾 Pending op saved:", method, url);
}

// ========== Sync pending ops ==========
self.addEventListener("sync", e => {
  if (e.tag === "sync-pending-operations") e.waitUntil(syncPendingOperations());
});
async function syncPendingOperations() {
  const db = await openDB();
  const tx = db.transaction(STORE_PENDING, "readwrite");
  const store = tx.objectStore(STORE_PENDING);
  const all = await new Promise((res,rej)=>{
    const r=store.getAll(); r.onsuccess=()=>res(r.result); r.onerror=()=>rej(r.error);
  });

  for (const op of all) {
    try {
      const r = await fetch(op.url,{
        method: op.method,
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify(op.body)
      });
      if (r.ok) {
        const del = db.transaction(STORE_PENDING,"readwrite");
        del.objectStore(STORE_PENDING).delete(op.id);
        await txComplete(del);
        console.log("✅ Synced:", op.method, op.url);
      }
    } catch (err) {
      console.warn("❌ Sync fail:", op.url, err);
    }
  }
}

// ========== MESSAGE HANDLER ==========
self.addEventListener("message", async event => {
  try {
    const { type, data, urls } = event.data || {};
    const db = await openDB();

    // Save lots locally
    if (type === "LOTS_SAVE" && Array.isArray(data)) {
      const tx = db.transaction("lots","readwrite");
      const store = tx.objectStore("lots");
      data.forEach(l=>{ try{store.put(l);}catch{} });
      await txComplete(tx);
      console.log(`💾 Lots saved locally: ${data.length}`);
    }

    // Cache images URLs (ex: /uploads/xxx.jpg)
    if (type === "CACHE_URLS" && Array.isArray(urls) && urls.length) {
      const runtime = await caches.open(RUNTIME);

      await Promise.allSettled(urls.map(async (u)=>{
        try {
          const existing = await runtime.match(u);
          if (existing) return;

          const res = await fetch(u, { cache:"no-store", redirect:"follow" });
          if (res.ok && !res.redirected) {
            await runtime.put(u, res.clone());
            console.log("🖼 cached img:", u);
          } else {
            console.warn("⚠️ image skip:", u, res.status);
          }
        } catch (e) {
          console.warn("⚠️ image skip:", u, e);
        }
      }));
    }

    if (type === "TRIGGER_SYNC") syncPendingOperations();

  } catch (err) {
    console.error("❌ Message handler error:", err);
  }
});
