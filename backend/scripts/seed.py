"""Reproducible seed: Postgres users/orders/items, MongoDB catalog (+ inactive
product + the Wireless Mouse -> Wireless Mouse Pro rename fixture), and a
fully caught-up Elasticsearch orders index.

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
    print(f"Postgres: schema ready, {len(USERS)} users")


def seed_mongo(mdb):
    mdb.products.delete_many({})
    docs = []
    for sku, title, desc, price, cat, tags, attrs, variants in CATALOG:
        docs.append({
            "sku": sku, "title": title, "description": desc, "price": price,
            "category": cat, "tags": tags, "attributes": attrs, "variants": variants,
            "active": True, "updated_at": NOW,
        })
    sku, title, desc, price, cat, tags, attrs, variants = INACTIVE_PRODUCT
    docs.append({
        "sku": sku, "title": title, "description": desc, "price": price,
        "category": cat, "tags": tags, "attributes": attrs, "variants": variants,
        "active": False, "updated_at": NOW,
    })
    mdb.products.insert_many(docs)
    print(f"MongoDB: {len(docs)} products ({len(docs) - 1} active, 1 inactive)")


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
    titles = list(by_title)
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

    users = pg_repo.list_users(pool)
    check(len(users) == 8, f"users: expected 8, got {len(users)}")
    active = mdb.products.count_documents({"active": True})
    check(active >= 24, f"active products: expected >=24, got {active}")
    check(mdb.products.count_documents({"active": False}) >= 1, "missing inactive product")
    wireless = mdb.products.count_documents(
        {"active": True, "$or": [{"title": {"$regex": "wireless", "$options": "i"}},
                                 {"tags": "wireless"}]})
    check(wireless >= 6, f"wireless products: expected >=6, got {wireless}")

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM orders")
        n_orders = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n FROM order_items")
        n_items = cur.fetchone()["n"]
        cur.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status")
        statuses = {r["status"]: r["n"] for r in cur.fetchall()}
        cur.execute("SELECT user_id, COUNT(*) n FROM orders GROUP BY user_id")
        per_user = {r["user_id"]: r["n"] for r in cur.fetchall()}
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

    check(n_orders >= 40, f"orders: expected >=40, got {n_orders}")
    check(n_items >= 80, f"order_items: expected >=80, got {n_items}")
    check(n_items / max(n_orders, 1) >= 2, "avg items/order < 2")
    for s in ("PENDING", "PROCESSING", "SHIPPED"):
        check(statuses.get(s, 0) >= 10, f"status {s}: expected >=10, got {statuses.get(s, 0)}")
    check(all(v >= 2 for v in per_user.values()) and len(per_user) == 8,
          f"per-user orders: {per_user}")
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

    live = mdb.products.find_one({"sku": "WM-001"})
    check(live["title"] == "Wireless Mouse Pro",
          f"rename fixture missing: {live['title']}")

    if errs:
        print("SEED VERIFICATION FAILED:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print(f"Verify OK: {n_orders} orders, {n_items} items, ES docs={es_count}, "
          f"statuses={statuses}, bands(<30/30-150/>200)={cheap}/{mid}/{premium}")


def main():
    pool, mdb, es = db.pg_pool(), db.mongo_db(), db.es_client()
    seed_postgres_schema(pool)
    seed_mongo(mdb)
    by_title = {d["title"]: d for d in mdb.products.find({"active": True})}
    specs = build_order_specs(by_title)
    seed_orders(pool, mdb, specs)
    rename_fixture(mdb)
    n = sync_service.reindex_all(pool, es, settings.es_index)
    print(f"Elasticsearch: index '{settings.es_index}' rebuilt with {n} docs")
    verify(pool, mdb, es, settings.es_index)
    db.close_all()


if __name__ == "__main__":
    main()
