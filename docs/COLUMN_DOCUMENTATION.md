# Enterprise Business Simulation Engine
## Column Documentation

> **Scope**: Only the *generated* columns are documented here.
> Original Amazon columns (Order ID, Date, SKU, Amount, etc.) are preserved unchanged.

---

## 1. Logistics Engine Columns

### `warehouse_zone`
| Field | Detail |
|---|---|
| **Business meaning** | Geographic delivery tier for last-mile logistics costing |
| **Formula** | State → Tier-1 (metro), Tier-2 (large city), Tier-3 (remote) via config mapping |
| **Assumptions** | Maharashtra, Karnataka, Delhi, Tamil Nadu, Telangana, Gujarat, West Bengal = Tier-1 |
| **Why generated** | Determines surcharge rates and SLA. Carriers use zone matrices; never exposed publicly |
| **Why absent in public data** | Zone contracts are negotiated confidentially with carriers |

### `estimated_shipping_distance`
| Field | Detail |
|---|---|
| **Business meaning** | Approximate kilometres from fulfilment centre to delivery address |
| **Formula** | `avg_distance(tier) × uniform_jitter(0.8, 1.2)` |
| **Assumptions** | Tier-1 avg 450 km, Tier-2 avg 850 km, Tier-3 avg 1400 km |
| **Why generated** | Distance drives shipping cost and estimated delivery time |
| **Why absent in public data** | Origin warehouse location is proprietary operational data |

### `courier_partner`
| Field | Detail |
|---|---|
| **Business meaning** | Which carrier delivered/attempted this shipment |
| **Formula** | Amazon fulfiled → [Amazon Logistics, Blue Dart] with 70/30 weight; Merchant → [Delhivery, Ekart, DTDC, Xpressbees] |
| **Assumptions** | Primary carrier gets 70% of volume; tier-1 uses more premium carriers |
| **Why generated** | Carrier selection affects cost, delay rates, and customer experience |
| **Why absent in public data** | Carrier contracts and preferred partner agreements are commercial secrets |

### `shipping_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Total INR cost of dispatching this order |
| **Formula** | `weight_kg(category) × qty × rate_per_kg(fulfilment) × (1 + tier_surcharge_pct)` |
| **Assumptions** | Category weights from config (0.15–0.60 kg). FBA rate ₹55/kg, merchant ₹70/kg |
| **Why generated** | Shipping is a major post-gross cost; essential for contribution margin |
| **Why absent in public data** | Actual shipper invoices are confidential; marketplaces don't expose seller costs |

### `fuel_surcharge`
| Field | Detail |
|---|---|
| **Business meaning** | Variable fuel levy added to base shipping cost |
| **Formula** | `shipping_cost × 0.06` (6% rate from config) |
| **Why absent in public data** | Surcharge rates fluctuate monthly; part of carrier invoicing only |

### `shipping_insurance`
| Field | Detail |
|---|---|
| **Business meaning** | INR premium to insure the order value in transit |
| **Formula** | `Amount × 0.005` (0.5% of order value) |
| **Why absent in public data** | Insurance coverage decisions are at seller discretion |

### `expected_delivery_days`
| Field | Detail |
|---|---|
| **Business meaning** | Number of days from dispatch to expected delivery |
| **Formula** | Tier-1: 3 days, Tier-2: 5 days, Tier-3: 8 days; Expedited service -1 day |
| **Why absent in public data** | Internal SLA data; not in transaction exports |

### `delay_probability`
| Field | Detail |
|---|---|
| **Business meaning** | Probability (0–1) that this order will be delivered late |
| **Formula** | `base_delay(tier) + qty_factor(0.02/unit) + courier_penalty(0.05 for 3PL)` |
| **Assumptions** | Tier-1 base 5%, Tier-3 base 20%; Amazon Logistics is more reliable |
| **Why absent in public data** | Carrier reliability data is internal and changes seasonally |

---

## 2. Customer Engine Columns

