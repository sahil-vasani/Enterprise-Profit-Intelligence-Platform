# SQL.md — PostgreSQL Data Warehouse Workflow

This document explains, in simple English, how the raw Amazon sales CSV (128,975 rows, 79 columns) was turned into a clean PostgreSQL data warehouse and connected to Power BI. It follows the exact steps that were run, in the exact order they were run.

---

## 1. Project Overview

The goal was to take one messy CSV file and turn it into a proper **enterprise data warehouse** — the same kind of structure real companies use — instead of connecting Power BI directly to a raw CSV.

The overall journey looked like this:

```
CSV
  ↓
Staging Table
  ↓
Validation
  ↓
Dimension Tables (Customer, Product, Date, Location, Marketing, Inventory, Returns)
  ↓
Fact Staging Table
  ↓
Final Fact Table (fact_sales)
  ↓
One Reporting View (vw_sales_reporting)
  ↓
Power BI
```

Every step was validated with row counts and checks before moving to the next one. This matters because in a real company, if you skip validation, a wrong number can silently end up on a dashboard that executives make decisions from.

---

## 2. What is ETL? (Simple Explanation)

**ETL** stands for **Extract, Transform, Load**. It's the standard process of moving data from a raw source into a place where it's clean and ready to use.

- **Extract** — take the data out of its original source. Here, that's the Amazon sales CSV file.
- **Transform** — clean it, fix its structure, remove duplicates, and organize it into a proper format.
- **Load** — put the final, clean data into tables that reports and dashboards can use directly.

In this project, ETL looked like: CSV → staging table (Extract + first Load) → dimension and fact tables (Transform) → reporting view (final Load, ready for Power BI). The whole point of ETL is that nobody should ever build a dashboard directly on messy raw data — there should always be a cleaning step in between.

---

## 3. Database and Schema Creation

Before creating any tables, a clean **schema** was created to hold all warehouse objects.

```sql
DROP SCHEMA IF EXISTS analytics CASCADE;
CREATE SCHEMA analytics;
```

A schema is like a labeled folder inside the database — it keeps all the warehouse tables (staging, dimensions, fact, views) grouped together and separate from anything else in the database. Starting with a `DROP SCHEMA` first made sure there were no leftover tables from an earlier, incorrect attempt at the warehouse.

Validation:
```sql
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name = 'analytics';
```
Expected result: `analytics` — confirming the schema exists before any table is built inside it.

---

## 4. Staging Table — Loading the Raw CSV

A **staging table** was created next, using the real column names from the CSV (like `"Order ID"`, `"Amount"`, `"cogs"`, `"gross_profit"`) instead of generic placeholders like `col1`, `col2`. It has all 79 columns, matching the CSV exactly:

```sql
CREATE TABLE analytics.stg_amazon_sales_raw (
    "index" INTEGER,
    "Order ID" TEXT,
    "Date" TEXT,
    "Status" TEXT,
    "Amount" NUMERIC(12,2),
    ...
    "cogs" NUMERIC(12,2),
    "gross_profit" NUMERIC(12,2),
    "net_profit" NUMERIC(12,2),
    "profit_leakage" NUMERIC(12,2)
);
```

A staging table exists purely as a landing zone — it holds the data in its raw, unprocessed form so nothing is transformed before it's confirmed to be loaded correctly. Using the real business column names (instead of `col1`, `col2`...) makes every later query far easier to read, debug, and explain in an interview.

Validation: confirming the table has exactly 79 columns before loading any data into it.
```sql
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema='analytics' AND table_name='stg_amazon_sales_raw';
-- Expected: 79
```

### Loading the CSV

```sql
COPY analytics.stg_amazon_sales_raw
FROM 'D:/Project/amazon_enterprise_dataset.csv'
DELIMITER ','
CSV HEADER
ENCODING 'UTF8';
```

`COPY` is PostgreSQL's fast bulk-loading command — it reads the CSV file directly from disk and inserts every row into the staging table in one operation, which is much faster than inserting rows one at a time.

