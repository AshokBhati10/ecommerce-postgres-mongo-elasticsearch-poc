"""Reproducible seed: Postgres users/orders/items (~50k orders), MongoDB catalog
(100,000 products with images, + inactive products + the Wireless Mouse ->
Wireless Mouse Pro rename fixture), a fully caught-up Elasticsearch orders
index, and the Elasticsearch products index (search layer for the Storefront).

Run from backend/:  python -m scripts.seed
"""
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from app.core import database as db
from app.core.settings import settings
from app.repositories import es as es_repo
from app.repositories import mongo as mongo_repo
from app.repositories import postgres as pg_repo
from app.services import sync as sync_service

NOW = datetime.now(timezone.utc)

# Product-relevant catalog images.
#
# Curated, stable CDN photo URLs (Unsplash / Pexels), each verified
# 2026-09-28 to return HTTP 200 with an image content type and visually
# confirmed to depict the product type it is assigned to. URLs are fixed
# strings (no randomness), so reseeding always produces the same catalog.
# No binary image data is stored in the repo or in MongoDB.
def _u(photo_id):
    return f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w=600&q=80"


_PRODUCT_IMAGES = {
    "mouse": _u("1625750188088-f6cd6756349c"),        # wireless gaming mouse
    "keyboard": _u("1656711081969-9d16ebc2d210"),     # mechanical keyboard
    "monitor": _u("1547658718-1cdaa0852790"),         # desktop monitor
    "hub": _u("1616578273461-3a99ce422de6"),          # USB-C hub with accessories
    "monitorarm": _u("1614598389565-8d56eddd2f48"),   # monitor on adjustable arm
    "laptopstand": _u("1663873148245-df991e1717ea"),  # aluminum laptop stand
    "desksetup": _u("1591222380707-dcde425cc8ac"),    # tidy desk: monitor+keyboard+mouse
    "earbuds": _u("1590658268037-6bf12165a8df"),      # wireless earbuds
    "headphones": _u("1505740420928-5e560c06d30e"),   # over-ear headphones
    "speaker": _u("1608043152269-423dbba4e7e1"),      # bluetooth speaker
    "microphone": _u("1478737270239-2f02b77fc618"),   # studio microphone
    "mixer": _u("1470225620780-dba8ba36b745"),        # audio mixer
    "turntable": _u("1531469543542-5f61e38b875b"),    # turntable
    "cable": ("https://images.pexels.com/photos/3921633/"
              "pexels-photo-3921633.jpeg?auto=compress&cs=tinysrgb&w=600"),  # braided USB-C cable
    "charger": _u("1591290619618-904f6dd935e3"),      # wireless charging pad
    "desklamp": _u("1507473885765-e6ed057f782c"),     # desk lamp
    "deskorganizer": ("https://images.pexels.com/photos/8581047/"
                      "pexels-photo-8581047.jpeg?auto=compress&cs=tinysrgb&w=600"),  # desk organizer
    "office": _u("1588357767511-c6b3010409a3"),       # home office desk
    "crt": _u("1628329336337-8c33a8f08ec1"),          # CRT monitor
}

# (title keyword, image key) in priority order — specific phrases first.
# Products without a dedicated photo fall back to the closest product type
# (e.g. power strip -> cable, soundbar -> speaker, webcam -> monitor).
_IMAGE_KEYWORDS = [
    ("crt", "crt"),
    ("studio monitor", "speaker"),
    ("monitor arm", "monitorarm"),
    ("monitor light", "desklamp"),
    ("cable organizer", "cable"),
    ("cable tray", "cable"),
    ("cable management", "cable"),
    ("desk organizer", "deskorganizer"),
    ("file tray", "deskorganizer"),
    ("pen holder", "deskorganizer"),
    ("bookend", "deskorganizer"),
    ("desk drawer", "deskorganizer"),
    ("docking station", "hub"),
    ("kvm switch", "hub"),
    ("usb hub", "hub"),
    ("headset stand", "headphones"),
    ("power strip", "cable"),
    ("extension cord", "cable"),
    ("power adapter", "charger"),
    ("gan charger", "charger"),
    ("wireless charger", "charger"),
    ("desk lamp", "desklamp"),
    ("whiteboard", "office"),
    ("wireless presenter", "office"),
    ("graphics tablet", "desksetup"),
    ("laptop stand", "laptopstand"),
    ("laptop riser", "laptopstand"),
    ("monitor riser", "laptopstand"),
    ("privacy filter", "monitor"),
    ("privacy screen", "monitor"),
    ("desk mat", "desksetup"),
    ("chair mat", "office"),
    ("wrist rest", "desksetup"),
    ("karaoke mic", "microphone"),
    ("microphone arm", "microphone"),
    ("audio interface", "mixer"),
    ("sound mixer", "mixer"),
    ("webcam", "monitor"),
    ("headphone", "headphones"),
    ("earbud", "earbuds"),
    ("earphone", "earbuds"),
    ("soundbar", "speaker"),
    ("speaker", "speaker"),
    ("radio", "speaker"),
    ("turntable", "turntable"),
    ("mixer", "mixer"),
    ("microphone", "microphone"),
    ("keyboard", "keyboard"),
    ("trackpad", "keyboard"),
    ("mouse", "mouse"),
    ("monitor", "monitor"),
    ("tablet", "desksetup"),
    ("charger", "charger"),
    ("adapter", "cable"),
    ("ethernet", "cable"),
    ("hdmi", "cable"),
    ("cable", "cable"),
    ("lamp", "desklamp"),
    ("organizer", "deskorganizer"),
    ("clock", "office"),
    ("shelf", "office"),
    ("footrest", "office"),
    ("cushion", "office"),
    ("hub", "hub"),
]

