import os, re, json, unicodedata, glob

# ══════════════════════════════════════════════════════════════════
#  НАЛАШТУВАННЯ
# ══════════════════════════════════════════════════════════════════
OUTPUT_FILE   = "index.html"
PHOTOS_BASE   = "photos"

# ── Оптимізація зображень для вебу (WebP) ──
# Оригінали в PHOTOS_BASE не змінюються. Згенеровані версії складаються у WEB_BASE:
#   web/thumbs/...  — прев'ю для сітки галереї
#   web/full/...    — облегшені повнорозмірні для лайтбоксу
WEB_BASE      = "web"
THUMB_MAX     = 1000   # макс. сторона прев'ю, px
FULL_MAX      = 2000   # макс. сторона повного фото, px
Q_THUMB       = 82     # якість WebP для прев'ю
Q_FULL        = 80     # якість WebP для повного фото

HERO_IMAGE    = "photos/Heros/Image.jpg"   # головна картинка
ABOUT_IMAGE   = "photos/Heros/About.jpg"   # фото в розділі "Про мене" (додайте About.jpg у photos/Heros/)

SITE_URL = "https://ostrohliad.photo"      # адреса сайту (для прев'ю при поширенні / SEO)
CONTACT_EMAIL = "kateryna.ostrohlyd@icloud.com"   # пошта, на яку приходять заявки
INSTAGRAM_USER = "ostrohliad.k"            # нік в Instagram (для прямого повідомлення в Direct)

# ── Бронювання дати ──
BOOKING_OUTPUT  = "booking.html"           # сторінка з календарем бронювання
BOOKING_DEPOSIT = 1000                     # передоплата за бронювання, грн
# Бекенд для Monobank Acquiring (створення інвойсу). Після деплою
# serverless-функції api/create-invoice.js вставте сюди її повний URL,
# напр. "https://ваш-сайт.vercel.app/api/create-invoice".
# Поки порожнє — кнопка оплати працює у запасному режимі (нижче).
BOOKING_API_URL = ""
# Запасний варіант, якщо бекенд не підключено: статичне платіжне посилання
# (банка Monobank / Privat24 / Stripe Payment Link) на суму передоплати.
# Якщо й воно порожнє — кнопка відкриває Instagram Direct для підтвердження.
PAYMENT_LINK    = ""
# Робочі години та крок слотів для календаря
BOOKING_HOURS   = (10, 19)                 # з 10:00 до 19:00
BOOKING_STEP_MIN = 60                      # крок, хвилин

# Категорії: folder — назва підпапки, label — назва на сайті. Порядок = порядок на сайті.
CATEGORIES = {
    "individual": {"folder": "Individual", "label": "Індивідуальні та портретні зйомки"},
    "family":     {"folder": "Family",     "label": "Love story & Сімейні зйомки"},
    "reportage":  {"folder": "Reportage",  "label": "Репортажні зйомки"},
    "wedding":    {"folder": "Wedding",    "label": "Весілля"},
}

# Обкладинка категорії (квадрат у портфоліо). Вкажіть шлях до фото-оригіналу
# в папці photos/. Якщо порожньо — береться перше фото першої зйомки.
CATEGORY_COVERS = {
    "individual": "photos/Individual/Anna's sensual photoshoot/photo-243.JPG",
    "family":     "",
    "reportage":  "photos/Reportage/HB Mari/photo-514.JPG",
    "wedding":    "",
}

# Зйомки (папки), які НЕ показувати на сайті (оригінали лишаються на диску)
EXCLUDE_SHOOTS = {
    "2026-04-28_Family_shoot",
    "ALINA RETRO",
    "2026-02-19_Shoot_with_Musya",
}

# Перенесення окремих зйомок між категоріями (назва папки -> ключ категорії)
MOVE_SHOOTS = {}

# Обкладинка КОНКРЕТНОЇ зйомки: вказане фото стає першим (назва папки -> файл)
SHOOT_COVERS = {
    "2022-11-14_Photos_for_friends": "2022-11-14_2971450573309007269.jpg",
}

# Порядок зйомок у категорії: перелічені папки йдуть першими (категорія -> [папки])
SHOOT_ORDER = {
    "family": ["F2 FEDORCHUK"],
}

# Фото для розділу «Моя філософія» (3 шт.)
PHIL_PHOTOS = ["photos/Philosophy/IMG_6878.JPG", "photos/Philosophy/IMG_6932.JPG", "photos/Philosophy/IMG_8714.JPG"]

# Бекенд замовлення зворотного дзвінка (Cloudflare Worker -> Telegram).
# Поки порожньо — форма відкриває Instagram Direct із даними у буфері обміну.
CALLBACK_API_URL = "https://ostrohliad-callback.ostrohliad-k.workers.dev"
# ══════════════════════════════════════════════════════════════════

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_title(name):
    """Приводить назву папки до єдиного стилю (Title Case), щоб назви зйомок
    на сайті виглядали однаково. Прибирає дату-префікс, підкреслення, дужки,
    приховані/службові символи та технічні префікси (HB, F1/F2/F3).
    Напр.: 'ALINA RETRO'->'Alina Retro', 'HB Mari'->'Mari',
    '2020-09-01_Love_stories_in_shoots'->'Love Stories'."""
    # прибрати дату-префікс
    name = re.sub(r"^\d{4}[-_]\d{1,2}[-_]\d{1,2}[ _-]+", "", name)
    # прибрати приховані символи (приватна зона U+E000..U+F8FF та керівні)
    name = "".join(ch for ch in name
                   if not (0xE000 <= ord(ch) <= 0xF8FF)
                   and unicodedata.category(ch)[0] != "C")
    name = name.replace("_", " ")
    name = re.sub(r"[()]", " ", name)
    # прибрати технічні префікси: HB (Happy Birthday), F1/F2/F3 (родинні)
    name = re.sub(r"^\s*(HB|F\d)\s+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    return name.title()


def parse_shoot_name(name):
    """Повертає (нормалізована назва, '') — дати в назвах не показуємо."""
    return normalize_title(name), ""


def resolve_cover(path):
    """Знаходить файл обкладинки, навіть якщо в назві папки є прихований символ.
    У конфізі шлях можна писати 'чистою' назвою (напр. .../Anna/photo-243.JPG)."""
    if not path:
        return ""
    if os.path.exists(path):
        return path
    parent, fname = os.path.split(path)
    grand, folder = os.path.split(parent)
    if os.path.isdir(grand):
        clean = lambda s: "".join(c for c in s if ord(c) < 0xE000)
        for sub in os.listdir(grand):
            if clean(sub) == folder:
                cand = os.path.join(grand, sub, fname)
                if os.path.exists(cand):
                    return cand.replace("\\", "/")
    return path


def photos_in(path):
    files = sorted(f for f in os.listdir(path)
                   if not f.startswith(".")                       # пропускаємо ._* та .DS_Store (службові файли macOS)
                   and os.path.splitext(f)[1].lower() in EXTS)
    return [os.path.join(path, f).replace("\\", "/") for f in files]


# ── Оптимізація у WebP ──────────────────────────────────────────────
_opt_stats = {"made": 0, "skipped": 0, "failed": 0}


def _make_webp(src, dst, max_side, quality):
    """Створює зменшену WebP-версію src у dst (інкрементально за mtime)."""
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        _opt_stats["skipped"] += 1
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        from PIL import Image, ImageOps
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)          # врахувати орієнтацію з EXIF
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side), Image.LANCZOS)
            im.save(dst, "WEBP", quality=quality, method=6)
        _opt_stats["made"] += 1
        return True
    except Exception as e:
        _opt_stats["failed"] += 1
        print(f"  [!] не вдалося обробити {src}: {e}")
        return False


def optimize(src):
    """Повертає URL повнорозмірної WebP-версії (2000px), створюючи її за потреби.
    Галерея показує фото у повному якості на всіх рівнях."""
    rel = os.path.relpath(src, PHOTOS_BASE)
    rel_webp = os.path.splitext(rel)[0] + ".webp"
    full = os.path.join(WEB_BASE, "full", rel_webp).replace("\\", "/")
    ok = _make_webp(src, full, FULL_MAX, Q_FULL)
    return full if ok else src


def optimize_list(src_paths):
    """[шлях, ...] -> [url_повного_фото, ...]"""
    return [optimize(p) for p in src_paths]