Validation: `SELECT COUNT(*) FROM analytics.stg_amazon_sales_raw;` → expected and confirmed **128,975** rows.

---

## 5. Data Cleaning and Validation (Staging Layer)

Before building anything on top of the staging table, four quality checks were run:

| Check | Query Purpose | Result |
|---|---|---|
| Null Order IDs | Make sure no row is missing its order identifier | 0 ✅ |
| Null Amount | Make sure no row is missing its revenue value | 0 ✅ |
| Duplicate Orders | Compare total rows vs. unique Order IDs | 128,975 total / 120,378 unique — expected, since one order can contain multiple products |
| Date Range | Confirm dates loaded in a valid range | `03-31-2022` → `06-29-2022` ✅ |

This step matters because, in real ETL work, **you never build dimension tables on top of unvalidated data.** If a data quality issue exists in the staging table, it will silently spread into every dimension and fact table built afterward, and it's far harder to trace back once that happens.

---

## 6. Building the Dimension Tables

This is where the raw staging data was broken into separate, clean **dimension tables** — one table per real-world business entity (a customer, a product, a location, and so on).

A repeatable pattern was used for every dimension:
1. Remove duplicate records for that entity using `DISTINCT ON`.
2. Generate a new surrogate key using `ROW_NUMBER()`.
3. Add that key as the table's `PRIMARY KEY`.
4. Validate the row count makes sense (dimensions should be much smaller than the raw data).

### dim_date
```sql
CREATE TABLE analytics.dim_date AS
SELECT DISTINCT TO_DATE("Date", 'MM-DD-YY') AS full_date
FROM analytics.stg_amazon_sales_raw;

ALTER TABLE analytics.dim_date ADD COLUMN date_id SERIAL PRIMARY KEY;
ALTER TABLE analytics.dim_date
  ADD COLUMN day INT, ADD COLUMN month INT, ADD COLUMN month_name VARCHAR(20),
  ADD COLUMN quarter INT, ADD COLUMN year INT, ADD COLUMN day_name VARCHAR(20),
  ADD COLUMN week_of_year INT, ADD COLUMN is_weekend BOOLEAN;

UPDATE analytics.dim_date
SET day = EXTRACT(DAY FROM full_date),
    month = EXTRACT(MONTH FROM full_date),
    month_name = TO_CHAR(full_date,'Month'),
    quarter = EXTRACT(QUARTER FROM full_date),
    year = EXTRACT(YEAR FROM full_date),
    day_name = TO_CHAR(full_date,'Day'),
    week_of_year = EXTRACT(WEEK FROM full_date),
    is_weekend = CASE WHEN EXTRACT(ISODOW FROM full_date) IN (6,7) THEN TRUE ELSE FALSE END;
```
`dim_date` breaks every date into useful parts (day, month, quarter, weekend flag) so Power BI can filter and group by time without doing date math inside every chart. Result: **91 unique dates**.

### dim_customer — where a real bug was caught and fixed
The first version of this table used `DISTINCT` across all customer columns, which produced 128,975 rows instead of one row per customer — because a column called `loyalty_score` changes over time for the same customer, so PostgreSQL treated every change as a "different" customer.

The fix: only keep customer attributes that don't change per customer (segment, CLV), and for `loyalty_score`, keep just the latest value using `DISTINCT ON`:

```sql
CREATE TABLE analytics.dim_customer AS
SELECT
    ROW_NUMBER() OVER (ORDER BY customer_code) AS customer_id,
    customer_code, customer_segment, repeat_customer_flag,
    estimated_clv, loyalty_score
FROM (
    SELECT DISTINCT ON ("customer_id")
        "customer_id" AS customer_code, customer_segment,
        repeat_customer_flag, estimated_clv, loyalty_score
    FROM analytics.stg_amazon_sales_raw
    ORDER BY "customer_id", loyalty_score DESC
) t;

ALTER TABLE analytics.dim_customer ADD PRIMARY KEY (customer_id);
```
This is a simple version of a data warehouse concept called a **Slowly Changing Dimension (Type 1)** — when an attribute changes over time but you only need to keep the latest value, not the full history. Result: **29,671 unique customers** (down from 128,975 raw rows).