_CATEGORY_FALLBACK_IMAGE = {
    "peripherals": "desksetup",
    "audio": "headphones",
    "cables": "cable",
    "office": "office",
}


def _image_url_for(title, category):
    """Deterministic product-relevant image URL for a catalog title."""
    text = title.lower()
    for keyword, key in _IMAGE_KEYWORDS:
        if keyword in text:
            return _PRODUCT_IMAGES[key]
    return _PRODUCT_IMAGES[_CATEGORY_FALLBACK_IMAGE.get(category, "desksetup")]


# The POC's two designated admin accounts (user ids from USERS above).
# No role information existed in the original dataset; these are set as
# admins so the frontend can demonstrate role-based navigation.
ADMIN_USER_IDS = (2, 4)  # Jane Smith, Alex Rivera

USERS = [
    (1, "John Doe", "john.doe@example.com"),
    (2, "Jane Smith", "jane.smith@example.com"),
    (3, "Wendy Wireless", "wendy.wireless@example.com"),
    (4, "Alex Rivera", "alex.rivera@example.com"),
    (5, "Sam Patel", "sam.patel@example.com"),
    (6, "Casey Nguyen", "casey.nguyen@example.com"),
    (7, "Morgan Lee", "morgan.lee@example.com"),
    (8, "Riley Brooks", "riley.brooks@example.com"),
]

# sku, title, description, price, category, tags, attributes, variants
CATALOG = [
    ("WM-001", "Wireless Mouse", "Ergonomic 2.4GHz mouse", 50.16, "peripherals",
     ["wireless", "usb", "office"], {"color": "black", "dpi": 1600, "battery": "AA"},
     [{"sku": "WM-001-BLK", "color": "black", "stock": 40},
      {"sku": "WM-001-WHT", "color": "white", "stock": 12}]),
    ("MK-201", "Mechanical Keyboard", "Hot-swappable RGB keyboard", 100.34, "peripherals",
     ["keyboard", "rgb", "office"], {"switch": "tactile", "layout": "TKL"},
     [{"sku": "MK-201-BRN", "switch": "brown", "stock": 25},
      {"sku": "MK-201-RED", "switch": "red", "stock": 18}]),
    ("AU-310", "Wireless Earbuds", "True wireless earbuds with charging case", 79.99, "audio",
     ["wireless", "bluetooth", "earbuds"], {"battery_hours": 6, "anc": False},
     [{"sku": "AU-310-WHT", "color": "white", "stock": 60}]),
    ("CB-410", "USB-C Hub 7-in-1", "7-port USB-C hub with 4K HDMI", 45.00, "cables",
     ["usb-c", "hub", "laptop"], {"ports": "3xUSB-A, HDMI, SD, USB-C PD"},
     [{"sku": "CB-410-GRY", "color": "gray", "stock": 33}]),
    ("OF-510", "Desk Lamp LED", "Dimmable LED desk lamp", 32.50, "office",
     ["lamp", "led", "desk"], {"color_temp": "3000-6000K", "dimmable": True},
     [{"sku": "OF-510-BLK", "color": "black", "stock": 22},
      {"sku": "OF-510-WHT", "color": "white", "stock": 19}]),
    ("AU-320", "Noise Cancelling Headphones", "Over-ear ANC headphones", 199.00, "audio",
     ["wireless", "bluetooth", "anc", "premium"], {"battery_hours": 30, "anc": True},
     [{"sku": "AU-320-BLK", "color": "black", "stock": 15}]),
    ("WK-202", "Wireless Keyboard", "Slim wireless keyboard", 89.99, "peripherals",
     ["wireless", "keyboard", "office"], {"layout": "full", "battery": "2xAAA"},
     [{"sku": "WK-202-BLK", "color": "black", "stock": 28}]),
    ("GM-101", "Gaming Mouse", "High-DPI gaming mouse", 65.00, "peripherals",
     ["gaming", "rgb", "usb"], {"dpi": 12000, "color": "black"},
     [{"sku": "GM-101-BLK", "color": "black", "stock": 35}]),
    ("MP-102", "Mouse Pad XL", "Extended desk mouse pad", 19.99, "peripherals",
     ["mousepad", "desk"], {"size": "900x400mm", "color": "black"},
     [{"sku": "MP-102-BLK", "color": "black", "stock": 80}]),
    ("LS-103", "Laptop Stand", "Adjustable aluminum laptop stand", 39.95, "peripherals",
     ["laptop", "ergonomic", "aluminum"], {"material": "aluminum", "adjustable": True},
     [{"sku": "LS-103-SLV", "color": "silver", "stock": 26}]),
    ("WC-104", "Webcam 4K Pro", "4K webcam with dual mics", 119.99, "peripherals",
     ["webcam", "4k", "video"], {"resolution": "4K", "mic": "dual"},
     [{"sku": "WC-104-BLK", "color": "black", "stock": 20}]),
    ("AU-330", "Bluetooth Speaker", "Portable waterproof speaker", 49.99, "audio",
     ["wireless", "bluetooth", "speaker"], {"battery_hours": 12, "waterproof": "IPX5"},
     [{"sku": "AU-330-BLK", "color": "black", "stock": 44},
      {"sku": "AU-330-BLU", "color": "blue", "stock": 31}]),
    ("AU-340", "Wired Earphones", "Budget wired earphones", 14.99, "audio",
     ["earphones", "wired", "budget"], {"connector": "3.5mm", "mic": True},
     [{"sku": "AU-340-WHT", "color": "white", "stock": 90}]),
    ("AU-350", "USB Microphone", "Cardioid USB microphone", 89.00, "audio",
     ["microphone", "usb", "podcast"], {"pattern": "cardioid", "mount": "desk"},
     [{"sku": "AU-350-BLK", "color": "black", "stock": 17}]),
    ("AU-360", "Soundbar", "2.1 channel TV soundbar", 149.99, "audio",
     ["soundbar", "tv", "premium"], {"channels": "2.1", "bluetooth": True},
     [{"sku": "AU-360-BLK", "color": "black", "stock": 15}]),
    ("CB-411", "HDMI Cable 2m", "High-speed HDMI 2.0 cable", 12.99, "cables",
     ["hdmi", "cable", "video"], {"length": "2m", "version": "2.0"},
     [{"sku": "CB-411-BLK", "color": "black", "stock": 120}]),
    ("CB-412", "USB-C Cable 1m", "60W fast-charge USB-C cable", 9.99, "cables",
     ["usb-c", "cable", "charging"], {"length": "1m", "power": "60W"},
     [{"sku": "CB-412-WHT", "color": "white", "stock": 150},
      {"sku": "CB-412-BLK", "color": "black", "stock": 140}]),
    ("CB-413", "Wireless Charger Pad", "15W Qi wireless charger", 29.99, "cables",
     ["wireless", "charger", "qi"], {"power": "15W", "standard": "Qi"},
     [{"sku": "CB-413-BLK", "color": "black", "stock": 55}]),
    ("CB-414", "Ethernet Cable 5m", "Cat6 ethernet cable", 15.49, "cables",
     ["ethernet", "cable", "network"], {"length": "5m", "category": "Cat6"},
     [{"sku": "CB-414-YLW", "color": "yellow", "stock": 70}]),
    ("CB-415", "DisplayPort Cable", "DisplayPort 1.4 cable", 18.99, "cables",
     ["displayport", "cable", "video"], {"length": "1.8m", "version": "1.4"},
     [{"sku": "CB-415-BLK", "color": "black", "stock": 65}]),
    ("OF-511", "Wireless Presenter", "Presentation clicker with laser", 24.99, "office",
     ["wireless", "presenter", "office"], {"range": "30m", "laser": "red"},
     [{"sku": "OF-511-BLK", "color": "black", "stock": 38}]),
    ("OF-512", "Monitor Light Bar", "USB monitor light bar", 44.99, "office",
     ["monitor", "light", "desk"], {"color_temp": "2900-6000K", "usb_powered": True},
     [{"sku": "OF-512-BLK", "color": "black", "stock": 24}]),
    ("OF-513", "Desk Organizer", "Bamboo desk organizer", 22.99, "office",
     ["organizer", "desk", "office"], {"material": "bamboo", "compartments": 6},
     [{"sku": "OF-513-NAT", "color": "natural", "stock": 41}]),
    ("OF-514", "Ergonomic Footrest", "Memory-foam footrest", 34.99, "office",
     ["ergonomic", "footrest", "office"], {"material": "memory foam", "adjustable": True},
     [{"sku": "OF-514-GRY", "color": "gray", "stock": 29}]),
    ("OF-515", "Cable Management Kit", "20-piece cable organizer kit", 16.99, "cables",
     ["cable", "organizer", "desk"], {"pieces": 20, "color": "black"},
     [{"sku": "OF-515-BLK", "color": "black", "stock": 75}]),
]

