# star_schema_design.md

## Section 1: Schema Overview

### FACT TABLE: `fact_sales`
**Grain:** One row per product per order line item (i.e., each line item in an order becomes one fact row).  
**Business Process:** Sales transactions (customer purchases of products on a specific date).

**Measures (Numeric Facts):**
- **quantity_sold:** Number of units sold in the line item.
- **unit_price:** Price per unit at the time of sale (stored in the fact table so historical pricing analysis is possible).
- **discount_amount:** Discount applied to the line item (absolute currency amount).
- **total_amount:** Final net amount for the line item:
  - `total_amount = (quantity_sold × unit_price) - discount_amount`

**Foreign Keys (Dimensions Linked):**
- **date_key → dim_date(date_key)**
- **product_key → dim_product(product_key)**
- **customer_key → dim_customer(customer_key)**

**Why these fields live in the fact:**
- Measures are additive (or semi-additive) and designed for aggregation (SUM/AVG) across time, product, and customer dimensions.
- Storing `unit_price` and `discount_amount` in the fact table enables “as-sold” revenue reporting and discount analysis without being impacted by later product price changes.

---

### DIMENSION TABLE: `dim_date`
**Purpose:** Provides a rich time axis for reporting, drill-down, roll-up, and time-series analysis.  
**Type:** Conformed dimension (can be reused across multiple fact tables in a larger warehouse).

**Attributes:**
- **date_key (PK):** Surrogate key, integer in `YYYYMMDD` format (e.g., 20240115).
- **full_date:** Actual calendar date (DATE type).
- **day_of_week:** Monday, Tuesday, etc.
- **day_of_month:** 1–31
- **month:** 1–12
- **month_name:** January, February, etc.
- **quarter:** Q1, Q2, Q3, Q4
- **year:** 2023, 2024, etc.
- **is_weekend:** Boolean (TRUE for Saturday/Sunday, else FALSE)

**Common analytics enabled:**
- Monthly/quarterly/yearly sales trends
- Weekend vs weekday performance
- Day-of-week demand patterns

---

### DIMENSION TABLE: `dim_product`
**Purpose:** Describes products and supports slicing sales by product attributes like category and subcategory.  
**Type:** Descriptive dimension (often used for product hierarchy roll-ups).

**Attributes:**
- **product_key (PK):** Surrogate key (AUTO_INCREMENT).
- **product_id:** Natural/business key from the source system (e.g., P001).
- **product_name:** Human-readable name.
- **category:** High-level grouping (e.g., Electronics).
- **subcategory:** Lower-level grouping (e.g., Computers, Audio).
- **unit_price:** Current/reference price in the dimension (useful for browsing and basic checks; “as-sold” price remains in `fact_sales.unit_price`).

**Product hierarchy example (roll-up path):**
`product_name → subcategory → category`

---

### DIMENSION TABLE: `dim_customer`
**Purpose:** Describes customers and supports segmentation, geography analysis, and customer-level roll-ups.  
**Type:** Descriptive dimension (used heavily for marketing and customer analytics).

**Attributes:**
- **customer_key (PK):** Surrogate key (AUTO_INCREMENT).
- **customer_id:** Natural/business key from source (e.g., C001).
- **customer_name:** Customer name.
- **city:** Customer city.
- **state:** Customer state.
- **customer_segment:** Segment label (e.g., Consumer, Corporate, Home Office)

**Common analytics enabled:**
- City/state sales distribution
- Segment-based revenue analysis
- High-value customer identification and retention targeting

---

## Section 2: Design Decisions (approx. 150 words)

This star schema uses **transaction line-item granularity** because it preserves the most detail for analytics: every product in every order is recorded, enabling accurate revenue, discount, and quantity analysis at the lowest level. From this grain, reporting can roll up cleanly to daily/monthly totals, product category totals, or customer segments without losing detail. **Surrogate keys** are used for `product_key` and `customer_key` because natural keys (like `product_id` and `customer_id`) can change, vary across systems, or contain business meaning that complicates joins and history handling. Surrogate keys keep joins fast, stable, and consistent, and they support future enhancements like Slowly Changing Dimensions (SCD) if product categories or customer segments evolve. The dimensional attributes in `dim_date`, `dim_product`, and `dim_customer` enable **drill-down** (e.g., Category → Subcategory → Product) and **roll-up** (e.g., Day → Month → Quarter → Year) using standard GROUP BY operations.

---

## Section 3: Sample Data Flow

### Source Transaction
Order #101, Customer "John Doe", Product "Laptop", Qty: 2, Price: 50000

### Becomes in Data Warehouse

**fact_sales**
```json
{
  "date_key": 20240115,
  "product_key": 5,
  "customer_key": 12,
  "quantity_sold": 2,
  "unit_price": 50000,
  "discount_amount": 0,
  "total_amount": 100000
}
