// Serverless-функція для створення інвойсу Monobank Acquiring.
// Працює на Vercel (та сумісних платформах) як /api/create-invoice.
//
// Потрібні змінні середовища (Environment Variables) на хостингу:
//   MONOBANK_TOKEN  — токен мерчанта з кабінету https://web.monobank.ua/ (Acquiring)
//   SITE_URL        — базовий URL сайту, напр. https://your-site.vercel.app  (необов'язково)
//   WEBHOOK_URL     — URL для вебхука статусу оплати (необов'язково)
//
// Клієнт (booking.html) робить POST { date, time, amount } і отримує { pageUrl }.

export default async function handler(req, res) {
  // CORS — дозволяємо виклик зі сторінки бронювання
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  const token = process.env.MONOBANK_TOKEN;
  if (!token) return res.status(500).json({ error: "MONOBANK_TOKEN is not configured" });

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const date = String(body.date || "").slice(0, 20);
    const time = String(body.time || "").slice(0, 10);
    // Сума передоплати у копійках. Мінімум 1000 грн, ігноруємо те, що прийшло з клієнта якщо менше.
    const amountUah = Math.max(Number(body.amount) || 0, 1000);
    const amount = Math.round(amountUah * 100);

    const reference = "booking-" + date.replace(/\D/g, "") + "-" + time.replace(/\D/g, "");

    const payload = {
      amount,
      ccy: 980, // UAH
      merchantPaymInfo: {
        reference,
        destination: `Передоплата за фотозйомку ${date} ${time}`.trim(),
      },
    };
    if (process.env.SITE_URL) payload.redirectUrl = process.env.SITE_URL.replace(/\/$/, "") + "/booking.html?paid=1";
    if (process.env.WEBHOOK_URL) payload.webHookUrl = process.env.WEBHOOK_URL;

    const r = await fetch("https://api.monobank.ua/api/merchant/invoice/create", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Token": token },
      body: JSON.stringify(payload),
    });

    const data = await r.json();
    if (!r.ok) return res.status(502).json({ error: "monobank_error", detail: data });

    // data: { invoiceId, pageUrl }
    return res.status(200).json({ pageUrl: data.pageUrl, invoiceId: data.invoiceId });
  } catch (e) {
    return res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
}
