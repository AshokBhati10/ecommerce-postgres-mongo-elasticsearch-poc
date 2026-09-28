from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Users ----------
class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str = "customer"


# ---------- Products (MongoDB) ----------
class ProductCreate(BaseModel):
    sku: str
    title: str
    description: str = ""
    price: float = Field(gt=0)
    category: str
    tags: list[str] = []
    attributes: dict = {}
    variants: list[dict] = []
    image_url: str = ""
    stock: int = 0
    active: bool = True


class ProductUpdate(BaseModel):
    sku: str | None = None
    title: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = None
    tags: list[str] | None = None
    attributes: dict | None = None
    variants: list[dict] | None = None
    image_url: str | None = None
    stock: int | None = None
    active: bool | None = None


class ProductOut(BaseModel):
    id: str
    sku: str
    title: str
    description: str = ""
    price: float
    category: str
    tags: list[str] = []
    attributes: dict = {}
    variants: list[dict] = []
    image_url: str = ""
    stock: int = 0
    active: bool = True
    updated_at: datetime | None = None


class ProductPage(BaseModel):
    """Paginated catalog response (returned when `page` is given)."""
    items: list[ProductOut]
    page: int
    page_size: int
    total: int
    total_pages: int


# ---------- Orders (PostgreSQL) ----------
class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    user_id: int
    items: list[CartItem] = Field(min_length=1)


class OrderItemOut(BaseModel):
    product_id: str
    title: str
    quantity: int
    unit_price: float


class CustomerOut(BaseModel):
    id: int
    name: str
    email: str


class OrderOut(BaseModel):
    id: int
    user_id: int
    customer: CustomerOut | None = None
    order_date: datetime
    status: str
    total_amount: float
    updated_at: datetime
    items: list[OrderItemOut] = []


class OrderPlacedOut(OrderOut):
    es_synced: bool = False


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(PENDING|PROCESSING|SHIPPED)$")


# ---------- Search (Elasticsearch) ----------
class SearchRequest(BaseModel):
    q: str = ""
    statuses: list[str] = []
    date_from: str | None = None
    date_to: str | None = None
    min_total: float | None = None
    max_total: float | None = None
    size: int = Field(default=50, le=200)
