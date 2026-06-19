// Cloudflare Worker: приймає замовлення зворотного дзвінка з сайту
// і надсилає сповіщення у Telegram-бот.
//
// Secrets / vars (через wrangler або дашборд Cloudflare):
//   TG_BOT_TOKEN — токен бота від @BotFather                 [secret]
//   TG_CHAT_ID   — твій chat_id (куди слати сповіщення)       [var]
//
// Сайт (index.html) робить POST { name, phone } -> сюди.

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
    if (!env.TG_BOT_TOKEN || !env.TG_CHAT_ID) return json({ error: "Telegram is not configured" }, 500);

    try {
      const body = await request.json().catch(() => ({}));
      const name = String(body.name || "").slice(0, 80).trim();
      const phone = String(body.phone || "").slice(0, 40).trim();
      if (!name || !phone) return json({ error: "name and phone required" }, 400);

      const text =
        "📞 Замовлення дзвінка з сайту\n\n" +
        "Ім'я: " + name + "\n" +
        "Телефон: " + phone;

      const botToken = String(env.TG_BOT_TOKEN).trim();
      const chatId = String(env.TG_CHAT_ID).trim();
      const r = await fetch("https://api.telegram.org/bot" + botToken + "/sendMessage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, text }),
      });
      const data = await r.json();
      if (!data.ok) return json({ error: "telegram_error", detail: data }, 502);

      return json({ ok: true }, 200);
    } catch (e) {
      return json({ error: String((e && e.message) || e) }, 500);
    }
  },
};