### `customer_id`
| Field | Detail |
|---|---|
| **Business meaning** | Opaque identifier linking orders to the same buyer |
| **Formula** | `SHA1(city + state + style_prefix + b2b_salt + cluster_counter)[:10]` |
| **Assumptions** | Same city+style+segment cluster = ~20% chance of repeat buyer; B2B repeats more often |
| **Why generated** | Essential for CLV, retention, and segmentation analysis |
| **Why absent in public data** | Customer PII / identity is never shared in marketplace transaction exports |

### `customer_segment`
| Field | Detail |
|---|---|
| **Business meaning** | RFM-style tier: Champion / Loyal / Potential_Loyal / At_Risk |
| **Formula** | Based on order frequency per customer_id: ≥5 → Champion, ≥3 → Loyal, ≥2 → Potential, else At_Risk |
| **Why absent in public data** | CRM segmentation is a core retention IP |

### `repeat_customer_flag`
| Field | Detail |
|---|---|
| **Business meaning** | 1 if this customer_id appears more than once in the dataset |
| **Formula** | `1 if order_count(customer_id) > 1 else 0` |

### `loyalty_score`
| Field | Detail |
|---|---|
| **Business meaning** | Composite 0–100 score representing customer engagement |
| **Formula** | `40×repeat_flag + 30×(freq/max_freq) + 20×(order_value/max_value) + 10×promo_flag` |
| **Why absent in public data** | Loyalty scoring models are proprietary marketing IP |

### `acquisition_channel`
| Field | Detail |
|---|---|
| **Business meaning** | How the customer discovered and purchased the product |
| **Formula** | Inferred from: PLCC promo → Credit_Card_Offer; other promo → Promotional_Campaign; Amazon FBA no promo → Organic_Search; B2B → Enterprise_Sales |
| **Why absent in public data** | Attribution data requires integration of ad platform data with transaction data |

### `estimated_clv`
| Field | Detail |
|---|---|
| **Business meaning** | Estimated Customer Lifetime Value in INR |
| **Formula** | `avg_order_value × order_frequency × clv_multiplier(segment)` |
| **Assumptions** | Multipliers: Champion 4.5×, Loyal 3.0×, Potential 2.0×, At_Risk 1.2× |
| **Why absent in public data** | CLV models require long-term purchase history and are closely guarded |

### `estimated_cac`
| Field | Detail |
|---|---|
| **Business meaning** | Customer Acquisition Cost — how much was spent to acquire this customer |
| **Formula** | `base_cac(B2B=₹320, B2C=₹180) × (1 + promo_uplift×0.25) × (1 + new_customer_premium×0.30)` |
| **Why absent in public data** | CAC requires marketing spend attribution across campaigns |

---

## 3. Inventory Engine Columns

### `safety_stock`
| Field | Detail |
|---|---|
| **Business meaning** | Buffer inventory units held to prevent stockouts |
| **Formula** | `Z × σ_daily_demand × √lead_time` where Z=1.65 (95% service level) |
| **Why absent in public data** | Reorder policies are proprietary supply chain strategy |

### `reorder_point`
| Field | Detail |
|---|---|
| **Business meaning** | Stock level at which a purchase order must be placed |
| **Formula** | `daily_demand × lead_time_days + safety_stock` |

### `reorder_quantity`
| Field | Detail |
|---|---|
| **Business meaning** | How many units to order when reorder point is reached |
| **Formula** | `daily_demand × reorder_days_supply` (30-day supply) |

### `inventory_available`
| Field | Detail |
|---|---|
| **Business meaning** | Estimated units on-hand at the time of each order |
| **Formula** | `starting_stock - cumulative_units_sold + periodic_replenishment` |
| **Why absent in public data** | Real-time inventory positions are operational secrets |

### `inventory_age_days`
| Field | Detail |
|---|---|
| **Business meaning** | How long this SKU's stock has been sitting in the warehouse |
| **Formula** | `days_since_first_sale / (daily_demand × 5)` — slower SKUs age faster |

### `inventory_turnover`
| Field | Detail |
|---|---|
| **Business meaning** | Times the full inventory is sold and replenished per year (annualised) |
| **Formula** | `(total_units_sold / avg_inventory) × (365 / dataset_days)` |

