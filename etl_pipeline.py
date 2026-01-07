#!/usr/bin/env python3
"""
etl_pipeline.py
ETL Pipeline for fleximart (MySQL reference)

Extract: Read customers_raw.csv, products_raw.csv, sales_raw.csv
Transform:
  - Remove duplicates
  - Handle missing values
  - Standardize phone formats (+91-XXXXXXXXXX)
  - Standardize categories to canonical values
  - Convert date formats to YYYY-MM-DD
  - Use MySQL AUTO_INCREMENT as surrogate keys
Load:
  - Insert into MySQL tables: customers, products, orders, order_items
  - Generate data_quality_report.txt
"""

import csv
import os
import re
import sys
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

import mysql.connector
from mysql.connector import Error


# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("etl_pipeline.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

DATE_FORMATS = [
    "%Y-%m-%d",   # 2024-01-15
    "%d/%m/%Y",   # 15/01/2024
    "%m-%d-%Y",   # 01-22-2024
    "%m/%d/%Y",   # 02/22/2024 (if present)
]

def parse_date_to_iso(s: str):
    """Return date object or None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def normalize_phone_india(phone: str):
    """
    Standardize to +91-XXXXXXXXXX.
    - Keep last 10 digits if >=10
    - If <10 digits => return None
    """
    if phone is None:
        return None
    p = str(phone).strip()
    if not p:
        return None
    digits = re.sub(r"\D", "", p)
    if len(digits) < 10:
        return None
    digits = digits[-10:]
    return f"+91-{digits}"

def clean_city(city: str):
    if city is None:
        return None
    c = str(city).strip()
    if not c:
        return None
    # Title case but preserve common multi-word city names
    return " ".join([w.capitalize() for w in c.split()])

CATEGORY_MAP = {
    "electronics": "Electronics",
    "fashion": "Fashion",
    "groceries": "Groceries",
}

def normalize_category(cat: str):
    if cat is None:
        return None
    c = str(cat).strip()
    if not c:
        return None
    key = c.strip().lower()
    return CATEGORY_MAP.get(key, " ".join([w.capitalize() for w in key.split()]))

def to_decimal(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None

def to_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None

def safe_lower(s):
    return str(s).strip().lower() if s is not None else ""


# ---------------------------
# CSV Extraction
# ---------------------------

def read_csv_dicts(path: str):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
    return rows


# ---------------------------
# Transform: Customers
# ---------------------------

def transform_customers(raw_rows):
    report = {
        "input_records": len(raw_rows),
        "duplicates_removed": 0,
        "missing_email_filled": 0,
        "missing_email_dropped": 0,
        "phones_standardized": 0,
        "dates_parsed_failed": 0,
    }

    # 1) remove exact duplicates (same tuple across all columns)
    seen = set()
    deduped = []
    for r in raw_rows:
        key = tuple((k, (r.get(k) or "").strip()) for k in sorted(r.keys()))
        if key in seen:
            report["duplicates_removed"] += 1
            continue
        seen.add(key)
        deduped.append(r)

    cleaned = []
    for r in deduped:
        raw_customer_id = r.get("customer_id")
        first = (r.get("first_name") or "").strip()
        last = (r.get("last_name") or "").strip()

        email = (r.get("email") or "").strip()
        if not email:
            # strategy: generate deterministic placeholder due to NOT NULL UNIQUE constraint
            # uses raw_customer_id if present, else name-based
            base = (raw_customer_id or f"{first}.{last}" or "unknown").strip().lower()
            base = re.sub(r"[^a-z0-9]+", "", base) or "unknown"
            email = f"{base}@fleximart.local"
            report["missing_email_filled"] += 1

        phone_before = r.get("phone")
        phone = normalize_phone_india(phone_before)
        if phone_before and phone and phone_before.strip() != phone:
            report["phones_standardized"] += 1

        city = clean_city(r.get("city"))
        reg_date = parse_date_to_iso(r.get("registration_date"))
        if (r.get("registration_date") or "").strip() and reg_date is None:
            report["dates_parsed_failed"] += 1

        # Schema requires first_name/last_name/email NOT NULL
        if not first or not last or not email:
            # extremely rare; drop if any mandatory field missing
            report["missing_email_dropped"] += 1
            continue

        cleaned.append({
            "raw_customer_id": raw_customer_id,
            "first_name": first,
            "last_name": last,
            "email": email.lower(),  # enforce lowercase for uniqueness
            "phone": phone,
            "city": city,
            "registration_date": reg_date,
        })

    # dedup by email (unique constraint)
    email_seen = set()
    final = []
    for c in cleaned:
        e = c["email"]
        if e in email_seen:
            report["duplicates_removed"] += 1
            continue
        email_seen.add(e)
        final.append(c)

    report["output_records"] = len(final)
    return final, report


# ---------------------------
# Transform: Products
# ---------------------------

def median_decimal(vals):
    vals = sorted([v for v in vals if v is not None])
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / Decimal("2")

def transform_products(raw_rows):
    report = {
        "input_records": len(raw_rows),
        "duplicates_removed": 0,
        "missing_price_imputed": 0,
        "missing_stock_filled": 0,
        "categories_standardized": 0,
    }

    # remove exact duplicates
    seen = set()
    deduped = []
    for r in raw_rows:
        key = tuple((k, (r.get(k) or "").strip()) for k in sorted(r.keys()))
        if key in seen:
            report["duplicates_removed"] += 1
            continue
        seen.add(key)
        deduped.append(r)

    # normalize category first to compute medians per category
    tmp = []
    for r in deduped:
        raw_pid = r.get("product_id")
        name = (r.get("product_name") or "").strip()
        cat_raw = r.get("category")
        cat = normalize_category(cat_raw)
        if cat_raw and cat_raw.strip() and cat_raw.strip() != cat:
            report["categories_standardized"] += 1

        price = to_decimal(r.get("price"))
        stock = to_int(r.get("stock_quantity"))

        tmp.append({
            "raw_product_id": raw_pid,
            "product_name": name,
            "category": cat or "Unknown",
            "price": price,
            "stock_quantity": stock,
        })

    # compute median per category and global median
    by_cat = {}
    all_prices = []
    for p in tmp:
        if p["price"] is not None:
            by_cat.setdefault(p["category"], []).append(p["price"])
            all_prices.append(p["price"])

    global_med = median_decimal(all_prices) or Decimal("0.00")

    cat_meds = {c: (median_decimal(vals) or global_med) for c, vals in by_cat.items()}

    # fill missing price & stock
    cleaned = []
    for p in tmp:
        if not p["product_name"]:
            # product_name is NOT NULL; drop if missing
            report["duplicates_removed"] += 1
            continue

        if p["price"] is None:
            p["price"] = cat_meds.get(p["category"], global_med)
            report["missing_price_imputed"] += 1

        if p["stock_quantity"] is None:
            p["stock_quantity"] = 0
            report["missing_stock_filled"] += 1

        cleaned.append(p)

    # soft dedup: same (name, category, price) treat as duplicate
    uniq = set()
    final = []
    for p in cleaned:
        k = (safe_lower(p["product_name"]), safe_lower(p["category"]), str(p["price"]))
        if k in uniq:
            report["duplicates_removed"] += 1
            continue
        uniq.add(k)
        final.append(p)

    report["output_records"] = len(final)
    return final, report


# ---------------------------
# Transform: Sales -> Orders + Items
# ---------------------------

def transform_sales(raw_rows):
    report = {
        "input_records": len(raw_rows),
        "duplicates_removed": 0,
        "missing_customer_dropped": 0,
        "missing_product_dropped": 0,
        "date_parse_failed": 0,
        "output_records": 0,
    }

    # dedup by transaction_id
    seen_txn = set()
    deduped = []
    for r in raw_rows:
        tid = (r.get("transaction_id") or "").strip()
        if tid and tid in seen_txn:
            report["duplicates_removed"] += 1
            continue
        if tid:
            seen_txn.add(tid)
        deduped.append(r)

    cleaned = []
    for r in deduped:
        tid = (r.get("transaction_id") or "").strip()
        raw_cust = (r.get("customer_id") or "").strip()
        raw_prod = (r.get("product_id") or "").strip()

        if not raw_cust:
            report["missing_customer_dropped"] += 1
            continue
        if not raw_prod:
            report["missing_product_dropped"] += 1
            continue

        qty = to_int(r.get("quantity")) or 0
        unit_price = to_decimal(r.get("unit_price")) or Decimal("0.00")

        dt = parse_date_to_iso(r.get("transaction_date"))
        if (r.get("transaction_date") or "").strip() and dt is None:
            report["date_parse_failed"] += 1
            continue

        status = (r.get("status") or "Pending").strip() or "Pending"

        cleaned.append({
            "transaction_id": tid,
            "raw_customer_id": raw_cust,
            "raw_product_id": raw_prod,
            "quantity": qty if qty > 0 else 1,
            "unit_price": unit_price,
            "order_date": dt,
            "status": status,
        })

    report["output_records"] = len(cleaned)
    return cleaned, report


# ---------------------------
# Load into MySQL
# ---------------------------

def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "yash")
    password = os.getenv("DB_PASSWORD", "Yash@2014")
    database = os.getenv("DB_NAME", "fleximart")

    return mysql.connector.connect(
        host=host, port=port, user=user, password=password, database=database
    )

def load_customers(conn, customers):
    """
    Insert customers and return mapping:
      - email -> customer_id (surrogate)
      - raw_customer_id -> customer_id (best-effort)
    """
    email_to_id = {}
    raw_to_id = {}

    insert_sql = """
        INSERT INTO customers (first_name, last_name, email, phone, city, registration_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          phone=VALUES(phone),
          city=VALUES(city),
          registration_date=VALUES(registration_date)
    """

    select_id_sql = "SELECT customer_id FROM customers WHERE email = %s"

    cur = conn.cursor()
    loaded = 0

    for c in customers:
        cur.execute(insert_sql, (
            c["first_name"], c["last_name"], c["email"], c["phone"], c["city"], c["registration_date"]
        ))
        # retrieve id
        cur.execute(select_id_sql, (c["email"],))
        cid = cur.fetchone()[0]
        email_to_id[c["email"]] = cid
        if c["raw_customer_id"]:
            raw_to_id[c["raw_customer_id"]] = cid
        loaded += 1

    conn.commit()
    cur.close()
    return email_to_id, raw_to_id, loaded

def load_products(conn, products):
    """
    Insert products and return mapping:
      - product_signature -> product_id
      - raw_product_id -> product_id (best-effort)
    Signature used to map sales -> products reliably.
    """
    sig_to_id = {}
    raw_to_id = {}

    insert_sql = """
        INSERT INTO products (product_name, category, price, stock_quantity)
        VALUES (%s, %s, %s, %s)
    """

    select_id_sql = """
        SELECT product_id FROM products
        WHERE product_name = %s AND category = %s AND price = %s
        ORDER BY product_id DESC LIMIT 1
    """

    cur = conn.cursor()
    loaded = 0

    for p in products:
        cur.execute(insert_sql, (
            p["product_name"], p["category"], p["price"], p["stock_quantity"]
        ))
        cur.execute(select_id_sql, (p["product_name"], p["category"], p["price"]))
        pid = cur.fetchone()[0]

        sig = (safe_lower(p["product_name"]), safe_lower(p["category"]), str(p["price"]))
        sig_to_id[sig] = pid

        if p["raw_product_id"]:
            raw_to_id[p["raw_product_id"]] = pid

        loaded += 1

    conn.commit()
    cur.close()
    return sig_to_id, raw_to_id, loaded

def load_orders_and_items(conn, sales_rows, raw_customer_map, raw_product_map):
    """
    Each sales row becomes:
      - 1 order
      - 1 order_item
    Returns counts loaded and counts dropped due to missing FK mapping.
    """
    cur = conn.cursor()

    orders_loaded = 0
    items_loaded = 0
    dropped_fk = 0

    insert_order_sql = """
        INSERT INTO orders (customer_id, order_date, total_amount, status)
        VALUES (%s, %s, %s, %s)
    """
    insert_item_sql = """
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
        VALUES (%s, %s, %s, %s, %s)
    """

    for s in sales_rows:
        cust_id = raw_customer_map.get(s["raw_customer_id"])
        prod_id = raw_product_map.get(s["raw_product_id"])

        if not cust_id or not prod_id:
            dropped_fk += 1
            continue

        subtotal = (Decimal(s["quantity"]) * s["unit_price"]).quantize(Decimal("0.01"))
        total_amount = subtotal

        # insert order
        cur.execute(insert_order_sql, (cust_id, s["order_date"], total_amount, s["status"]))
        order_id = cur.lastrowid
        orders_loaded += 1

        # insert item
        cur.execute(insert_item_sql, (order_id, prod_id, s["quantity"], s["unit_price"], subtotal))
        items_loaded += 1

    conn.commit()
    cur.close()

    return orders_loaded, items_loaded, dropped_fk


# ---------------------------
# Report writer
# ---------------------------

def write_report(path, sections: dict):
    lines = []
    lines.append("DATA QUALITY REPORT - fleximart ETL")
    lines.append(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("-" * 60)

    for name, stats in sections.items():
        lines.append(f"\n[{name}]")
        for k, v in stats.items():
            lines.append(f"{k}: {v}")

    lines.append("\n" + "-" * 60)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------
# Main
# ---------------------------

def main():
    customers_path = "customers_raw.csv"
    products_path = "products_raw.csv"
    sales_path = "sales_raw.csv"

    if not (os.path.exists(customers_path) and os.path.exists(products_path) and os.path.exists(sales_path)):
        logging.error("CSV files not found in current directory. Expected:")
        logging.error(" - customers_raw.csv")
        logging.error(" - products_raw.csv")
        logging.error(" - sales_raw.csv")
        sys.exit(1)

    # Extract
    logging.info("EXTRACT: Reading CSV files...")
    raw_customers = read_csv_dicts(customers_path)
    raw_products = read_csv_dicts(products_path)
    raw_sales = read_csv_dicts(sales_path)

    # Transform
    logging.info("TRANSFORM: Cleaning customers...")
    customers_clean, customers_rep = transform_customers(raw_customers)

    logging.info("TRANSFORM: Cleaning products...")
    products_clean, products_rep = transform_products(raw_products)

    logging.info("TRANSFORM: Cleaning sales...")
    sales_clean, sales_rep = transform_sales(raw_sales)

    # Load
    load_rep = {
        "customers_loaded": 0,
        "products_loaded": 0,
        "orders_loaded": 0,
        "order_items_loaded": 0,
        "sales_dropped_unmapped_fk": 0,
    }

    try:
        conn = get_db_connection()
        logging.info("LOAD: Connected to MySQL.")

        # customers
        email_map, raw_customer_map, loaded_customers = load_customers(conn, customers_clean)
        load_rep["customers_loaded"] = loaded_customers

        # products
        sig_map, raw_product_map, loaded_products = load_products(conn, products_clean)
        load_rep["products_loaded"] = loaded_products

        # orders + items from sales
        orders_loaded, items_loaded, dropped_fk = load_orders_and_items(
            conn, sales_clean, raw_customer_map, raw_product_map
        )
        load_rep["orders_loaded"] = orders_loaded
        load_rep["order_items_loaded"] = items_loaded
        load_rep["sales_dropped_unmapped_fk"] = dropped_fk

        conn.close()
        logging.info("LOAD: Completed successfully.")

    except Error as e:
        logging.exception(f"MySQL error: {e}")
        sys.exit(2)
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        sys.exit(3)

    # Write report
    sections = {
        "customers_raw.csv": customers_rep,
        "products_raw.csv": products_rep,
        "sales_raw.csv": sales_rep,
        "load_summary": load_rep,
    }
    write_report("data_quality_report.txt", sections)
    logging.info("Generated data_quality_report.txt")


if __name__ == "__main__":
    main()