INACTIVE_PRODUCT = (
    "CR-900", "Old CRT Monitor", "Discontinued CRT display", 199.99, "peripherals",
    ["monitor", "vintage"], {"size": '17"', "connector": "VGA"},
    [{"sku": "CR-900-BGE", "color": "beige", "stock": 0}],
)

# ---------- Generated large catalog ----------
# Deterministic generator that grows the hand-written CATALOG above to a
# genuinely large catalog (100,000 products) across the same four categories.
# Uses its own Random instance so order seeding (random.seed(42)) is untouched.
CATALOG_TARGET_TOTAL = 100000

_GEN_BRANDS = ["NorthPeak", "VoltEdge", "ClearLine", "DeskForge",
               "SonicLab", "PixelPro", "AeroDesk", "BrightPath",
               "LumaCraft", "TerraTone", "NimbusLab", "ForgeLine"]
_GEN_COLORS = ["black", "white", "gray", "silver", "blue", "red", "green", "navy"]
_GEN_DESCRIPTORS = ["Ergo", "Pro", "Ultra", "Lite", "Max", "Silent",
                    "Studio", "Elite", "Compact", "Flex", "Aero", "Prime",
                    "AirFlow", "Smart", "Touch", "Solar", "Titanium",
                    "Hybrid", "Quantum", "Nova", "Zephyr", "Vortex",
                    "Echo", "Pulse", "Atlas", "Nimbus", "Orbit", "Lumen",
                    "Terra", "Pixel", "Wave", "Onyx"]
_GEN_MODELS = ["S100", "S200", "S300", "X1", "X2", "X5", "MK-II", "MK-III",
               "Pro 5", "Pro 7", "Air", "Go", "Plus", "Mini",
               "M10", "M20", "X9", "T1", "T2", "Gen3", "Gen4", "Nano",
               "Mega", "Duo", "Trio", "Z5", "V2", "Core", "S400", "S500"]

