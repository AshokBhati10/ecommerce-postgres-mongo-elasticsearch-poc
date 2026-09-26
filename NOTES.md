# Learning notes — polyglot persistence

## 1. Split-brain: what breaks when stores disagree

The catalog rename fixture makes split-brain concrete: MongoDB sells
`Wireless Mouse Pro` at $59.99 while order history shows `Wireless Mouse` at
$50.16. Neither store is "wrong" — they answer different questions (what can I
buy now vs. what did the customer agree to then). The real split-brain risk is
order data: if Elasticsearch says an order is PENDING while PostgreSQL says
SHIPPED, customer support acts on a lie. Mitigations used here:

- PostgreSQL is the single system of record; ES is a derived index.
- `/api/orders/{id}` returns `es_in_sync` so divergence is visible, not silent.
- Recovery is always "rebuild from Postgres" (`scripts/reindex_orders.py`),
  never "merge the two and hope".

## 2. Elasticsearch vs SQL search

SQL `LIKE '%wireless%'` can't rank, can't search customers and items in one
query, and degrades on every row. The ES `multi_match` query searches
`customer.name`, `customer.email`, `items.title`, and `items.sku` in one shot
with relevance scoring — typing "Wendy" finds Wendy Wireless's orders even
though none of her products are wireless. Aggregations (revenue, per-status
counts, avg order value) come back in the same request, which would be three
separate SQL queries plus application-side bucketing. The price: an eventually
consistent copy of the data and a mapping to maintain. Search-heavy admin
dashboards justify it; a single lookup by order ID never would.

## 3. MongoDB catalog modeling

Products are documents because their shape varies: a shirt has sizes, a
headphone has driver specs, a bundle has neither. One `products` collection
holds `tags` (array), `attributes` (free-form object), and `variants` (array of
SKU/price/stock objects) without migrations or sparse nullable columns.
The tradeoff is discipline: queries must tolerate missing keys, and there is
no foreign key stopping an order from referencing a deleted product — which is
exactly why checkout validates product IDs and then snapshots the data it
needs.

## 4. Snapshotting

`order_items` stores `title`, `unit_price`, and `variant_label` copied from the
catalog at checkout time. The seeded history proves the point: order 17 still
says `Wireless Mouse` / $50.16 after the catalog renamed the product and raised
the price. Alternatives (joining orders to live products, or versioning every
product) either rewrite history or complicate the catalog. Snapshots are
redundant by design — storage is cheap, legal/financial history is not. The
rule: transactional records are immutable; reference data is mutable; never let
a mutable record edit the past.

## 5. Write-path discipline

Every order flows through one choke point: `POST /api/orders` → validate
against Mongo → insert users/orders/order_items in a single Postgres
transaction → sync ES. No screen writes to ES directly; no screen writes
orders to Mongo. This ordering matters: the Postgres commit is the point of no
return. Dual-write happens *after* commit (a failed ES write never rolls back
a paid order), and the polling worker plus full reindex exist precisely because
"after commit" can still fail. The discipline is boring on purpose — one write
path, one source of truth, every derived store rebuildable.