### dim_product
```sql
CREATE TABLE analytics.dim_product AS
SELECT ROW_NUMBER() OVER (ORDER BY sku) AS product_id,
       sku, style, asin, category, size
FROM (
    SELECT DISTINCT ON ("SKU")
        "SKU" AS sku, "Style" AS style, "ASIN" AS asin,
        "Category" AS category, "Size" AS size
    FROM analytics.stg_amazon_sales_raw
    ORDER BY "SKU"
) t;
ALTER TABLE analytics.dim_product ADD PRIMARY KEY (product_id);
```
One row per unique product variant (SKU + size). Result: **7,195 products**.

### dim_location
Same pattern, grouped by shipping city, state, and postal code. Result: **18,230 locations**.

### dim_marketing
Same pattern, grouped by campaign name and campaign type. Result: **3 campaigns**.

### dim_inventory
Same pattern, grouped by fulfillment method, warehouse zone, and courier partner. Result: **18 combinations**.

### dim_returns
Same pattern, grouped by return reason and courier status. Result: **24 combinations**.

**Why dimensions matter:** each dimension table stores one clean copy of a business entity's information. Instead of repeating "Mumbai, Maharashtra, 400081" 5,000 times across the raw data, it's stored once in `dim_location`, and every sale just points to it with a small number (a foreign key). This is what keeps the warehouse small, fast, and free of repeated/inconsistent data.

---

## 7. Fact Staging Table (fact_sales_stage)

This is the table that connects every dimension to every actual sale. Because joining 7 dimension tables at once against 128,975 rows was slow, it was built in three steps instead of one giant query:

**Step 1 — link the foreign keys only:**
```sql
CREATE TABLE analytics.fact_sales_stage AS
SELECT
    s."Order ID" AS order_id,
    c.customer_id, p.product_id, d.date_id,
    l.location_id, m.marketing_id, i.inventory_id, r.return_id
FROM analytics.stg_amazon_sales_raw s
JOIN analytics.dim_customer c ON s."customer_id" = c.customer_code
JOIN analytics.dim_product p ON s."SKU" = p.sku
JOIN analytics.dim_date d ON TO_DATE(s."Date",'MM-DD-YY') = d.full_date
JOIN analytics.dim_location l ON ... 
JOIN analytics.dim_marketing m ON ...
JOIN analytics.dim_inventory i ON ...
JOIN analytics.dim_returns r ON ...;
```

**Step 2 — add empty columns for the business numbers** (revenue, cogs, gross_profit, net_profit, discount, shipping_cost, and so on).

**Step 3 — fill those numbers in with a fast `UPDATE`** matched by `order_id`, instead of redoing all 7 joins again.

Splitting it into three steps this way is a real enterprise ETL technique: it's easier to debug (you can check the joins worked before adding numbers), and it runs faster than one giant multi-join query.

**Validation performed:**
- Row count still matches: 128,975 ✅
- All key business measures (`cogs`, `gross_profit`, `net_profit`, `discount`, `delay_probability`) are 100% filled — no missing values ✅
- Total Revenue: 78,598,985.21 | Total COGS: 39,440,615.88 | Total Gross Profit: 39,158,369.33 | Total Net Profit: **-2,158,539.66**

A negative overall net profit is not a mistake — it reflects real costs in the data (marketing spend, platform commission, shipping, refunds, reverse logistics) that can legitimately outweigh gross profit.