_GEN_CATEGORY_SPECS = {
    "peripherals": {
        "sku_prefix": "PH", "price": (14.99, 249.99),
        "cores": ["Mouse", "Keyboard", "Monitor", "Webcam", "Docking Station",
                  "Trackpad", "Headset Stand", "USB Hub", "KVM Switch",
                  "Graphics Tablet", "Monitor Arm", "Laptop Riser", "Wrist Rest",
                  "Desk Mat", "Microphone Arm", "Privacy Filter"],
        "descriptors": _GEN_DESCRIPTORS + ["Wireless", "RGB", "Gaming"],
        "tags": ["wireless", "usb", "office", "gaming", "ergonomic", "rgb",
                 "laptop", "desk", "bluetooth", "4k", "video", "aluminum"],
        "attrs": lambda r: {"connectivity": r.choice(
            ["wired USB", "2.4GHz wireless", "Bluetooth 5.2", "USB-C"]),
            "warranty_years": r.choice([1, 2, 3])},
        "blurbs": ["{brand} {core} with {desc} design for a cleaner desk setup.",
                   "This {desc_l} {core_l} is built for daily work and play.",
                   "{brand}'s {desc_l} {core_l} — reliable performance, modern styling."],
    },
    "audio": {
        "sku_prefix": "AD", "price": (11.99, 349.99),
        "cores": ["Earbuds", "Headphones", "Bluetooth Speaker", "Soundbar",
                  "USB Microphone", "Earphones", "Studio Monitor", "Audio Interface",
                  "Headphone Stand", "Conference Speaker", "Portable Radio",
                  "Karaoke Mic", "Sound Mixer", "Turntable"],
        "descriptors": _GEN_DESCRIPTORS + ["Wireless", "Bass+", "Hi-Fi"],
        "tags": ["wireless", "bluetooth", "audio", "anc", "premium", "bass",
                 "studio", "podcast", "portable", "waterproof", "hi-fi"],
        "attrs": lambda r: {"battery_hours": r.randint(4, 40),
                            "bluetooth": r.choice(["5.2", "5.3", "5.4"])},
        "blurbs": ["{brand} {core} with {desc} tuning for rich, detailed sound.",
                   "This {desc_l} {core_l} handles music, calls, and everything between.",
                   "{brand}'s {desc_l} {core_l} — deep bass, clear highs."],
    },
    "cables": {
        "sku_prefix": "CB", "price": (4.99, 79.99),
        "cores": ["USB-C Cable", "HDMI Cable", "Ethernet Cable", "DisplayPort Cable",
                  "Wireless Charger", "GaN Charger", "Cable Organizer", "Extension Cord",
                  "Adapter Kit", "Braided Cable", "Power Strip", "Lightning Cable",
                  "Optical Cable", "USB-C Adapter"],
        "descriptors": _GEN_DESCRIPTORS + ["Fast-Charge", "Braided"],
        "tags": ["usb-c", "cable", "charging", "hdmi", "network", "video",
                 "adapter", "fast-charge", "braided", "laptop", "power"],
        "attrs": lambda r: {"length": r.choice(["0.5m", "1m", "2m", "3m", "5m"]),
                            "certified": r.choice([True, True, False])},
        "blurbs": ["{brand} {core} with {desc} build for dependable everyday use.",
                   "This {desc_l} {core_l} keeps power and data tidy where you need it.",
                   "{brand}'s {desc_l} {core_l}, tested for thousands of bends."],
    },
    "office": {
        "sku_prefix": "OF", "price": (9.99, 199.99),
        "cores": ["Desk Lamp", "Monitor Light", "Desk Organizer", "Footrest",
                  "Cable Tray", "Desk Shelf", "Chair Mat", "Whiteboard",
                  "Desk Clock", "Pen Holder", "File Tray", "Monitor Riser",
                  "Desk Drawer", "Privacy Screen", "Ergonomic Cushion", "Bookends"],
        "descriptors": _GEN_DESCRIPTORS + ["LED", "Bamboo"],
        "tags": ["office", "desk", "ergonomic", "lamp", "organizer", "monitor",
                 "led", "bamboo", "wireless", "light", "storage"],
        "attrs": lambda r: {"material": r.choice(
            ["bamboo", "aluminum", "fabric", "steel", "plastic"])},
        "blurbs": ["{brand} {core} with {desc} styling for a calmer workspace.",
                   "This {desc_l} {core_l} keeps your desk tidy and comfortable.",
                   "{brand}'s {desc_l} {core_l} — small upgrade, big difference."],
    },
}


def _generate_catalog_products():
    """Deterministic extra products (no meaningless duplicates).

    A generator: yields one product dict at a time so the 100k catalog is
    never held in memory all at once; callers insert in controlled batches.

    Title space per category is cores x descriptors x colors x models
    (~16 x ~35 x 8 x 30 ~= 134k combinations), so 25k products per category
    stay varied; any residual collision gets a deterministic Mk suffix.
    """
    rng = random.Random(20260928)
    used_titles = {t for _, t, *_ in CATALOG} | {INACTIVE_PRODUCT[1]}
    used_skus = {s for s, *_ in CATALOG} | {INACTIVE_PRODUCT[0]}
    # Split the generated target evenly across the four categories.
    n_generated = CATALOG_TARGET_TOTAL - len(CATALOG) - 1  # minus inactive fixture
    cats = list(_GEN_CATEGORY_SPECS)
    base, rem = divmod(n_generated, len(cats))
    counts = {c: base + (1 if i < rem else 0) for i, c in enumerate(cats)}
    for cat, spec in _GEN_CATEGORY_SPECS.items():
        for i in range(counts[cat]):
            sku = f"{spec['sku_prefix']}-{1000 + i}"
            assert sku not in used_skus, f"duplicate sku {sku}"
            used_skus.add(sku)
            core = rng.choice(spec["cores"])
            desc = rng.choice(spec["descriptors"])
            model = rng.choice(_GEN_MODELS)
            color = rng.choice(_GEN_COLORS)
            title = f"{desc} {color.title()} {core} {model}"
            suffix = 2
            while title in used_titles:
                title = f"{desc} {color.title()} {core} {model} Mk{suffix}"
                suffix += 1
            used_titles.add(title)
            brand = rng.choice(_GEN_BRANDS)
            variants = []
            for _ in range(rng.choice([1, 1, 2, 2, 3])):
                vcolor = rng.choice(_GEN_COLORS)
                variants.append({"sku": f"{sku}-{vcolor[:3].upper()}",
                                 "color": vcolor,
                                 "stock": rng.randint(0, 120)})
            tags = sorted(rng.sample(spec["tags"], k=rng.randint(2, 4)))
            attrs = {"brand": brand, "color": color}
            attrs.update(spec["attrs"](rng))
            blurb = rng.choice(spec["blurbs"])
            yield {
                "sku": sku, "title": title,
                "description": blurb.format(brand=brand, core=core, desc=desc,
                                           core_l=core.lower(), desc_l=desc.lower()),
                "price": round(rng.uniform(*spec["price"]), 2),
                "category": cat, "tags": tags, "attributes": attrs,
                "variants": variants,
                "image_url": _image_url_for(title, cat),
                "stock": sum(v["stock"] for v in variants),
                # sprinkle a few inactive products in deterministically
                # (~2.8% -> ~2,800 inactive of 100,000)
                "active": rng.random() >= 0.028,
                "updated_at": NOW,
            }