### `dead_stock_flag`
| Field | Detail |
|---|---|
| **Business meaning** | 1 if this SKU is at serious risk of never selling |
| **Formula** | `inventory_age_days > 90 AND daily_demand < 0.5` |

### `stockout_probability`
| Field | Detail |
|---|---|
| **Business meaning** | Probability of running out of stock in the next 7 days |
| **Formula** | `1 - Φ(inventory_available; μ=7×daily_demand, σ=√7×σ_daily)` (normal CDF survival function) |
| **Why absent in public data** | Stockout risk is a key buying team metric; never shared externally |

---

## 4. Returns Engine Columns

### `return_probability`
| Field | Detail |
|---|---|
| **Business meaning** | Probability (0–1) that this order will result in a return |
| **Formula** | `base_rate(category) + promo_uplift(+4%) - b2b_discount(-5%) + high_value_risk(+2%) + repeat_customer(+3%) - amazon_fulfilled(-2%)` |
| **Why absent in public data** | Return rates by SKU are product quality signals; kept confidential |

### `return_reason`
| Field | Detail |
|---|---|
| **Business meaning** | Most probable reason customer returned the item |
| **Formula** | Weighted random from category-specific reason list: size_mismatch (55%), color_mismatch (30%), change_of_mind (15%) etc. |
| **Why absent in public data** | Return reason codes are from internal CRM; not in marketplace exports |

### `refund_amount`
| Field | Detail |
|---|---|
| **Business meaning** | INR refunded to the customer |
| **Formula** | Returned orders: full Amount. Probabilistic: `return_probability × Amount` |

### `refurbishment_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Cost to inspect, clean, and repackage returned items for resale |
| **Formula** | `refund_amount × 0.12` (12% of item value) |
| **Why absent in public data** | Post-return processing costs are internal operational expenses |

### `disposal_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Cost to dispose of items that cannot be resold (dead stock) |
| **Formula** | `COGS × 0.04` for dead-stock SKUs |

### `refund_processing_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Administrative cost of processing the refund transaction |
| **Formula** | `refund_amount × 0.02` |

---

## 5. Marketing Engine Columns

### `campaign_name` / `campaign_type`
| Field | Detail |
|---|---|
| **Business meaning** | Internal campaign identifier and type |
| **Formula** | Inferred from promotion-ids: PLCC → Amazon_PLCC_Financing; others → Seasonal/Flash/Loyalty; empty → Organic |
| **Why absent in public data** | Campaign metadata is in ad platform systems; not in order exports |

### `discount_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Revenue foregone due to promotional discounting |
| **Formula** | `Amount × promo_margin_impact(6%)` for orders with promotions |

### `attributed_revenue`
| Field | Detail |
|---|---|
| **Business meaning** | Incremental revenue that would not have occurred without the campaign |
| **Formula** | `Amount × 0.40` for promo orders (40% incrementality assumption) |

### `marketing_attribution_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Per-order share of the campaign's marketing spend |
| **Formula** | `base_cac × campaign_type_factor` (PLCC 40%, Flash Sale 80%, Seasonal 65%, Loyalty 50%) |

### `campaign_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Total marketing investment for this order |
| **Formula** | `marketing_attribution_cost + discount_cost` |

### `campaign_roi`
| Field | Detail |
|---|---|
| **Business meaning** | Return on marketing investment |
| **Formula** | `attributed_revenue / campaign_cost` |
| **Why absent in public data** | ROI requires linking ad spend data to transaction records |

---

## 6. Product Engine Columns

### `lifecycle_stage`
| Field | Detail |
|---|---|
| **Business meaning** | Where the SKU is in its product lifecycle |
| **Formula** | Based on days since first sale: ≤30 → Introduction, ≤90 → Growth, ≤180 → Maturity, >180 → Decline |
| **Why absent in public data** | Lifecycle classification requires full sales history |

### `velocity_class`
| Field | Detail |
|---|---|
| **Business meaning** | How fast this SKU sells relative to others |
| **Formula** | `daily_demand ≥ 3 → Fast, ≥ 0.5 → Medium, else Slow` |

