# schema_documentation.md

## 1) Entity–Relationship Description (Text Format)

### ENTITY: customers  
**Purpose:** Stores customer master data (one row per customer).  
**Attributes:**  
- **customer_sk**: Surrogate key (Primary Key, auto-increment)  
- **customer_id**: Business identifier (Unique; e.g., C001)  
- **first_name**: Customer’s first name  
- **last_name**: Customer’s last name  
- **email**: Customer email (nullable if missing in source)  
- **phone**: Standardized phone (e.g., +91-9876543210)  
- **city**: Customer city (trimmed, standardized casing)  
- **registration_date**: Date customer registered (YYYY-MM-DD)  
- **created_at**: ETL load timestamp  
- **updated_at**: Last update timestamp  

**Relationships:**  
- One **customer** can place **many orders** (1:M with `orders`).

---

### ENTITY: products  
**Purpose:** Stores product master data (one row per product).  
**Attributes:**  
- **product_sk**: Surrogate key (Primary Key, auto-increment)  
- **product_id**: Business identifier (Unique; e.g., P001)  
- **product_name**: Name of product  
- **category**: Standardized category (Electronics/Fashion/Groceries)  
- **price**: Current product price (nullable if missing in source)  
- **stock_quantity**: Current stock (default 0 if missing)  
- **created_at**: ETL load timestamp  
- **updated_at**: Last update timestamp  

**Relationships:**  
- One **product** can appear in **many order_items** (1:M with `order_items`).

---

### ENTITY: orders  
**Purpose:** Stores one order per transaction header (customer + date + status).  
**Attributes:**  
- **order_sk**: Surrogate key (Primary Key, auto-increment)  
- **transaction_id**: Business transaction id (Unique; e.g., T001)  
- **customer_sk**: Foreign Key → `customers.customer_sk` (nullable if missing customer_id in source)  
- **order_date**: Transaction date (YYYY-MM-DD)  
- **status**: Completed / Pending / Cancelled  
- **created_at**: ETL load timestamp  

**Relationships:**  
- One **order** has **many order_items** (1:M with `order_items`).  
- Many **orders** belong to one **customer** (M:1 with `customers`).

---

### ENTITY: order_items  
**Purpose:** Stores line-items for each order (product + quantity + unit_price).  
**Attributes:**  
- **order_item_sk**: Surrogate key (Primary Key, auto-increment)  
- **order_sk**: Foreign Key → `orders.order_sk`  
- **product_sk**: Foreign Key → `products.product_sk` (nullable if missing product_id in source)  
- **quantity**: Units purchased  
- **unit_price**: Price per unit captured at transaction time  

**Relationships:**  
- Many **order_items** belong to one **order** (M:1 with `orders`).  
- Many **order_items** reference one **product** (M:1 with `products`).

---

## 2) Normalization Explanation (3NF) — 200–250 words

This design satisfies **Third Normal Form (3NF)** by separating customer, product, order header, and order line-item data so every non-key attribute depends only on the key, the whole key, and nothing but the key. Key functional dependencies include:  
- `customer_id → {first_name, last_name, email, phone, city, registration_date}`  
- `product_id → {product_name, category, price, stock_quantity}`  
- `transaction_id → {customer_sk, order_date, status}`  
- `{order_sk, product_sk} → {quantity, unit_price}` (or `order_item_sk → {order_sk, product_sk, quantity, unit_price}`)

No table contains attributes that depend on another non-key attribute (no transitive dependencies). For example, customer contact fields are stored only in `customers`, not repeated in orders; product category/price lives in `products`, not duplicated in sales rows. This prevents **update anomalies** (changing a customer’s phone requires updating exactly one row), **insert anomalies** (a product can be inserted without needing a sale), and **delete anomalies** (deleting an order does not delete the customer or product master records). Capturing `unit_price` at `order_items` also preserves historical pricing without overwriting `products.price`, avoiding inconsistent reporting. Overall, the schema cleanly models entities and relationships with minimal redundancy and stable referential integrity.

---

## 3) Sample Data Representation (2–3 records each)

### customers (sample)
| customer_sk | customer_id | first_name | last_name | email                   | phone           | city       | registration_date |
|------------:|------------|------------|-----------|-------------------------|----------------|-----------|------------------|
| 1           | C001       | Rahul      | Sharma    | rahul.sharma@gmail.com  | +91-9876543210 | Bangalore | 2023-01-15       |
| 2           | C002       | Priya      | Patel     | priya.patel@yahoo.com   | +91-9988776655 | Mumbai    | 2023-02-20       |
| 3           | C003       | Amit       | Kumar     | NULL                    | +91-9765432109 | Delhi     | 2023-03-10       |

### products (sample)
| product_sk | product_id | product_name          | category     | price     | stock_quantity |
|-----------:|-----------|-----------------------|--------------|----------:|---------------:|
| 1          | P001      | Samsung Galaxy S21    | Electronics  | 45999.00  | 150            |
| 2          | P002      | Nike Running Shoes    | Fashion      | 3499.00   | 80             |
| 3          | P006      | Organic Almonds       | Groceries    | 899.00    | 0              |

### orders (sample)
| order_sk | transaction_id | customer_sk | order_date  | status     |
|---------:|----------------|------------:|------------|------------|
| 1        | T001           | 1           | 2024-01-15 | Completed  |
| 2        | T004           | NULL        | 2024-01-18 | Pending    |
| 3        | T009           | 9           | 2024-01-28 | Cancelled  |

### order_items (sample)
| order_item_sk | order_sk | product_sk | quantity | unit_price |
|--------------:|---------:|-----------:|---------:|-----------:|
| 1             | 1        | 1          | 1        | 45999.00   |
| 2             | 2        | 2          | 1        | 3499.00    |
| 3             | 3        | 11         | 1        | 4599.00    |