STATUSES = ["PENDING", "PROCESSING", "SHIPPED"]


def seed_postgres_schema(pool):
    with open("scripts/init_db.sql") as f:
        sql = f.read()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql)  # CREATE TABLE IF NOT EXISTS ...
        cur.execute("TRUNCATE users, orders, order_items RESTART IDENTITY CASCADE")
        for uid, name, email in USERS:
            cur.execute(
                "INSERT INTO users (id, name, email) VALUES (%s, %s, %s)",
                (uid, name, email),
            )
        cur.execute("SELECT setval('users_id_seq', 8)")
        cur.execute(
            "UPDATE users SET role = 'admin' WHERE id = ANY(%s)",
            (list(ADMIN_USER_IDS),),
        )
    print(f"Postgres: schema ready, {len(USERS)} users")


def iter_product_docs():
    """The full deterministic product catalog (hand-written + inactive
    fixture + generated) as a lazy iterator. Separated from seed_mongo so the
    product-only reindex script can reuse it without touching
    PostgreSQL/orders. At most one insert batch is materialized at a time."""
    for sku, title, desc, price, cat, tags, attrs, variants in CATALOG:
        yield {
            "sku": sku, "title": title, "description": desc, "price": price,
            "category": cat, "tags": tags, "attributes": attrs, "variants": variants,
            "image_url": _image_url_for(title, cat),
            "stock": sum(v.get("stock", 0) for v in variants),
            "active": True, "updated_at": NOW,
        }
    sku, title, desc, price, cat, tags, attrs, variants = INACTIVE_PRODUCT
    yield {
        "sku": sku, "title": title, "description": desc, "price": price,
        "category": cat, "tags": tags, "attributes": attrs, "variants": variants,
        "image_url": _image_url_for(title, cat),
        "stock": sum(v.get("stock", 0) for v in variants),
        "active": False, "updated_at": NOW,
    }
    yield from _generate_catalog_products()


def build_product_docs():
    """Materialize the full catalog (handy for quick checks; seed_mongo
    streams via iter_product_docs instead)."""
    docs = list(iter_product_docs())
    assert len(docs) == CATALOG_TARGET_TOTAL, \
        f"catalog size {len(docs)} != target {CATALOG_TARGET_TOTAL}"
    return docs


# One insert_many call per chunk: 100k individual inserts would take
# orders of magnitude longer and hammer the server with round-trips.
MONGO_INSERT_CHUNK = 10000


def seed_mongo(mdb):
    mdb.products.delete_many({})
    batch: list[dict] = []
    n_total = n_active = 0

    def _flush():
        if batch:
            mdb.products.insert_many(batch, ordered=False)
            batch.clear()

    for doc in iter_product_docs():
        batch.append(doc)
        n_total += 1
        n_active += 1 if doc["active"] else 0
        if len(batch) >= MONGO_INSERT_CHUNK:
            _flush()
    _flush()
    assert n_total == CATALOG_TARGET_TOTAL, \
        f"catalog size {n_total} != target {CATALOG_TARGET_TOTAL}"
    print(f"MongoDB: {n_total} products ({n_active} active, {n_total - n_active} inactive)")