### `abc_class`
| Field | Detail |
|---|---|
| **Business meaning** | Pareto classification of SKUs by revenue contribution |
| **Formula** | A = top SKUs driving 70% of revenue; B = next 20%; C = remaining 10% |
| **Why absent in public data** | ABC matrix is the core buying/merchandising strategy tool |

### `xyz_class`
| Field | Detail |
|---|---|
| **Business meaning** | Demand predictability classification |
| **Formula** | Coefficient of Variation of weekly sales: CV ≤ 0.30 → X, ≤ 0.60 → Y, else Z |

### `contribution_margin`
| Field | Detail |
|---|---|
| **Business meaning** | Revenue minus all variable costs (INR per order) |
| **Formula** | `Revenue - COGS - Packaging - Shipping` |

### `product_profitability_score`
| Field | Detail |
|---|---|
| **Business meaning** | Composite 0–100 score of SKU's overall financial performance |
| **Formula** | `40×cm_normalised + 30×abc_score + 20×velocity_score + 10×lifecycle_score` |

### `dead_stock_score`
| Field | Detail |
|---|---|
| **Business meaning** | Risk score (0–100) for becoming dead / unsellable inventory |
| **Formula** | `velocity_risk(Slow=50) + abc_risk(C=30) + lifecycle_risk(Decline=20)` |

---

## 7. Finance Engine Columns

### `cogs`
| Field | Detail |
|---|---|
| **Business meaning** | Cost of Goods Sold — what the seller paid to source the product |
| **Formula** | `Revenue × (1 - gross_margin_pct(category))` |
| **Why absent in public data** | COGS is the most sensitive data a business holds; reveals supplier pricing |

### `gross_profit` / `gross_margin_pct`
| Field | Detail |
|---|---|
| **Business meaning** | Revenue minus COGS, and as a percentage |
| **Formula** | `gross_profit = Revenue - COGS; gross_margin_pct = gross_profit / Revenue × 100` |

### `warehouse_handling_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Pick, pack, and sort cost per unit dispatched from warehouse |
| **Formula** | `₹22 × qty` |

### `inventory_holding_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Monthly cost of storing inventory (opportunity + space cost) |
| **Formula** | `COGS × 1.5% × 1.5 months` |

### `platform_commission`
| Field | Detail |
|---|---|
| **Business meaning** | Amazon's referral/commission fee on this order |
| **Formula** | `Revenue × commission_rate(category)` — typically 11–13% for apparel |

### `payment_gateway_fee`
| Field | Detail |
|---|---|
| **Business meaning** | Processing fee for the payment transaction |
| **Formula** | `Revenue × 1.8%` |

### `reverse_logistics_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Cost of shipping a returned item back from customer to warehouse |
| **Formula** | `shipping_cost × 50%` for returned orders |

### `cancellation_cost`
| Field | Detail |
|---|---|
| **Business meaning** | Administrative cost of processing a cancelled order |
| **Formula** | Flat ₹15 per cancelled order |

### `net_profit`
| Field | Detail |
|---|---|
| **Business meaning** | Full-stack profit after every cost is deducted |
| **Formula** | `Revenue − COGS − Packaging − Shipping − Fuel − Insurance − Commission − Gateway − Marketing − Return Costs − Reverse Logistics − Warehouse Handling − Inventory Holding − Cancellation` |
| **Why absent in public data** | No marketplace or e-commerce player publishes per-order P&L |

### `profit_margin_pct`
| Field | Detail |
|---|---|
| **Business meaning** | Net profit as a percentage of revenue |
| **Formula** | `net_profit / Revenue × 100` |

### `profit_leakage`
| Field | Detail |
|---|---|
| **Business meaning** | Total cost erosion between gross profit and net profit |
| **Formula** | `gross_profit - net_profit` |
| **Why generated** | Profit leakage analysis reveals where to focus cost reduction efforts |
| **Why absent in public data** | Requires full operational cost data across logistics, returns, and marketing |