**Duplicate order check:** 128,975 total rows but only 120,378 unique Order IDs (8,597 "duplicates"). This was confirmed to be correct, not an error — one order can contain multiple products (a shirt, pants, and shoes in a single order becomes 3 separate rows). This means the fact table's **grain** (what one row represents) is one *order line item*, not one *order*. Getting the grain right is one of the most important decisions in building any fact table.

---

## 8. Final Fact Table (fact_sales)

Once the staging version was validated, the real fact table was built with a proper primary key and enforced relationships to every dimension:

```sql
CREATE TABLE analytics.fact_sales (
    sales_id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(50),
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    date_id INT NOT NULL,
    location_id BIGINT NOT NULL,
    marketing_id BIGINT NOT NULL,
    inventory_id BIGINT NOT NULL,
    return_id BIGINT NOT NULL,
    quantity INT,
    revenue NUMERIC(15,2), cogs NUMERIC(15,2),
    gross_profit NUMERIC(15,2), net_profit NUMERIC(15,2),
    discount NUMERIC(15,2), shipping_cost NUMERIC(15,2),
    marketing_cost NUMERIC(15,2), platform_fee NUMERIC(15,2),
    inventory_cost NUMERIC(15,2), profit_leakage NUMERIC(15,2),
    profit_margin NUMERIC(15,2), return_probability NUMERIC(15,2),
    delay_probability NUMERIC(15,2), refund_amount NUMERIC(15,2),
    reverse_shipping_cost NUMERIC(15,2), campaign_roi NUMERIC(15,2)
);

INSERT INTO analytics.fact_sales (...)
SELECT ... FROM analytics.fact_sales_stage;

ALTER TABLE analytics.fact_sales ADD CONSTRAINT fk_customer
  FOREIGN KEY (customer_id) REFERENCES analytics.dim_customer(customer_id);
-- (same pattern repeated for product, date, location, marketing, inventory, returns)
```

Adding `FOREIGN KEY` constraints for every dimension does two things: it guarantees every sale record always points to a real, existing customer/product/date/etc. (no broken links), and it documents the relationships directly in the database so anyone opening it later can see how the tables connect.

Validation: `SELECT COUNT(*) FROM analytics.fact_sales;` → expected and confirmed **128,975** rows.

This completed the **star schema** — one central fact table surrounded by dimension tables:

```
                  dim_customer
                       │
   dim_product ───── fact_sales ───── dim_date
                       │
             dim_location · dim_marketing
             dim_inventory · dim_returns
```

---

## 9. Why a Star Schema?

A **star schema** is a way of organizing a data warehouse where one central **fact table** (the sales transactions) is connected to several small **dimension tables** (customer, product, date, location, etc.) — drawn out, it looks like a star, with the fact table in the middle.

It's used instead of one giant flat table for three simple reasons:
1. **No repeated data** — a customer's details are stored once in `dim_customer`, not repeated on every single sale row.
2. **Faster and simpler for BI tools** — Power BI is built to work with exactly this shape: one fact table plus lookup dimensions, so filters and relationships work automatically.
3. **Easier to understand and maintain** — anyone looking at the warehouse can immediately tell what a "sale" is and what information describes it, instead of hunting through 79 mixed-up raw columns.

---

## 10. Performance Improvements — Indexes

Because joining 7 dimension tables against a 128,975-row staging table was slow, indexes were recommended on the join columns to speed things up:

```sql
CREATE INDEX idx_stg_customer ON analytics.stg_amazon_sales_raw("customer_id");
CREATE INDEX idx_stg_sku ON analytics.stg_amazon_sales_raw("SKU");
CREATE INDEX idx_stg_date ON analytics.stg_amazon_sales_raw("Date");
CREATE INDEX idx_stg_order ON analytics.stg_amazon_sales_raw("Order ID");
```

An index works like a book's index page — instead of PostgreSQL scanning every one of the 128,975 rows to find matching customers or SKUs during a join, it can jump straight to the right rows, which makes both the initial build and any future data refresh much faster.

---

## 11. Reporting View — The Single Source of Truth