def build_order_specs(by_title):
    """Deterministic order plan: {user_id, picks:[(title, qty)], days_ago}."""
    random.seed(42)
    specs = []

    def add(user_id, picks, days_ago):
        specs.append({"user_id": user_id, "picks": list(picks), "days_ago": days_ago})

    # Group A: 5 cheap orders (< $30) — also the 5 recent ones
    cheap = ["USB-C Cable 1m", "HDMI Cable 2m", "Wired Earphones",
             "Ethernet Cable 5m", "Cable Management Kit"]
    for i, t in enumerate(cheap):
        add((i % 8) + 1, [(t, 1)], [1, 3, 5, 2, 6][i])

    # Group B: 6 mid orders ($30-$150)
    mid_combos = [
        [("Wireless Mouse", 1), ("Mouse Pad XL", 1)],          # 70.15
        [("Bluetooth Speaker", 1), ("USB-C Hub 7-in-1", 1)],   # 94.99
        [("Wireless Earbuds", 1), ("Wireless Charger Pad", 1)],# 109.98
        [("Desk Lamp LED", 1), ("Cable Management Kit", 1)],   # 49.49
        [("Gaming Mouse", 1)],                                 # 65.00
        [("USB Microphone", 1), ("DisplayPort Cable", 1)],     # 107.99
    ]
    for i, combo in enumerate(mid_combos):
        add(((i + 5) % 8) + 1, combo, random.randint(8, 55))

    # Group C: 5 premium orders (> $200)
    premium_combos = [
        [("Noise Cancelling Headphones", 1), ("Wireless Earbuds", 1)],   # 278.99
        [("Webcam 4K Pro", 1), ("Mechanical Keyboard", 1)],              # 220.33
        [("Soundbar", 1), ("Bluetooth Speaker", 1), ("HDMI Cable 2m", 1)],  # 212.97
        [("Noise Cancelling Headphones", 2)],                            # 398.00
        [("Mechanical Keyboard", 1), ("Wireless Keyboard", 1), ("Desk Lamp LED", 1)],  # 222.83
    ]
    for i, combo in enumerate(premium_combos):
        add(((i + 3) % 8) + 1, combo, random.randint(8, 55))

    # Group D: 26 random orders (1-4 items, qty 1-3)
    # NOTE: picks stay on the original hand-written catalog titles so the
    # accepted order dataset is byte-identical before/after the catalog expansion.
    titles = [t for _, t, *_ in CATALOG]
    for i in range(26):
        n = random.choice([1, 1, 2, 2, 2, 3, 4])
        picks = [(random.choice(titles), random.randint(1, 3)) for _ in range(n)]
        # merge duplicate titles
        merged: dict[str, int] = {}
        for t, q in picks:
            merged[t] = merged.get(t, 0) + q
        add(((i + 16) % 8) + 1, list(merged.items()), random.randint(1, 90))

    assert len(specs) == 42

    # --- Fixtures (only touch Group D indices 16..41, never the band groups) ---
    def add_item(idx, title, qty=1):
        picks = dict(specs[idx]["picks"])
        picks[title] = picks.get(title, 0) + qty
        specs[idx]["picks"] = list(picks.items())

    for idx in range(16, 24):          # 8 orders contain Wireless Mouse
        add_item(idx, "Wireless Mouse")
    for idx in (24, 25, 26):          # 3 orders contain Mechanical Keyboard
        add_item(idx, "Mechanical Keyboard")
    for idx in (16, 17):              # 2 of those contain both
        add_item(idx, "Mechanical Keyboard")
    for idx in (18, 26, 34):          # Wendy Wireless (user 3): 3 orders with a wireless product
        assert specs[idx]["user_id"] == 3, f"fixture user mismatch at {idx}"
        add_item(idx, random.choice(
            ["Wireless Earbuds", "Wireless Charger Pad", "Bluetooth Speaker"]))

    # --- Dates: 5 older than 60 days (Morgan Lee / Riley Brooks) ---
    for idx, days in [(6, 65), (14, 72), (22, 84), (7, 68), (15, 79)]:
        assert specs[idx]["user_id"] in (7, 8)
        specs[idx]["days_ago"] = days

    # --- Statuses: balanced round-robin -> 14 each ---
    for i, spec in enumerate(specs):
        spec["status"] = STATUSES[i % 3]

    return specs


def seed_orders(pool, mdb, specs):
    by_title = {d["title"]: d for d in mdb.products.find({"active": True})}
    order_ids = []
    for spec in specs:
        items = []
        for title, qty in spec["picks"]:
            p = by_title[title]
            items.append({
                "product_id": str(p["_id"]),
                "title": p["title"],          # snapshot at checkout
                "quantity": qty,
                "unit_price": p["price"],      # snapshot at checkout
            })
        order_date = NOW - timedelta(days=spec["days_ago"],
                                     hours=random.randint(0, 23),
                                     minutes=random.randint(0, 59))
        order = pg_repo.create_order(pool, spec["user_id"], items,
                                     order_date=order_date, status=spec["status"])
        order_ids.append(order["id"])
    print(f"Postgres: {len(order_ids)} orders seeded")
    return order_ids


# ---------- Bulk order generation (~50k orders) ----------
# The 42 hand-crafted specs above are the assignment's demo dataset and stay
# byte-identical. These deterministic bulk specs are APPENDED after them so
# order ids 1..42 (and every fixture built on them) never move.
ORDER_TARGET_TOTAL = 50000

_BULK_ITEM_COUNT_WEIGHTS = [0.12, 0.24, 0.26, 0.16, 0.10, 0.06, 0.04, 0.02]  # 1..8 items
_BULK_QTY_WEIGHTS = [0.60, 0.30, 0.10]  # qty 1..3


def _status_for_age(rng, days_ago):
    """Realistic status mix: old orders have shipped, recent ones are moving."""
    r = rng.random()
    if days_ago > 90:
        return "SHIPPED"
    if days_ago >= 30:
        return "SHIPPED" if r < 0.70 else "PROCESSING"
    if r < 0.40:
        return "PENDING"
    return "PROCESSING" if r < 0.80 else "SHIPPED"


def build_bulk_order_specs(by_title, n):
    """Deterministic bulk order specs: {user_id, picks:[(title, qty)],
    days_ago, status}. Own Random instance; the global random.seed(42)
    sequence used by build_order_specs/seed_orders is untouched."""
    rng = random.Random(20260928 + 7)
    titles = sorted(by_title)
    # popularity skew: a shuffled ranking where early titles sell far more,
    # so products are reused naturally across many orders
    ranking = titles[:]
    rng.shuffle(ranking)
    weights = [1.0 / (i + 1) ** 0.85 for i in range(len(ranking))]
    counts = [1, 2, 3, 4, 5, 6, 7, 8]
    qtys = [1, 2, 3]
    specs = []
    for _ in range(n):
        n_items = rng.choices(counts, weights=_BULK_ITEM_COUNT_WEIGHTS)[0]
        picks: dict[str, int] = {}
        for title in rng.choices(ranking, weights=weights, k=n_items):
            q = rng.choices(qtys, weights=_BULK_QTY_WEIGHTS)[0]
            picks[title] = picks.get(title, 0) + q
        # recency-skewed: mean ~120 days, capped at 2 years so date-range
        # filtering stays meaningful
        days_ago = min(int(rng.expovariate(1 / 120)), 729)
        specs.append({
            "user_id": rng.randint(1, 8),
            "picks": list(picks.items()),
            "days_ago": days_ago,
            "status": _status_for_age(rng, days_ago),
        })
    return specs