def scan_category(folder_name):
    """Повертає список зйомок: [{title, date, photos:[...]}, ...]"""
    base = os.path.join(PHOTOS_BASE, folder_name)
    if not os.path.isdir(base):
        print(f"  [!] Папка '{base}' не знайдена")
        return []

    shoots = []

    # фото, що лежать прямо в корені категорії (без підпапки)
    loose = photos_in(base)
    if loose:
        shoots.append({"title": CATEGORIES_LABEL.get(folder_name, folder_name),
                       "date": "", "photos": optimize_list(loose)})

    # підпапки = окремі зйомки
    for shoot_name in sorted(os.listdir(base)):
        if shoot_name.startswith(".") or shoot_name in EXCLUDE_SHOOTS:
            continue
        shoot_path = os.path.join(base, shoot_name)
        if not os.path.isdir(shoot_path):
            continue
        photos = photos_in(shoot_path)
        if not photos:
            continue
        # за потреби ставимо обрану обкладинку зйомки першою
        cover_file = SHOOT_COVERS.get(shoot_name)
        if cover_file:
            want = (base + "/" + shoot_name + "/" + cover_file).replace("\\", "/")
            photos.sort(key=lambda p: 0 if p == want else 1)
        title, date = parse_shoot_name(shoot_name)
        shoots.append({"title": title, "date": date, "folder": shoot_name,
                       "photos": optimize_list(photos)})

    return shoots


CATEGORIES_LABEL = {v["folder"]: v["label"] for v in CATEGORIES.values()}


def build_data():
    data = {}
    for key, info in CATEGORIES.items():
        data[key] = {"label": info["label"], "shoots": scan_category(info["folder"])}

    # перенесення окремих зйомок між категоріями
    for folder_name, target in MOVE_SHOOTS.items():
        if target not in data:
            continue
        for key in list(data.keys()):
            if key == target:
                continue
            for s in data[key]["shoots"][:]:
                if s.get("folder") == folder_name:
                    data[key]["shoots"].remove(s)
                    data[target]["shoots"].append(s)
                    print(f"  → перенесено '{folder_name}' у категорію '{target}'")

    # порядок зйомок: вказані папки йдуть першими
    for key, order in SHOOT_ORDER.items():
        if key not in data:
            continue
        rank = {name: i for i, name in enumerate(order)}
        data[key]["shoots"].sort(key=lambda s: rank.get(s.get("folder"), len(order)))

    # обкладинки + підрахунок
    total = 0
    for key, info in CATEGORIES.items():
        shoots = data[key]["shoots"]
        n = sum(len(s["photos"]) for s in shoots)
        total += n
        cover_src = resolve_cover(CATEGORY_COVERS.get(key, ""))
        if cover_src and os.path.exists(cover_src):
            data[key]["cover"] = optimize(cover_src)      # повнорозмірна обкладинка (чітка)
        else:
            if CATEGORY_COVERS.get(key):
                print(f"  [!] Обкладинку '{CATEGORY_COVERS.get(key)}' не знайдено — беру перше фото")
            for s in shoots:                              # авто: перше фото
                if s["photos"]:
                    data[key]["cover"] = s["photos"][0]
                    break
        for s in shoots:           # прибрати службовий ключ перед JSON
            s.pop("folder", None)
        print(f"  {info['folder']}: {len(shoots)} зйомок, {n} фото")
    return data, total


TEMPLATE = r"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Катя Острогляд — фотограф | портретна, сімейна, весільна зйомка</title>
<meta name="description" content="Фотограф Катя Острогляд. Індивідуальні та портретні, сімейні, репортажні та весільні зйомки. Фотографія, яка повертає впевненість у собі.">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Катя Острогляд — фотограф">
<meta property="og:title" content="Катя Острогляд — фотограф">
<meta property="og:description" content="Індивідуальні, сімейні, репортажні та весільні зйомки. Фотографія, яка повертає впевненість у собі.">
<meta property="og:url" content="__SITEURL__/">
<meta property="og:image" content="__OGIMAGE__">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Катя Острогляд — фотограф">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Катя Острогляд — фотограф">
<meta name="twitter:description" content="Індивідуальні, сімейні, репортажні та весільні зйомки.">
<meta name="twitter:image" content="__OGIMAGE__">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Montserrat:wght@200;300;400&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --cream:#f8f5f0;--bone:#eae4d9;--charcoal:#141414;
  --warm-gray:#6b6358;--accent:#a9824f;--white:#ffffff;--text:#3d362d;
}
html{scroll-behavior:smooth;font-size:17px}
body{font-family:'Montserrat',sans-serif;background:var(--cream);color:var(--text);font-weight:400;line-height:1.6;overflow-x:hidden;-webkit-font-smoothing:antialiased}

nav{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;justify-content:space-between;align-items:center;padding:1.4rem 3.5rem;background:rgba(248,245,240,0.93);backdrop-filter:blur(10px);border-bottom:1px solid rgba(184,154,106,0.12)}
.logo{font-family:'Cormorant Garamond',serif;font-size:1.4rem;font-weight:300;letter-spacing:0.18em;color:var(--charcoal);text-decoration:none;text-transform:lowercase}
.nav-links{display:flex;gap:2.5rem;list-style:none}
.nav-links a{font-size:0.72rem;letter-spacing:0.16em;text-transform:uppercase;color:var(--warm-gray);text-decoration:none;transition:color 0.3s}
.nav-links a:hover{color:var(--charcoal)}
.burger{display:none;flex-direction:column;gap:5px;cursor:pointer;background:none;border:none;padding:4px}
.burger span{display:block;width:22px;height:1px;background:var(--charcoal);transition:all 0.3s}

.hero{height:100vh;display:flex;position:relative;overflow:hidden;background:var(--charcoal)}
.hero-img-main{position:absolute;inset:0;background:url('__HERO__') center/cover no-repeat;opacity:0.65}
.hero-overlay{position:absolute;inset:0;background:linear-gradient(to right,rgba(20,20,20,0.78) 0%,rgba(20,20,20,0.1) 60%,rgba(20,20,20,0.42) 100%)}
.hero-content{position:relative;z-index:2;display:flex;flex-direction:column;justify-content:flex-end;padding:0 3.5rem 5.5rem;max-width:620px}
.hero-label{font-size:0.68rem;letter-spacing:0.32em;text-transform:uppercase;color:var(--accent);margin-bottom:1.2rem;display:block}
.hero-title{font-family:'Cormorant Garamond',serif;font-size:3.5rem;font-weight:300;line-height:1.1;color:var(--white);margin-bottom:1.3rem}
.hero-title em{font-style:italic;color:rgba(255,255,255,0.55)}
.hero-sub{font-size:0.98rem;letter-spacing:0.02em;line-height:1.85;color:rgba(255,255,255,0.8);max-width:460px;margin-bottom:2.5rem}
.btn-outline{display:inline-block;padding:0.85rem 2.4rem;border:1px solid rgba(255,255,255,0.35);font-size:0.58rem;letter-spacing:0.25em;text-transform:uppercase;color:rgba(255,255,255,0.85);text-decoration:none;transition:all 0.4s;background:transparent}
.btn-outline:hover{background:rgba(255,255,255,0.1);border-color:rgba(255,255,255,0.65)}

.gallery{padding:6.5rem 3.5rem 6rem;background:var(--cream);min-height:80vh}
.gallery-header{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:2.5rem}
.section-label{font-size:0.7rem;letter-spacing:0.26em;text-transform:uppercase;color:var(--accent);margin-bottom:0.8rem;display:block}
.section-title{font-family:'Cormorant Garamond',serif;font-size:2.8rem;font-weight:300;line-height:1.15;color:var(--charcoal)}
.link-accent{font-size:0.58rem;letter-spacing:0.2em;text-transform:uppercase;color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(184,154,106,0.3);padding-bottom:2px}
.link-accent:hover{border-color:var(--accent)}

/* breadcrumb */
.gallery-crumb{display:flex;align-items:center;gap:0.6rem;margin-bottom:2rem;min-height:1rem;flex-wrap:wrap}
.crumb-link{background:none;border:none;font-family:'Montserrat',sans-serif;font-size:0.7rem;letter-spacing:0.14em;text-transform:uppercase;color:var(--accent);cursor:pointer;padding:0;transition:color 0.3s}
.crumb-link:hover{color:var(--charcoal)}
.crumb-sep{color:var(--warm-gray);font-size:0.65rem}
.crumb-current{font-size:0.7rem;letter-spacing:0.14em;text-transform:uppercase;color:var(--warm-gray)}

