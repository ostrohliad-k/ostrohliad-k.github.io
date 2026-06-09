// Cloudflare Worker: створення інвойсу Monobank Acquiring.
// Викликається зі сторінки booking.html (на GitHub Pages) через CORS.
//
// Secrets / vars (налаштовуються через wrangler або в дашборді Cloudflare):
//   MONOBANK_TOKEN — токен мерчанта (інтернет-еквайринг Monobank)   [secret]
//   SITE_URL       — https://ostrohliad-k.github.io  (для повернення після оплати) [var, optional]
//   WEBHOOK_URL    — URL для статусів оплати (optional)

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
    if (!env.MONOBANK_TOKEN) return json({ error: "MONOBANK_TOKEN is not configured" }, 500);

    try {
      const body = await request.json().catch(() => ({}));
      const date = String(body.date || "").slice(0, 20);
      const time = String(body.time || "").slice(0, 10);
      const amountUah = Math.max(Number(body.amount) || 0, 1000);   // мінімум 1000 грн
      const amount = Math.round(amountUah * 100);                   // у копійках

      const payload = {
        amount,
        ccy: 980, // UAH
        merchantPaymInfo: {
          reference: "booking-" + date.replace(/\D/g, "") + "-" + time.replace(/\D/g, ""),
          destination: ("Передоплата за фотозйомку " + date + " " + time).trim(),
        },
      };
      if (env.SITE_URL) payload.redirectUrl = env.SITE_URL.replace(/\/$/, "") + "/booking.html?paid=1";
      if (env.WEBHOOK_URL) payload.webHookUrl = env.WEBHOOK_URL;

      const r = await fetch("https://api.monobank.ua/api/merchant/invoice/create", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Token": env.MONOBANK_TOKEN },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) return json({ error: "monobank_error", detail: data }, 502);

      return json({ pageUrl: data.pageUrl, invoiceId: data.invoiceId }, 200);
    } catch (e) {
      return json({ error: String((e && e.message) || e) }, 500);
    }
  },
};