def seed_bulk_orders(pool, by_title, specs):
    """Insert the bulk specs with multi-row INSERTs (a few dozen statements
    for ~50k orders + ~165k items) instead of one transaction per order.
    Snapshots (title/unit_price) are copied from the catalog exactly like
    create_order does. Returns the inserted order ids in insert order."""
    brng = random.Random(20260928 + 11)
    order_rows = []       # (user_id, order_date, status, total_amount)
    per_order_lines = []  # [(product_id, title, qty, unit_price)]
    for spec in specs:
        lines = []
        total = 0.0
        for title, qty in spec["picks"]:
            p = by_title[title]
            unit = float(p["price"])
            lines.append((str(p["_id"]), p["title"], qty, unit))
            total += qty * unit
        order_date = NOW - timedelta(days=spec["days_ago"],
                                     hours=brng.randint(0, 23),
                                     minutes=brng.randint(0, 59))
        order_rows.append((spec["user_id"], order_date, spec["status"], round(total, 2)))
        per_order_lines.append(lines)

    with pool.connection() as conn, conn.cursor() as cur:
        with conn.transaction():
            order_ids = []
            for i in range(0, len(order_rows), 2000):
                chunk = order_rows[i:i + 2000]
                placeholders = ",".join(["(%s,%s,%s,%s)"] * len(chunk))
                cur.execute(
                    "INSERT INTO orders (user_id, order_date, status, total_amount) "
                    f"VALUES {placeholders} RETURNING id",
                    [v for row in chunk for v in row],
                )
                ids = [r["id"] for r in cur.fetchall()]
                assert len(ids) == len(chunk), "bulk order insert lost rows"
                assert ids == sorted(ids), "bulk order ids not sequential"
                order_ids.extend(ids)
            item_rows = []
            for oid, lines in zip(order_ids, per_order_lines):
                for product_id, title, qty, unit in lines:
                    item_rows.append((oid, product_id, title, qty, unit))
            for i in range(0, len(item_rows), 5000):
                chunk = item_rows[i:i + 5000]
                placeholders = ",".join(["(%s,%s,%s,%s,%s)"] * len(chunk))
                cur.execute(
                    "INSERT INTO order_items "
                    "(order_id, product_id, title, quantity, unit_price) "
                    f"VALUES {placeholders}",
                    [v for row in chunk for v in row],
                )
    print(f"Postgres: {len(order_ids)} bulk orders, {len(item_rows)} order_items seeded")
    return order_ids


def rename_fixture(mdb):
    """Deliberate snapshot mismatch: catalog moves on, history does not."""
    mdb.products.update_one(
        {"title": "Wireless Mouse"},
        {"$set": {"title": "Wireless Mouse Pro", "price": 59.99, "updated_at": NOW}},
    )
    print("MongoDB: 'Wireless Mouse' renamed to 'Wireless Mouse Pro' ($59.99)")