The original plan was to build 7 separate summary views (one for sales, one for customers, one for products, and so on). That approach was changed in favor of **one single reporting view** that joins the fact table with every dimension at once:

```sql
CREATE VIEW analytics.vw_sales_reporting AS
SELECT
    f.sales_id, f.order_id, f.quantity, f.revenue, f.cogs,
    f.gross_profit, f.net_profit, f.discount, f.shipping_cost,
    f.marketing_cost, f.inventory_cost, f.platform_fee,
    f.profit_leakage, f.profit_margin, f.return_probability,
    f.delay_probability, f.refund_amount, f.reverse_shipping_cost,
    f.campaign_roi,
    d.full_date, d.day, d.month, d.month_name, d.quarter, d.year,
    d.day_name, d.week_of_year, d.is_weekend,
    c.customer_code, c.customer_segment, c.repeat_customer_flag,
    c.loyalty_score, c.estimated_clv,
    p.sku, p.style, p.category, p.size,
    l.ship_city, l.ship_state, l.ship_postal_code, l.ship_country, l.warehouse_zone,
    m.campaign_name, m.campaign_type, m.acquisition_channel, m.campaign_cost,
    i.fulfilled_by, i.courier_partner,
    r.return_reason, r.courier_status
FROM analytics.fact_sales f
JOIN analytics.dim_date d ON f.date_id = d.date_id
JOIN analytics.dim_customer c ON f.customer_id = c.customer_id
JOIN analytics.dim_product p ON f.product_id = p.product_id
JOIN analytics.dim_location l ON f.location_id = l.location_id
JOIN analytics.dim_marketing m ON f.marketing_id = m.marketing_id
JOIN analytics.dim_inventory i ON f.inventory_id = i.inventory_id
JOIN analytics.dim_returns r ON f.return_id = r.return_id;
```

A single reporting view is the **single source of truth** for every dashboard: instead of Power BI having to join 8 tables together every time it refreshes, it connects to one already-joined, ready-to-use view. This keeps the Power BI data model simple (no relationships to configure inside Power BI itself) and makes the whole system easier to maintain — if a column needs to change, it only needs to change in one place.

Validation: `SELECT COUNT(*) FROM analytics.vw_sales_reporting;` → confirmed **128,975** rows, matching the fact table exactly.

---

## 12. Final Power BI Connection

With the warehouse and reporting view complete, Power BI was connected as the very last step — no more SQL was written after this point.

1. In Power BI Desktop: **Home → Get Data → PostgreSQL database**
2. Server: `localhost`, Database: `enterprise_profit_intelligence`
3. Connectivity mode: **Import**
4. Enter PostgreSQL username and password → Connect
5. In the Navigator window, select **only** `analytics.vw_sales_reporting` — no other tables
6. Click **Load** and wait for it to finish

Because only one already-joined view was loaded, there was nothing left to configure in Power BI's Model view — no relationships, no cardinality settings, no cross-filter directions. The model was ready for building dashboards and DAX measures immediately after loading.

---

## 13. Summary — What Was Built

| Layer | Object | Row Count |
|---|---|---|
| Staging | `stg_amazon_sales_raw` | 128,975 |
| Dimension | `dim_date` | 91 |
| Dimension | `dim_customer` | 29,671 |
| Dimension | `dim_product` | 7,195 |
| Dimension | `dim_location` | 18,230 |
| Dimension | `dim_marketing` | 3 |
| Dimension | `dim_inventory` | 18 |
| Dimension | `dim_returns` | 24 |
| Fact (staging) | `fact_sales_stage` | 128,975 |
| Fact (final) | `fact_sales` | 128,975 |
| Reporting | `vw_sales_reporting` | 128,975 |

This is a complete, validated ETL pipeline: raw CSV → staging → cleaned dimensions → fact table with enforced foreign keys → one reporting view → Power BI. Every stage was checked with row counts and data quality queries before moving to the next one, which is exactly how a production data warehouse is built.