/* category squares */
.cat-squares{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.cat-square{position:relative;aspect-ratio:1/1;background-size:cover;background-position:center;cursor:pointer;overflow:hidden;background-color:var(--bone)}
.cat-square::after{content:'';position:absolute;inset:0;background:linear-gradient(to top,rgba(20,20,20,0.78) 0%,rgba(20,20,20,0.2) 45%,rgba(20,20,20,0.4) 100%);transition:background 0.45s}
.cat-square:hover::after{background:linear-gradient(to top,rgba(20,20,20,0.6) 0%,rgba(20,20,20,0.12) 45%,rgba(20,20,20,0.25) 100%)}
.cat-square-inner{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0.7rem;text-align:center;padding:1.5rem}
.cat-square-label{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:300;color:#fff;line-height:1.1}
.cat-square-count{font-size:0.7rem;letter-spacing:0.2em;text-transform:uppercase;color:rgba(255,255,255,0.82)}

/* shoot grid */
.shoot-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.shoot-card{cursor:pointer}
.shoot-card-imgwrap{overflow:hidden;background:var(--bone);aspect-ratio:4/5}
.shoot-card-img{width:100%;height:100%;object-fit:cover;display:block;filter:grayscale(12%);transition:transform 0.7s cubic-bezier(0.25,0.46,0.45,0.94),filter 0.5s}
.shoot-card:hover .shoot-card-img{transform:scale(1.04);filter:grayscale(0)}
.shoot-card-title{font-family:'Cormorant Garamond',serif;font-style:italic;font-size:1.25rem;color:var(--charcoal);display:block;line-height:1.3;margin-top:0.9rem}
.shoot-card-meta{font-size:0.66rem;letter-spacing:0.14em;text-transform:uppercase;color:var(--warm-gray);margin-top:0.35rem;display:block}

.photo-grid{columns:3;column-gap:12px}
.photo-item{break-inside:avoid;margin-bottom:12px;overflow:hidden;position:relative;cursor:pointer;background:var(--bone)}
.photo-item img{width:100%;display:block;transition:transform 0.7s cubic-bezier(0.25,0.46,0.45,0.94),filter 0.5s;filter:grayscale(12%)}
.photo-item:hover img{transform:scale(1.04);filter:grayscale(0)}

.cat-empty{font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-style:italic;color:var(--warm-gray);padding:3rem 0;text-align:center}

.lightbox{position:fixed;inset:0;background:rgba(0,0,0,0.96);z-index:500;display:flex;align-items:center;justify-content:center;opacity:0;visibility:hidden;transition:opacity 0.3s,visibility 0.3s}
.lightbox.open{opacity:1;visibility:visible}
.lb-img{max-width:88vw;max-height:88vh;object-fit:contain;display:block;user-select:none}
.lb-close{position:fixed;top:1.5rem;right:2rem;background:none;border:none;color:rgba(255,255,255,0.5);font-size:2rem;cursor:pointer;z-index:501;transition:color 0.3s;line-height:1;font-weight:200}
.lb-close:hover{color:var(--white)}
.lb-prev,.lb-next{position:fixed;top:50%;transform:translateY(-50%);background:none;border:none;color:rgba(255,255,255,0.35);font-size:2.5rem;cursor:pointer;z-index:501;transition:color 0.3s;padding:1.5rem;font-weight:200;line-height:1}
.lb-prev{left:0}.lb-next{right:0}
.lb-prev:hover,.lb-next:hover{color:var(--white)}
.lb-counter{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);font-size:0.55rem;letter-spacing:0.25em;color:rgba(255,255,255,0.3)}

.about{padding:7rem 3.5rem;background:var(--charcoal);display:flex;gap:6rem;align-items:center}
.about-img{flex:0 0 420px;height:560px;overflow:hidden;background:var(--charcoal)}
.about-img img{width:100%;height:100%;object-fit:cover;filter:grayscale(20%);display:block;
  -webkit-mask-image:linear-gradient(to right,transparent 0,#000 12%,#000 88%,transparent 100%),linear-gradient(to bottom,transparent 0,#000 10%,#000 90%,transparent 100%);
  mask-image:linear-gradient(to right,transparent 0,#000 12%,#000 88%,transparent 100%),linear-gradient(to bottom,transparent 0,#000 10%,#000 90%,transparent 100%);
  -webkit-mask-composite:source-in;mask-composite:intersect}
.about-text .section-title{color:#fff}
.about-body{font-size:1rem;line-height:1.95;color:rgba(255,255,255,0.74);margin:1.5rem 0 2rem}
.about-stats{display:flex;gap:3rem;margin-top:2.5rem;border-top:1px solid rgba(255,255,255,0.07);padding-top:2rem}
.stat-num{font-family:'Cormorant Garamond',serif;font-size:2.8rem;font-weight:300;color:var(--accent);display:block;line-height:1}
.stat-label{font-size:0.58rem;letter-spacing:0.2em;text-transform:uppercase;color:rgba(255,255,255,0.3);margin-top:0.4rem;display:block}

.philosophy{padding:7rem 3.5rem;background:var(--charcoal)}
.phil-grid{display:grid;grid-template-columns:1.05fr 0.95fr;gap:4.5rem;align-items:center}
.philosophy .section-title{color:#fff}
.philosophy .section-title em{font-style:italic;color:var(--accent)}
.phil-lead{font-family:'Cormorant Garamond',serif;font-style:italic;font-size:1.95rem;line-height:1.45;color:rgba(255,255,255,0.9);margin:1.6rem 0 1.8rem}
.phil-text p{font-size:1.02rem;line-height:1.9;color:rgba(255,255,255,0.58);margin-bottom:1.3rem}
.phil-text p strong{color:#fff;font-weight:400}
.phil-media{display:flex;gap:1.1rem;align-items:flex-start}
.phil-col{flex:1;display:flex;flex-direction:column;gap:1.1rem}
.phil-col-offset{margin-top:3.5rem}
.phil-media img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;background:#1f1f1f;filter:grayscale(10%)}
.phil-quote{font-family:'Cormorant Garamond',serif;font-style:italic;font-size:2.2rem;font-weight:300;line-height:1.42;color:#fff;text-align:center;max-width:900px;margin:5rem auto 0}
.phil-quote::before{content:'';display:block;width:42px;height:1px;background:var(--accent);margin:0 auto 2rem}
.phil-mission{max-width:680px;margin:2.6rem auto 0;text-align:center}
.phil-mission p{font-size:1.04rem;line-height:1.9;color:rgba(255,255,255,0.58)}
.phil-mission strong{color:var(--accent);font-weight:400}

.process{padding:7rem 3.5rem;background:var(--bone)}
.process-intro{font-size:1.04rem;line-height:1.9;color:var(--text);max-width:680px;margin-top:1.3rem}
.process-grid{display:grid;grid-template-columns:repeat(5,1fr);margin-top:3.5rem;border-top:1px solid rgba(184,154,106,0.25)}
.process-step{padding:2.5rem 1.6rem;border-right:1px solid rgba(184,154,106,0.25)}
.process-step:last-child{border-right:none}
.step-num{font-family:'Cormorant Garamond',serif;font-size:3.5rem;font-weight:300;color:rgba(184,154,106,0.2);line-height:1;display:block;margin-bottom:1rem}
.step-title{font-family:'Cormorant Garamond',serif;font-size:1.15rem;font-weight:400;margin-bottom:0.75rem}
.step-body{font-size:0.92rem;line-height:1.8;color:var(--text)}
.step-img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;margin-bottom:1.4rem;background:var(--bone);filter:grayscale(10%)}
.step-list{list-style:none;margin-top:0.7rem;display:flex;flex-direction:column;gap:0.4rem}
.step-list li{font-size:0.9rem;color:var(--text);display:flex;gap:0.55rem;line-height:1.5}
.step-list li::before{content:'—';color:var(--accent)}
.process-result{margin-top:4rem;border-top:1px solid rgba(184,154,106,0.25);padding-top:2.8rem}
.result-items{display:grid;grid-template-columns:repeat(4,1fr);gap:2.5rem;margin-top:1.4rem}
.result-item{display:flex;flex-direction:column;gap:0.7rem}
.result-num{font-family:'Cormorant Garamond',serif;font-size:2.1rem;font-weight:300;color:var(--accent);line-height:1}
.result-text{font-size:0.92rem;line-height:1.7;color:var(--text)}

.prices{padding:7rem 3.5rem;background:var(--cream)}
.price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-top:3.5rem}
.price-grid-3{margin-top:1.8rem}
.price-sub{font-family:'Cormorant Garamond',serif;font-size:2rem;font-weight:300;color:var(--charcoal);margin:4rem 0 0}
.price-card{background:var(--white);border:1px solid rgba(184,154,106,0.18);padding:2.5rem 2rem;display:flex;flex-direction:column}
.price-card.highlight{background:var(--charcoal)}
.price-card-cat{font-size:0.6rem;letter-spacing:0.28em;text-transform:uppercase;color:var(--accent);display:block;margin-bottom:0.6rem}
.price-card-name{font-family:'Cormorant Garamond',serif;font-size:1.45rem;font-weight:300;color:var(--charcoal);margin-bottom:1.5rem;line-height:1.2}
.price-card.highlight .price-card-name{color:var(--white)}
.price-divider{width:32px;height:1px;background:rgba(184,154,106,0.4);margin-bottom:1.5rem}
.price-amount{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:300;color:var(--accent);display:block;margin-bottom:0.3rem}
.price-from{font-size:0.7rem;letter-spacing:0.12em;text-transform:uppercase;color:var(--warm-gray);display:block;margin-bottom:1.5rem}
.price-list{list-style:none;display:flex;flex-direction:column;gap:0.55rem;margin-bottom:2rem;flex:1}
.price-list li{font-size:0.9rem;line-height:1.6;color:var(--text);display:flex;gap:0.6rem}
.price-card.highlight .price-list li{color:rgba(255,255,255,0.4)}
.price-list li::before{content:'--';color:var(--accent);flex-shrink:0}
.price-card-note{font-size:0.78rem;line-height:1.7;color:var(--warm-gray);font-style:italic;margin-bottom:1.5rem;padding-left:0.1rem}
.price-card.highlight .price-card-note{color:rgba(255,255,255,0.4)}
.price-unit{font-size:0.9rem;font-style:normal;letter-spacing:0.05em}
.price-btn{display:block;width:100%;padding:0.8rem;background:transparent;border:1px solid rgba(184,154,106,0.35);font-family:'Montserrat',sans-serif;font-size:0.52rem;letter-spacing:0.25em;text-transform:uppercase;color:var(--charcoal);cursor:pointer;transition:all 0.3s;text-align:center;text-decoration:none;margin-top:auto}
.price-btn:hover{background:var(--charcoal);color:var(--white);border-color:var(--charcoal)}
.price-card.highlight .price-btn{border-color:rgba(255,255,255,0.2);color:rgba(255,255,255,0.7)}
.price-card.highlight .price-btn:hover{background:var(--accent);border-color:var(--accent);color:var(--white)}
.price-note{font-size:0.85rem;letter-spacing:0.02em;line-height:1.75;color:var(--warm-gray);margin-top:2rem;text-align:center}

.contact{padding:7rem 3.5rem;background:var(--bone);display:grid;grid-template-columns:1fr 1fr;gap:7rem;align-items:start}
.contact-tagline{font-family:'Cormorant Garamond',serif;font-size:3.2rem;font-weight:300;line-height:1.18;color:var(--charcoal);margin:1rem 0 2rem}
.contact-tagline em{font-style:italic;color:var(--warm-gray)}
.contact-links{display:flex;flex-direction:column;gap:0.85rem;margin-top:2rem}
.contact-links a{font-size:0.9rem;letter-spacing:0.04em;color:var(--warm-gray);text-decoration:none;display:flex;align-items:center;gap:0.75rem;transition:color 0.3s}
.c-label{min-width:80px;font-size:0.6rem;letter-spacing:0.2em;text-transform:uppercase;color:var(--accent)}
.contact-links a::before{content:'';width:20px;height:1px;background:var(--accent);flex-shrink:0}
.contact-links a:hover{color:var(--charcoal)}
/* contact CTA */
.contact-cta{display:flex;flex-direction:column;justify-content:center;height:100%}
.contact-cta-text{font-size:1.02rem;line-height:1.85;color:var(--text);margin-bottom:2.2rem;max-width:420px}
.cta-buttons{display:flex;flex-direction:column;gap:1rem;max-width:420px}
.cta-btn{display:flex;align-items:center;justify-content:center;gap:0.6rem;width:100%;padding:1.2rem 1.5rem;font-family:'Montserrat',sans-serif;font-size:0.78rem;font-weight:400;letter-spacing:0.16em;text-transform:uppercase;text-decoration:none;text-align:center;cursor:pointer;transition:all 0.3s;border:1px solid var(--charcoal)}
.cta-btn-primary{background:var(--charcoal);color:var(--white)}
.cta-btn-primary:hover{background:var(--accent);border-color:var(--accent)}
.cta-btn-secondary{background:transparent;color:var(--charcoal)}
.cta-btn-secondary:hover{background:var(--charcoal);color:var(--white)}
.cta-note{font-size:0.82rem;line-height:1.7;color:var(--warm-gray);margin-top:1.4rem;max-width:420px}
.contact-cta .cta-btn{max-width:420px}
.contact-cta>.cta-btn-primary{margin-bottom:1.4rem}
.callback-form{max-width:420px}
.cb-row{display:grid;grid-template-columns:1fr 1fr;gap:0.9rem;margin-bottom:1.1rem}
.callback-form input{width:100%;padding:0.85rem 0;background:transparent;border:none;border-bottom:1px solid rgba(135,127,116,0.35);font-family:'Montserrat',sans-serif;font-size:0.95rem;color:var(--text);outline:none;transition:border-color 0.3s}
.callback-form input:focus{border-bottom-color:var(--accent)}
.callback-form input::placeholder{color:var(--warm-gray)}
.callback-form .cta-btn{width:100%}
.cb-msg{font-size:0.85rem;line-height:1.6;margin-top:0.9rem}
.cb-msg.ok{color:#5b7a52}.cb-msg.err{color:#a85b4f}

footer{padding:2rem 3.5rem;background:var(--charcoal);display:flex;justify-content:space-between;align-items:center}
.footer-logo{font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:300;letter-spacing:0.18em;color:rgba(255,255,255,0.55);text-decoration:none;text-transform:lowercase}
footer p{font-size:0.66rem;letter-spacing:0.08em;color:rgba(255,255,255,0.35)}
.social{display:flex;gap:1.5rem}
.social a{font-size:0.66rem;letter-spacing:0.14em;text-transform:uppercase;color:rgba(255,255,255,0.45);text-decoration:none;transition:color 0.3s}
.social a:hover{color:var(--accent)}

.fade-up{opacity:0;transform:translateY(24px);transition:opacity 0.9s,transform 0.9s}
.fade-up.visible{opacity:1;transform:translateY(0)}

.to-top{position:fixed;right:1.7rem;bottom:1.7rem;width:46px;height:46px;border-radius:50%;border:none;background:var(--charcoal);color:#fff;font-size:1.15rem;line-height:1;cursor:pointer;opacity:0;visibility:hidden;transform:translateY(8px);transition:opacity 0.3s,visibility 0.3s,transform 0.3s,background 0.3s;z-index:90}
.to-top.show{opacity:1;visibility:visible;transform:translateY(0)}
.to-top:hover{background:var(--accent)}
@media(max-width:600px){.to-top{right:1rem;bottom:1rem;width:42px;height:42px;font-size:1.05rem}}

@media(max-width:1100px){.price-grid{grid-template-columns:repeat(2,1fr)}.process-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:960px){
  nav{padding:1rem 1.5rem}
  .nav-links{display:none;position:fixed;top:0;left:0;right:0;height:100vh;height:100dvh;background:var(--cream);flex-direction:column;align-items:center;justify-content:center;gap:2rem;z-index:99}
  .nav-links.open{display:flex}
  .nav-links a{font-size:1.1rem;letter-spacing:0.14em}
  .burger{display:flex;z-index:101}
  .hero-content{padding:0 1.5rem 4rem;max-width:100%}
  .hero-title{font-size:3rem}
  .gallery,.about,.philosophy,.process,.prices,.contact{padding:4.5rem 1.5rem}
  .section-title{font-size:2.3rem}
  .gallery{padding-top:6rem}
  .shoot-grid{grid-template-columns:repeat(2,1fr)}
  .photo-grid{columns:2}
  .cat-square-label{font-size:2rem}
  .about{flex-direction:column;gap:2.5rem}
  .about-img{flex:none;width:100%;height:380px}
  .phil-grid{grid-template-columns:1fr;gap:2.8rem}
  .phil-media{gap:1rem;max-width:560px}
  .phil-col-offset{margin-top:2.5rem}
  .phil-quote{font-size:1.8rem;margin-top:3rem}
  .process-grid{grid-template-columns:1fr 1fr}
  .result-items{grid-template-columns:repeat(2,1fr)}
  .price-grid{grid-template-columns:1fr 1fr}
  .contact{grid-template-columns:1fr;gap:2.5rem}
  .contact-cta{height:auto}
  .contact-tagline{font-size:2.7rem}
  footer{flex-direction:column;gap:1rem;text-align:center;padding:1.5rem}
}
@media(max-width:600px){
  html{font-size:16px}
  .gallery,.about,.philosophy,.process,.prices,.contact{padding:3.5rem 1.25rem}
  .hero-content{padding:0 1.25rem 3.5rem}
  .hero-title{font-size:2.5rem}
  .hero-sub{font-size:0.95rem;line-height:1.8}
  .section-title{font-size:2rem}
  .gallery-header{flex-direction:column;align-items:flex-start;gap:1rem}
  .cat-squares{grid-template-columns:1fr}
  .cat-square{aspect-ratio:4/3}
  .shoot-grid{grid-template-columns:1fr}
  .photo-grid{columns:1}
  .price-grid{grid-template-columns:1fr}
  .phil-lead{font-size:1.6rem}
  .phil-col-offset{margin-top:1.5rem}
  .phil-quote{font-size:1.55rem}
  .process-grid{grid-template-columns:1fr}
  .process-step{border-right:none;border-bottom:1px solid rgba(184,154,106,0.25);padding:2rem 0}
  .process-step:last-child{border-bottom:none}
  .result-items{grid-template-columns:1fr;gap:1.6rem}
  .contact-tagline{font-size:2.3rem}
  .cta-btn{padding:1.1rem 1.2rem;font-size:0.74rem}
  .cb-row{grid-template-columns:1fr;gap:0}
  .cb-row input{margin-bottom:0.4rem}
  .lb-prev,.lb-next{font-size:2rem;padding:1rem}
  .lb-close{font-size:1.7rem;top:1rem;right:1.2rem}
}
</style>
</head>
<body>

<nav>
  <a class="logo" href="#">ostrohliad</a>
  <ul class="nav-links" id="nav-links">
    <li><a href="#gallery" onclick="closeMenu()">Портфоліо</a></li>
    <li><a href="#philosophy" onclick="closeMenu()">Філософія</a></li>
    <li><a href="#process" onclick="closeMenu()">Процес</a></li>
    <li><a href="#prices" onclick="closeMenu()">Ціни</a></li>
    <li><a href="#contact" onclick="closeMenu()">Контакт</a></li>
  </ul>
  <button class="burger" id="burger" onclick="toggleMenu()"><span></span><span></span><span></span></button>
</nav>

<section class="hero" id="hero">
  <div class="hero-img-main"></div>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <span class="hero-label">Фотограф Катя Острогляд</span>
    <h1 class="hero-title">Фотографія — мій<br>психологічний<br>інструмент по роботі<br>з <em>людьми</em></h1>
    <p class="hero-sub">Моя місія — допомогти вам віднайти впевненість у собі через портретні та індивідуальні фотосесії. Я зупиняю час крізь чуттєві лав сторі та теплі сімейні кадри, а також ловлю справжнє життя у щирих та ефектних репортажах.</p>
    <a class="btn-outline" href="#gallery">Переглянути роботи</a>
  </div>
</section>

<section class="gallery" id="gallery">
  <div class="gallery-header">
    <div>
      <h2 class="section-title">PORTFOLIO</h2>
    </div>
    <a class="link-accent" href="https://www.instagram.com/ostrohliad.k" target="_blank">Instagram &rarr;</a>
  </div>
  <div class="gallery-crumb" id="gallery-crumb"></div>
  <div id="gallery-body"></div>
</section>

<section class="philosophy fade-up" id="philosophy">
  <div class="phil-grid">
    <div class="phil-text">
      <span class="section-label" style="color:var(--accent)">Моя філософія</span>
      <h2 class="section-title">Фотографія — мій<br>психологічний <em>інструмент</em></h2>
      <p class="phil-lead">Мало хто знає, але врятувала мене саме фотографія.</p>
      <p>Колись моя невпевненість у собі сягала нереальних вершин. Я постійно сумнівалася — чи правильно сказала, чи правильно вчинила, як виглядаю збоку. У мене був безкінечний перелік внутрішніх станів, які заважали просто <strong>жити</strong>.</p>
      <p>На зйомках я ніби грала роль кращої версії себе — тієї, якою хочу бути, але не наважуюся. А потім, дозволяючи собі все більше зйомок і образів, я почала переносити це відчуття у своє реальне життя: <strong>красива, варта, впевнена</strong>.</p>
      <p>Після кожної фотосесії, коли я бачила на фото ту Я, якою хочу бути завжди, — зі мною ставалися справжні зміни. Я почала обирати себе там, де раніше підлаштовувалася. Спорт, медитації, турбота про себе прийшли в моє життя завдяки відчуттю, що я — головна героїня власної історії.</p>
    </div>
    <div class="phil-media">
      <div class="phil-col">
        <img src="__PHIL1__" alt="" loading="lazy">
        <img src="__PHIL3__" alt="" loading="lazy">
      </div>
      <div class="phil-col phil-col-offset">
        <img src="__PHIL2__" alt="" loading="lazy">
      </div>
    </div>
  </div>
  <blockquote class="phil-quote">«Я головна героїня власного життя —<br>прямо по центру кадру»</blockquote>
  <div class="phil-mission">
    <p>Саме тому сьогодні моя головна місія на зйомках — дати людині той психологічний ефект, якого вона потребує. Зйомка <strong>швидко й бережно</strong> опрацьовує ваш стан, і ви починаєте бачити це прекрасне в собі. Перевірено на собі.</p>
  </div>
</section>

<section class="process fade-up" id="process">
  <span class="section-label">Як це відбувається</span>
  <h2 class="section-title">Як проходить підготовка<br>і фотосесія</h2>
  <div class="process-grid">
    <div class="process-step"><span class="step-num">01</span><h4 class="step-title">Обираємо стиль фотосесії</h4><ul class="step-list"><li>портретна</li><li>мінімалізм</li><li>сексуальна</li><li>чуттєва</li><li>ефектна</li></ul></div>
    <div class="process-step"><span class="step-num">02</span><h4 class="step-title">Студія або локація</h4><p class="step-body">Допомагаю підібрати й забронювати фотостудію. Оренда студії (від 1200 грн/год) оплачується окремо.</p></div>
    <div class="process-step"><span class="step-num">03</span><h4 class="step-title">Складаємо образ</h4><p class="step-body">Не соромся попросити мене глянути на гардероб — я допоможу зібрати образи. За зйомку встигаємо 2–3 образи.</p></div>
    <div class="process-step"><span class="step-num">04</span><h4 class="step-title">Макіяж і стиль</h4><p class="step-body">Рекомендую перевірених мною візажистів та стилістів — зі знижкою −10%.</p></div>
    <div class="process-step"><span class="step-num">05</span><h4 class="step-title">Організація</h4><p class="step-body">Підбираю референси, за потреби підкажу, де орендувати одяг, на який час призначити макіяж і зачіску та як спланувати логістику.</p></div>
  </div>
  <div class="process-result">
    <span class="section-label">Що ти отримаєш</span>
    <div class="result-items">
      <div class="result-item"><span class="result-num">100+</span><span class="result-text">готових фото в кольоровій корекції та базовій ретуші</span></div>
      <div class="result-item"><span class="result-num">RAW</span><span class="result-text">усі чорнові фото за потреби віддаю</span></div>
      <div class="result-item"><span class="result-num">комфорт</span><span class="result-text">під час фотосесії допомагаю розслабитись та налаштуватись</span></div>
      <div class="result-item"><span class="result-num">30+</span><span class="result-text">позувань в арсеналі — повністю супроводжую на зйомці й показую, як їх повторити</span></div>
    </div>
  </div>
</section>

<section class="prices fade-up" id="prices">
  <span class="section-label">Послуги та вартість</span>
  <h2 class="section-title">Ціни</h2>
  <div class="price-grid">
    <div class="price-card">
      <span class="price-card-cat">01</span>
      <h3 class="price-card-name">Сімейні<br>фото</h3>
      <div class="price-divider"></div>
      <span class="price-amount">$200</span>
      <span class="price-from">Фіксована ціна · незалежно від часу</span>
      <ul class="price-list">
        <li>Фіксована вартість роботи фотографа</li>
        <li>Студія або зйомка на природі</li>
        <li>Рекомендовано орендувати студію від 2 годин</li>
        <li>Передача оброблених фото у JPEG та RAW</li>
      </ul>
      <p class="price-card-note">Окремо оплачується: оренда студії (від 1200 грн/год), мейкап, додаткове обладнання за потреби та одяг для образів. Допомагаю з бронюванням та організацією.</p>
      <a class="price-btn" href="#contact">Замовити</a>
    </div>
    <div class="price-card highlight">
      <span class="price-card-cat">02</span>
      <h3 class="price-card-name" style="color:var(--white)">Індивідуальна<br>зйомка</h3>
      <div class="price-divider"></div>
      <span class="price-amount">$200</span>
      <span class="price-from">Фіксована ціна · незалежно від часу</span>
      <ul class="price-list">
        <li>Фіксована вартість роботи фотографа</li>
        <li>Студія або виїзна зйомка</li>
        <li>Рекомендовано орендувати студію від 2 годин</li>
        <li>Передача оброблених фото у JPEG та RAW</li>
      </ul>
      <p class="price-card-note">Окремо оплачується: оренда студії (від 1200 грн/год), мейкап, додаткове обладнання за потреби та одяг для образів. Допомагаю з бронюванням та організацією.</p>
      <a class="price-btn" href="#contact">Замовити</a>
    </div>
    <div class="price-card">
      <span class="price-card-cat">03</span>
      <h3 class="price-card-name">Репортажні<br>зйомки</h3>
      <div class="price-divider"></div>
      <span class="price-amount">$150<span class="price-unit"> / год</span></span>
      <span class="price-from">Від 4 годин роботи</span>
      <ul class="price-list">
        <li>Погодинна оплата</li>
        <li>Мінімальне замовлення — 4 години</li>
        <li>Корпоративи, концерти, події</li>
        <li>Передача оброблених фото у JPEG та RAW</li>
      </ul>
      <a class="price-btn" href="#contact">Замовити</a>
    </div>
  </div>

  <h3 class="price-sub">Весільні пакети</h3>
  <div class="price-grid price-grid-3">
    <div class="price-card">
      <span class="price-card-cat">Mini Wedding</span>
      <h3 class="price-card-name">Mini</h3>
      <div class="price-divider"></div>
      <span class="price-amount">$400</span>
      <span class="price-from">Зйомка до 3 годин</span>
      <ul class="price-list">
        <li>Понад 150 оброблених фото</li>
        <li>Готовність матеріалу — до 1 місяця</li>
      </ul>
      <a class="price-btn" href="#contact">Замовити</a>
    </div>
    <div class="price-card">
      <span class="price-card-cat">Classic Wedding</span>
      <h3 class="price-card-name">Classic</h3>
      <div class="price-divider"></div>
      <span class="price-amount">$700</span>
      <span class="price-from">Зйомка до 6 годин</span>
      <ul class="price-list">
        <li>Понад 350 оброблених фото</li>
        <li>Готовність матеріалу — до 1 місяця</li>
      </ul>
      <a class="price-btn" href="#contact">Замовити</a>
    </div>
    <div class="price-card highlight">
      <span class="price-card-cat">Premium Wedding Experience</span>
      <h3 class="price-card-name" style="color:var(--white)">Premium</h3>
      <div class="price-divider"></div>
      <span class="price-amount">$800</span>
      <span class="price-from">Зйомка до 10 годин</span>
      <ul class="price-list">
        <li>Понад 1000 оброблених фото</li>
        <li>Готовність матеріалу — до 2 місяців</li>
      </ul>
      <a class="price-btn" href="#contact">Замовити</a>
    </div>
  </div>
  <p class="price-note">Точна вартість визначається індивідуально після обговорення деталей.<br>Зв'яжіться зі мною — обговоримо ваш проєкт.</p>
</section>

<section class="contact fade-up" id="contact">
  <div class="contact-left">
    <span class="section-label">Зв'язатись</span>
    <p class="contact-tagline">Готові створити<br>щось <em>прекрасне</em><br>разом?</p>
    <div class="contact-links">
      <a href="mailto:__EMAIL__"><span class="c-label">Пошта</span>__EMAIL__</a>
      <a href="https://www.instagram.com/ostrohliad.k" target="_blank"><span class="c-label">Instagram</span>ostrohliad.k</a>
      <a href="https://ostrohliad.photo" target="_blank"><span class="c-label">Сайт</span>ostrohliad.photo</a>
    </div>
  </div>
  <div class="contact-right contact-cta">
    <p class="contact-cta-text">Напишіть мені в Instagram Direct — обговоримо вашу ідею. Або залиште номер, і я передзвоню вам сама.</p>
    <a class="cta-btn cta-btn-primary" href="https://ig.me/m/__INSTAGRAM__" target="_blank" rel="noopener">Написати в Direct</a>
    <form class="callback-form" id="callback-form">
      <div class="cb-row">
        <input type="text" name="name" placeholder="Ваше ім'я" autocomplete="name" required>
        <input type="tel" name="phone" placeholder="+380 __ ___ __ __" autocomplete="tel" required>
      </div>
      <button class="cta-btn cta-btn-secondary" type="submit">Замовити дзвінок</button>
      <p class="cb-msg" id="cb-msg"></p>
    </form>
  </div>
</section>

<footer>
  <a class="footer-logo" href="#">ostrohliad</a>
  <p>&copy; 2026 Ostrohliad. Всі права захищені.</p>
  <div class="social">
    <a href="https://www.instagram.com/ostrohliad.k" target="_blank">Instagram</a>
    <a href="mailto:__EMAIL__">Email</a>
  </div>
</footer>

<div class="lightbox" id="lightbox">
  <button class="lb-close" onclick="closeLb()">&#x2715;</button>
  <button class="lb-prev" onclick="prevLb()">&#x2039;</button>
  <img class="lb-img" src="" alt="" id="lb-img">
  <button class="lb-next" onclick="nextLb()">&#x203a;</button>
  <span class="lb-counter" id="lb-counter"></span>
</div>

<button class="to-top" id="to-top" onclick="window.scrollTo({top:0,behavior:'smooth'})" aria-label="Наверх">&#x2191;</button>

<script>
const CATEGORIES = __CATS_JSON__;
const CAT_ORDER = ["individual","family","reportage","wedding"];
const CONTACT_EMAIL = "__EMAIL__";
const INSTAGRAM_USER = "__INSTAGRAM__";
const CALLBACK_API = "__CALLBACK_API__";

const body  = document.getElementById('gallery-body');
const crumb = document.getElementById('gallery-crumb');

let lbPhotos = [], lbIndex = 0;

function catCount(c){ return c.shoots.reduce((n,s)=>n+s.photos.length,0); }

/* — рівень 1: квадрати категорій — */
function showCats(){
  crumb.innerHTML = '';
  body.innerHTML = '<div class="cat-squares">' + CAT_ORDER.map(key=>{
    const c = CATEGORIES[key];
    const cover = c.cover || (c.shoots[0] && c.shoots[0].photos[0]) || '';
    const coverCss = encodeURI(cover).replace(/'/g, '%27');  // апострофи/пробіли в шляху не ламають url()
    return `<div class="cat-square" onclick="showShoots('${key}')" style="background-image:url('${coverCss}')">
      <div class="cat-square-inner">
        <span class="cat-square-label">${c.label}</span>
        <span class="cat-square-count">${c.shoots.length} зйомок · ${catCount(c)} фото</span>
      </div>
    </div>`;
  }).join('') + '</div>';
}

/* — рівень 2: зйомки в категорії — */
function showShoots(key){
  const c = CATEGORIES[key];
  crumb.innerHTML = `<button class="crumb-link" onclick="showCats()">Категорії</button>`
    + `<span class="crumb-sep">/</span><span class="crumb-current">${c.label}</span>`;
  if(!c.shoots.length){ body.innerHTML = '<p class="cat-empty">Зйомки ще не додані</p>'; return; }
  body.innerHTML = '<div class="shoot-grid">' + c.shoots.map((s,i)=>
    `<div class="shoot-card" onclick="showPhotos('${key}',${i})">
      <div class="shoot-card-imgwrap"><img class="shoot-card-img" src="${s.photos[0]}" alt="" loading="lazy"></div>
      <span class="shoot-card-title">${s.title}</span>
      <span class="shoot-card-meta">${s.date ? s.date+' · ' : ''}${s.photos.length} фото</span>
    </div>`
  ).join('') + '</div>';
}

/* — рівень 3: фото зйомки — */
function showPhotos(key, idx){
  const c = CATEGORIES[key], s = c.shoots[idx];
  crumb.innerHTML = `<button class="crumb-link" onclick="showCats()">Категорії</button>`
    + `<span class="crumb-sep">/</span><button class="crumb-link" onclick="showShoots('${key}')">${c.label}</button>`
    + `<span class="crumb-sep">/</span><span class="crumb-current">${s.title}</span>`;
  lbPhotos = s.photos;
  body.innerHTML = '<div class="photo-grid">' + s.photos.map((p,i)=>
    `<div class="photo-item" onclick="openLb(${i})"><img src="${p}" alt="" loading="lazy"></div>`
  ).join('') + '</div>';
  document.getElementById('gallery').scrollIntoView({behavior:'smooth'});
}

/* — лайтбокс — */
function openLb(i){ lbIndex = i; showLb(); }
function showLb(){
  document.getElementById('lb-img').src = lbPhotos[lbIndex];
  document.getElementById('lb-counter').textContent = (lbIndex+1)+' / '+lbPhotos.length;
  document.getElementById('lightbox').classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeLb(){
  document.getElementById('lightbox').classList.remove('open');
  document.body.style.overflow = '';
}
function prevLb(){ lbIndex = (lbIndex-1+lbPhotos.length)%lbPhotos.length; showLb(); }
function nextLb(){ lbIndex = (lbIndex+1)%lbPhotos.length; showLb(); }
document.getElementById('lightbox').addEventListener('click', e=>{ if(e.target===e.currentTarget) closeLb(); });
document.addEventListener('keydown', e=>{
  if(!document.getElementById('lightbox').classList.contains('open')) return;
  if(e.key==='Escape') closeLb();
  if(e.key==='ArrowLeft') prevLb();
  if(e.key==='ArrowRight') nextLb();
});

/* — меню — */
function toggleMenu(){ document.getElementById('nav-links').classList.toggle('open'); }
function closeMenu(){ document.getElementById('nav-links').classList.remove('open'); }

/* — форма зворотного дзвінка — */
const cbForm = document.getElementById('callback-form');
if(cbForm){
  cbForm.addEventListener('submit', async e=>{
    e.preventDefault();
    const msg = document.getElementById('cb-msg');
    const btn = cbForm.querySelector('button');
    const fd = new FormData(cbForm);
    const name = (fd.get('name')||'').toString().trim();
    const phone = (fd.get('phone')||'').toString().trim();
    if(!name || !phone){ return; }
    msg.className='cb-msg';

    // 1) Якщо підключено бекенд (Telegram) — надсилаємо туди
    if(CALLBACK_API){
      btn.disabled=true; const o=btn.textContent; btn.textContent='Надсилаємо…';
      try{
        const r = await fetch(CALLBACK_API,{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({name, phone})});
        if(!r.ok) throw new Error('bad');
        cbForm.innerHTML = '<p class="cb-msg ok">Дякую! Я зателефоную вам найближчим часом.</p>';
      }catch(err){
        btn.disabled=false; btn.textContent=o;
        msg.className='cb-msg err';
        msg.innerHTML='Не вдалося надіслати. Напишіть, будь ласка, в <a href="https://ig.me/m/'+INSTAGRAM_USER+'" target="_blank" rel="noopener">Direct</a>.';
      }
      return;
    }

    // 2) Запасний варіант: копіюємо дані та відкриваємо Direct
    const text = 'Передзвоніть мені, будь ласка. Ім\'я: '+name+'. Телефон: '+phone+'.';
    try{ await navigator.clipboard.writeText(text); }catch(err){}
    window.open('https://ig.me/m/'+INSTAGRAM_USER,'_blank','noopener');
    msg.className='cb-msg ok';
    msg.innerHTML='Відкрили Instagram Direct — дані вже скопійовано, просто вставте їх і надішліть.';
  });
}

/* — анімації — */
const obs = new IntersectionObserver(e=>e.forEach(x=>{ if(x.isIntersecting) x.target.classList.add('visible'); }), {threshold:0.08});
document.querySelectorAll('.fade-up').forEach(el=>obs.observe(el));

/* — кнопка «наверх» — */
const toTop = document.getElementById('to-top');
window.addEventListener('scroll', ()=>{ toTop.classList.toggle('show', window.scrollY > 600); }, {passive:true});

/* старт */
showCats();
</script>
</body>
</html>"""


BOOKING_TEMPLATE = r"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Бронювання — Ostrohliad</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Montserrat:wght@300;400&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--cream:#f8f5f0;--bone:#eae4d9;--charcoal:#141414;--warm-gray:#6b6358;--accent:#a9824f;--white:#fff;--text:#3d362d}
html{font-size:17px;scroll-behavior:smooth}
body{font-family:'Montserrat',sans-serif;background:var(--cream);color:var(--text);font-weight:400;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit}
nav{position:fixed;top:0;left:0;right:0;z-index:50;display:flex;justify-content:space-between;align-items:center;padding:1.3rem 2rem;background:rgba(248,245,240,0.94);backdrop-filter:blur(10px);border-bottom:1px solid rgba(169,130,79,0.14)}
.logo{font-family:'Cormorant Garamond',serif;font-size:1.4rem;letter-spacing:0.18em;text-decoration:none;text-transform:lowercase}
.back{font-size:0.72rem;letter-spacing:0.16em;text-transform:uppercase;color:var(--warm-gray);text-decoration:none}
.back:hover{color:var(--charcoal)}
.book-wrap{max-width:1080px;margin:0 auto;padding:7rem 2rem 5rem}
.book-head{text-align:center;margin-bottom:3rem}
.book-head .label{font-size:0.7rem;letter-spacing:0.26em;text-transform:uppercase;color:var(--accent);display:block;margin-bottom:0.7rem}
.book-head h1{font-family:'Cormorant Garamond',serif;font-size:3rem;font-weight:300;line-height:1.1}
.book-head p{color:var(--warm-gray);margin-top:0.9rem;font-size:0.96rem}
.book-grid{display:grid;grid-template-columns:1.2fr 0.8fr;gap:3rem;align-items:start}
.cal{background:var(--white);border:1px solid rgba(169,130,79,0.2);padding:1.8rem}
.cal-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.3rem}
.cal-nav{background:none;border:1px solid rgba(169,130,79,0.3);width:38px;height:38px;font-size:1.3rem;line-height:1;cursor:pointer;color:var(--accent);transition:all 0.2s}
.cal-nav:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.cal-nav:disabled{opacity:0.3;cursor:default;background:none;color:var(--accent)}
.cal-title{font-family:'Cormorant Garamond',serif;font-size:1.5rem}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
.cal-dow{text-align:center;font-size:0.66rem;letter-spacing:0.08em;text-transform:uppercase;color:var(--warm-gray);padding-bottom:0.4rem}
.cal-day{aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;font-size:0.95rem;border:1px solid transparent;cursor:pointer;transition:all 0.2s}
.cal-day:hover:not(.disabled):not(.empty){border-color:var(--accent)}
.cal-day.disabled{color:rgba(61,54,45,0.22);cursor:default}
.cal-day.empty{cursor:default}
.cal-day.selected{background:var(--charcoal);color:#fff}
.slots{margin-top:2rem}
.slots h3{font-size:0.72rem;letter-spacing:0.18em;text-transform:uppercase;color:var(--warm-gray);margin-bottom:1rem}
.slot-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(82px,1fr));gap:8px}
.slot{padding:0.75rem 0;text-align:center;border:1px solid rgba(169,130,79,0.3);background:transparent;font-family:inherit;font-size:0.92rem;color:var(--text);cursor:pointer;transition:all 0.2s}
.slot:hover{border-color:var(--accent)}
.slot.selected{background:var(--charcoal);color:#fff;border-color:var(--charcoal)}
.summary{background:var(--charcoal);color:#fff;padding:2.2rem;position:sticky;top:6rem}
.summary h2{font-family:'Cormorant Garamond',serif;font-weight:300;font-size:1.7rem;margin-bottom:1.5rem}
.sum-row{display:flex;justify-content:space-between;gap:1rem;padding:0.75rem 0;border-bottom:1px solid rgba(255,255,255,0.1);font-size:0.94rem}
.sum-row span:first-child{color:rgba(255,255,255,0.5)}
.sum-total{display:flex;justify-content:space-between;align-items:baseline;margin:1.5rem 0 0.3rem}
.sum-total .lbl{font-size:0.7rem;letter-spacing:0.2em;text-transform:uppercase;color:rgba(255,255,255,0.5)}
.sum-total .amt{font-family:'Cormorant Garamond',serif;font-size:2.1rem;color:var(--accent)}
.pay-btn{display:block;width:100%;margin-top:1.6rem;padding:1.15rem;background:var(--accent);color:#fff;border:none;font-family:inherit;font-size:0.78rem;font-weight:400;letter-spacing:0.16em;text-transform:uppercase;cursor:pointer;transition:opacity 0.3s}
.pay-btn:hover:not(:disabled){opacity:0.88}
.pay-btn:disabled{opacity:0.35;cursor:default}
.pay-note{font-size:0.8rem;color:rgba(255,255,255,0.45);line-height:1.65;margin-top:1.1rem}
.pay-msg{font-size:0.88rem;line-height:1.65;margin-top:1.1rem}
.pay-msg a{color:var(--accent)}
@media(max-width:860px){.book-grid{grid-template-columns:1fr;gap:2rem}.summary{position:static}}
@media(max-width:600px){.book-wrap{padding:6rem 1.1rem 3rem}.book-head h1{font-size:2.3rem}.cal{padding:1.2rem}.cal-grid{gap:4px}.slot-grid{grid-template-columns:repeat(auto-fill,minmax(72px,1fr))}}
</style>
</head>
<body>
<nav>
  <a class="logo" href="index.html">ostrohliad</a>
  <a class="back" href="index.html">&larr; На головну</a>
</nav>

<div class="book-wrap">
  <div class="book-head">
    <span class="label">Бронювання</span>
    <h1>Оберіть дату та час</h1>
    <p>Передоплата __DEPOSIT__ грн підтверджує бронювання і зараховується у вартість зйомки.</p>
  </div>
  <div class="book-grid">
    <div>
      <div class="cal">
        <div class="cal-top">
          <button class="cal-nav" id="prev" aria-label="Попередній місяць">&#x2039;</button>
          <span class="cal-title" id="cal-title"></span>
          <button class="cal-nav" id="next" aria-label="Наступний місяць">&#x203a;</button>
        </div>
        <div class="cal-grid" id="cal-dows"></div>
        <div class="cal-grid" id="cal-days" style="margin-top:6px"></div>
      </div>
      <div class="slots" id="slots" style="display:none">
        <h3>Доступний час</h3>
        <div class="slot-grid" id="slot-grid"></div>
      </div>
    </div>
    <div class="summary">
      <h2>Ваше бронювання</h2>
      <div class="sum-row"><span>Дата</span><span id="sum-date">—</span></div>
      <div class="sum-row"><span>Час</span><span id="sum-time">—</span></div>
      <div class="sum-total"><span class="lbl">Передоплата</span><span class="amt">__DEPOSIT__ грн</span></div>
      <button class="pay-btn" id="pay" disabled>Сплатити та забронювати</button>
      <p class="pay-note">Оберіть дату й час, щоб продовжити. Решта вартості зйомки сплачується після узгодження деталей.</p>
      <p class="pay-msg" id="pay-msg"></p>
    </div>
  </div>
</div>

<script>
const DEPOSIT=__DEPOSIT__;
const BOOKING_API="__BOOKING_API__";
const PAYMENT_LINK="__PAYMENT_LINK__";
const INSTAGRAM_USER="__INSTAGRAM__";
const HOUR_START=__HOUR_START__, HOUR_END=__HOUR_END__, STEP=__STEP__;

// повернення після оплати Monobank (redirectUrl ...?paid=1)
if(new URLSearchParams(location.search).get('paid')==='1'){
  const m=document.getElementById('pay-msg');
  m.style.color='#cdbfa6';
  m.innerHTML='Дякуємо! Оплату отримано. Я зв\'яжуся з вами найближчим часом для підтвердження деталей зйомки.';
}
const MONTHS=["Січень","Лютий","Березень","Квітень","Травень","Червень","Липень","Серпень","Вересень","Жовтень","Листопад","Грудень"];
const DOWS=["Пн","Вт","Ср","Чт","Пт","Сб","Нд"];
const today=new Date(); today.setHours(0,0,0,0);
let view=new Date(today.getFullYear(),today.getMonth(),1);
let selDate=null, selTime=null;

document.getElementById('cal-dows').innerHTML=DOWS.map(d=>'<div class="cal-dow">'+d+'</div>').join('');

function sameDay(a,b){return a&&b&&a.getTime()===b.getTime();}
function fmtDate(d){return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')+'.'+d.getFullYear();}

function renderCal(){
  const y=view.getFullYear(), m=view.getMonth();
  document.getElementById('cal-title').textContent=MONTHS[m]+' '+y;
  const startDow=(new Date(y,m,1).getDay()+6)%7;
  const days=new Date(y,m+1,0).getDate();
  let html='';
  for(let i=0;i<startDow;i++) html+='<div class="cal-day empty"></div>';
  for(let d=1;d<=days;d++){
    const date=new Date(y,m,d);
    const past=date<today;
    const sel=sameDay(date,selDate);
    html+='<div class="cal-day'+(past?' disabled':'')+(sel?' selected':'')+'" data-d="'+d+'">'+d+'</div>';
  }
  document.getElementById('cal-days').innerHTML=html;
  document.querySelectorAll('#cal-days .cal-day:not(.disabled):not(.empty)').forEach(el=>{
    el.onclick=()=>{selDate=new Date(y,m,+el.dataset.d);selTime=null;renderCal();renderSlots();updateSummary();};
  });
  const curStart=new Date(today.getFullYear(),today.getMonth(),1);
  document.getElementById('prev').disabled=(new Date(y,m,1)<=curStart);
}
function renderSlots(){
  const wrap=document.getElementById('slots');
  if(!selDate){wrap.style.display='none';return;}
  wrap.style.display='block';
  const now=new Date();
  const isToday=sameDay(selDate,today);
  let html='';
  for(let mins=HOUR_START*60; mins<HOUR_END*60; mins+=STEP){
    const hh=Math.floor(mins/60), mm=mins%60;
    const t=String(hh).padStart(2,'0')+':'+String(mm).padStart(2,'0');
    const passed=isToday && (hh<now.getHours() || (hh===now.getHours() && mm<=now.getMinutes()));
    if(passed) continue;
    html+='<button class="slot'+(selTime===t?' selected':'')+'" data-t="'+t+'">'+t+'</button>';
  }
  document.getElementById('slot-grid').innerHTML=html || '<p style="color:var(--warm-gray);font-size:0.9rem">На цей день вільних слотів немає — оберіть інший день.</p>';
  document.querySelectorAll('.slot').forEach(b=>b.onclick=()=>{selTime=b.dataset.t;renderSlots();updateSummary();});
}
function updateSummary(){
  document.getElementById('sum-date').textContent=selDate?fmtDate(selDate):'—';
  document.getElementById('sum-time').textContent=selTime||'—';
  document.getElementById('pay').disabled=!(selDate&&selTime);
}
document.getElementById('prev').onclick=()=>{view=new Date(view.getFullYear(),view.getMonth()-1,1);renderCal();};
document.getElementById('next').onclick=()=>{view=new Date(view.getFullYear(),view.getMonth()+1,1);renderCal();};
document.getElementById('pay').onclick=async()=>{
  if(!(selDate&&selTime)) return;
  const btn=document.getElementById('pay'), msg=document.getElementById('pay-msg');
  const details='Бронювання зйомки: '+fmtDate(selDate)+' о '+selTime+'. Передоплата '+DEPOSIT+' грн.';
  msg.style.color='#cdbfa6';

  // 1) Monobank Acquiring через бекенд: створюємо інвойс і йдемо на сторінку оплати
  if(BOOKING_API){
    btn.disabled=true; const orig=btn.textContent; btn.textContent='Створюємо оплату…';
    try{
      const r=await fetch(BOOKING_API,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({date:fmtDate(selDate),time:selTime,amount:DEPOSIT})});
      const d=await r.json();
      if(r.ok && d.pageUrl){ window.location.href=d.pageUrl; return; }
      throw new Error(d.error||'no pageUrl');
    }catch(e){
      btn.disabled=false; btn.textContent=orig;
      msg.style.color='#e0a89a';
      msg.innerHTML='Не вдалося створити оплату автоматично. Напишіть, будь ласка, в <a href="https://ig.me/m/'+INSTAGRAM_USER+'" target="_blank" rel="noopener">Direct</a> — підтвердимо бронювання вручну.';
    }
    return;
  }

  // 2) Запасний варіант: статичне платіжне посилання
  try{await navigator.clipboard.writeText(details);}catch(e){}
  if(PAYMENT_LINK){
    window.open(PAYMENT_LINK,'_blank','noopener');
    msg.innerHTML='Відкрили сторінку оплати передоплати ('+DEPOSIT+' грн). Деталі бронювання скопійовано — після оплати напишіть мені в <a href="https://ig.me/m/'+INSTAGRAM_USER+'" target="_blank" rel="noopener">Direct</a> для підтвердження.';
  }else{
    // 3) Без оплати: підтвердження через Direct
    window.open('https://ig.me/m/'+INSTAGRAM_USER,'_blank','noopener');
    msg.innerHTML='Деталі бронювання скопійовано. Відкрили Instagram Direct — надішліть повідомлення, і я підтверджу дату та надішлю реквізити для передоплати ('+DEPOSIT+' грн).';
  }
};
renderCal();
</script>
</body>
</html>"""


def pick_cover(data, key, fallback):
    """Повнорозмірне (WebP) фото першої зйомки категорії — для розділу «Філософія»."""
    for shoot in data.get(key, {}).get("shoots", []):
        if shoot["photos"]:
            return shoot["photos"][0]
    return fallback


def main():
    print("Scanning categories...\n")
    data, total = build_data()
    cats_js = json.dumps(data, ensure_ascii=False)

    # Оптимізуємо головне фото та фото «Про мене» (повнорозмірні WebP)
    hero_full = optimize(HERO_IMAGE) if os.path.exists(HERO_IMAGE) else HERO_IMAGE
    about_full = optimize(ABOUT_IMAGE) if os.path.exists(ABOUT_IMAGE) else ABOUT_IMAGE

    # Фото для розділу «Філософія» (з папки Philosophy), із запасним варіантом
    def opt_or(path, fallback):
        return optimize(path) if path and os.path.exists(path) else fallback
    phil1 = opt_or(PHIL_PHOTOS[0] if len(PHIL_PHOTOS) > 0 else "", about_full)
    phil2 = opt_or(PHIL_PHOTOS[1] if len(PHIL_PHOTOS) > 1 else "", hero_full)
    phil3 = opt_or(PHIL_PHOTOS[2] if len(PHIL_PHOTOS) > 2 else "", about_full)

    # OG-зображення для прев'ю при поширенні (JPG 1200x630 — підтримується всюди)
    try:
        from PIL import Image, ImageOps
        if os.path.exists(HERO_IMAGE):
            im = ImageOps.exif_transpose(Image.open(HERO_IMAGE)).convert("RGB")
            ImageOps.fit(im, (1200, 630), Image.LANCZOS).save("og-image.jpg", "JPEG", quality=85)
    except Exception as e:
        print("  [!] OG-зображення:", e)
    og_image = SITE_URL.rstrip("/") + "/og-image.jpg"   # абсолютний URL прев'ю

    html = (TEMPLATE
            .replace("__CATS_JSON__", cats_js)
            .replace("__HERO__", hero_full)
            .replace("__ABOUT__", about_full)
            .replace("__PHIL1__", phil1)
            .replace("__PHIL2__", phil2)
            .replace("__PHIL3__", phil3)
            .replace("__CALLBACK_API__", CALLBACK_API_URL)
            .replace("__SITEURL__", SITE_URL.rstrip("/"))
            .replace("__OGIMAGE__", og_image)
            .replace("__EMAIL__", CONTACT_EMAIL)
            .replace("__INSTAGRAM__", INSTAGRAM_USER))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nDone: {OUTPUT_FILE}  ({total} photos total)")

    # сторінка бронювання/оплати більше не генерується (видалено за бажанням)

    print(f"\nWebP: створено {_opt_stats['made']}, пропущено (вже є) {_opt_stats['skipped']}, "
          f"помилок {_opt_stats['failed']}  ->  папка '{WEB_BASE}/'")


if __name__ == "__main__":
    main()