def verify(pool, mdb, es, index):
    errs = []

    def check(cond, msg):
        if not cond:
            errs.append(msg)

    # --- PostgreSQL users ---
    users = pg_repo.list_users(pool)
    check(len(users) == 8, f"users: expected 8, got {len(users)}")
    admins = sorted(u["id"] for u in users if u.get("role") == "admin")
    check(admins == sorted(ADMIN_USER_IDS),
          f"admin users: expected {sorted(ADMIN_USER_IDS)}, got {admins}")

    # --- MongoDB catalog ---
    total_products = mdb.products.count_documents({})
    n_active = mdb.products.count_documents({"active": True})
    n_inactive = total_products - n_active
    check(total_products == 100000,
          f"products: expected 100000, got {total_products}")
    check(96000 <= n_active <= 98000,
          f"active products: expected 96000-98000, got {n_active}")
    check(n_inactive >= 2000,
          f"inactive products: expected >=2000, got {n_inactive}")
    wireless = mdb.products.count_documents(
        {"active": True, "$or": [{"title": {"$regex": "wireless", "$options": "i"}},
                                 {"tags": "wireless"}]})
    check(wireless >= 6, f"wireless products: expected >=6, got {wireless}")
    for title in ("Wireless Mouse Pro", "Mechanical Keyboard", "Wireless Earbuds",
                  "USB-C Hub 7-in-1", "Desk Lamp LED", "Noise Cancelling Headphones"):
        check(mdb.products.count_documents({"title": title, "active": True}) >= 1,
              f"required product missing: {title}")
    sample = mdb.products.find_one({"active": True})
    check({"sku", "title", "description", "price", "category", "tags",
           "attributes", "variants", "active", "updated_at"} <= set(sample),
          "product document structure changed")
    cat_counts = {c: mdb.products.count_documents({"category": c})
                  for c in ("peripherals", "audio", "cables", "office")}
    check(all(v >= 20000 for v in cat_counts.values()),
          f"category counts: {cat_counts}")

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM orders")
        n_orders = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM order_items")
        n_items = cur.fetchone()["n"]
        cur.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status")
        statuses = {r["status"]: r["n"] for r in cur.fetchall()}
        cur.execute("SELECT user_id, COUNT(*) n FROM orders GROUP BY user_id")
        per_user = {r["user_id"]: r["n"] for r in cur.fetchall()}
        cur.execute("SELECT MIN(order_date) AS lo, MAX(order_date) AS hi FROM orders")
        date_range = cur.fetchone()
        cur.execute("SELECT MIN(total_amount) AS mn, MAX(total_amount) AS mx, "
                    "AVG(total_amount) AS av FROM orders")
        totals = cur.fetchone()
        # --- the original 42-order assignment fixtures (still intact) ---
        cur.execute("SELECT COUNT(*) n FROM orders WHERE order_date < %s",
                    (NOW - timedelta(days=60),))
        old = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM orders WHERE order_date > %s",
                    (NOW - timedelta(days=7),))
        recent = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM orders WHERE total_amount < 30")
        cheap = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM orders WHERE total_amount BETWEEN 30 AND 150")
        mid = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM orders WHERE total_amount > 200")
        premium = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(DISTINCT order_id) n FROM order_items WHERE title = 'Wireless Mouse'")
        wm = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(DISTINCT order_id) n FROM order_items WHERE title = 'Mechanical Keyboard'")
        mk = cur.fetchone()["n"]
        cur.execute("""SELECT COUNT(*) n FROM (
            SELECT order_id FROM order_items WHERE title = 'Wireless Mouse'
            INTERSECT
            SELECT order_id FROM order_items WHERE title = 'Mechanical Keyboard') t""")
        both = cur.fetchone()["n"]
        cur.execute("""SELECT COUNT(DISTINCT o.id) n FROM orders o
                       JOIN order_items i ON i.order_id = o.id
                       WHERE o.user_id = 3 AND i.title ILIKE '%wireless%'""")
        wendy_wireless = cur.fetchone()["n"]

    check(n_orders == ORDER_TARGET_TOTAL,
          f"orders: expected {ORDER_TARGET_TOTAL}, got {n_orders}")
    check(150000 <= n_items <= 200000,
          f"order_items: expected 150k-200k, got {n_items}")
    avg_items = n_items / max(n_orders, 1)
    check(2.5 <= avg_items <= 4.5, f"avg items/order: {avg_items:.2f}")
    for s in ("PENDING", "PROCESSING", "SHIPPED"):
        check(statuses.get(s, 0) >= 1000,
              f"status {s}: expected >=1000, got {statuses.get(s, 0)}")
    check(len(per_user) == 8 and all(v >= 1000 for v in per_user.values()),
          f"per-user orders: {per_user}")
    check(date_range["lo"] < NOW - timedelta(days=700),
          f"date range too narrow (oldest: {date_range['lo']})")
    check(date_range["hi"] > NOW - timedelta(days=1),
          f"no recent orders (newest: {date_range['hi']})")
    check(totals["mn"] > 0 and totals["mx"] > totals["mn"] and totals["av"] > 0,
          f"order totals look wrong: {dict(totals)}")
    check(old >= 5, f"orders older than 60d: expected >=5, got {old}")
    check(recent >= 5, f"orders in last 7d: expected >=5, got {recent}")
    check(cheap >= 5 and mid >= 5 and premium >= 5,
          f"price bands <30/30-150/>200: {cheap}/{mid}/{premium}")
    check(wm >= 8, f"'Wireless Mouse' orders: expected >=8, got {wm}")
    check(mk >= 3, f"'Mechanical Keyboard' orders: expected >=3, got {mk}")
    check(both >= 2, f"orders with both: expected >=2, got {both}")
    check(wendy_wireless >= 3, f"Wendy wireless orders: expected >=3, got {wendy_wireless}")

    es_count = es.count(index=index)["count"]
    check(es_count == n_orders, f"ES docs {es_count} != Postgres orders {n_orders}")

    es_products = es.count(index=settings.es_products_index)["count"]
    check(es_products == total_products,
          f"ES product docs {es_products} != MongoDB products {total_products}")

    live = mdb.products.find_one({"sku": "WM-001"})
    check(live["title"] == "Wireless Mouse Pro",
          f"rename fixture missing: {live['title']}")

    if errs:
        print("SEED VERIFICATION FAILED:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print(f"Postgres: {len(users)} users, {n_orders} orders, {n_items} order_items "
          f"(avg {avg_items:.2f}/order)")
    print(f"  statuses={statuses}")
    print(f"  date range: {date_range['lo']} .. {date_range['hi']}")
    print(f"  totals: min={totals['mn']} max={totals['mx']} "
          f"avg={round(float(totals['av']), 2)}")
    print(f"MongoDB: {total_products} products "
          f"({n_active} active, {n_inactive} inactive), categories={cat_counts}")
    print(f"Elasticsearch: index '{index}' has {es_count} docs "
          f"(== Postgres orders)")
    print(f"Elasticsearch: index '{settings.es_products_index}' has "
          f"{es_products} docs (== MongoDB products)")


def main():
    pool, mdb, es = db.pg_pool(), db.mongo_db(), db.es_client()
    seed_postgres_schema(pool)
    seed_mongo(mdb)
    by_title = {d["title"]: d for d in mdb.products.find({"active": True})}
    specs = build_order_specs(by_title)          # the 42 hand-crafted orders
    seed_orders(pool, mdb, specs)
    bulk_specs = build_bulk_order_specs(by_title, ORDER_TARGET_TOTAL - len(specs))
    seed_bulk_orders(pool, by_title, bulk_specs)
    rename_fixture(mdb)
    n = sync_service.reindex_all(pool, es, settings.es_index)
    print(f"Elasticsearch: index '{settings.es_index}' rebuilt with {n} docs")
    n_products = sync_service.reindex_all_products(
        mdb, es, settings.es_products_index)
    print(f"Elasticsearch: index '{settings.es_products_index}' rebuilt "
          f"with {n_products} docs")
    verify(pool, mdb, es, settings.es_index)
    db.close_all()


if __name__ == "__main__":
    main()
