# Formulas, Definitions, and the Business Problem Each One Solves

This document explains every metric this repo computes in plain language:
what it means, the formula behind it, and — most importantly — **what
business decision it's for**. It's organized by module. For step-by-step
computational walkthroughs with worked numeric examples, see
[`COLUMN_DEFINITIONS.md`](COLUMN_DEFINITIONS.md) (inventory planning) and
the module docstrings in `src/*.py`.

## Contents

1. [Inventory planning — `src/inventory_planning.py`](#1-inventory-planning)
2. [Policy backtest — `src/policy_simulation.py`](#2-policy-backtest)
3. [Advanced analytics — `src/advanced_analytics.py`](#3-advanced-analytics)
4. [Customer lifetime value — `src/customer_ltv_segmentation.py`](#4-customer-lifetime-value)
5. [Market basket analysis — `src/market_basket_analysis.py`](#5-market-basket-analysis)
6. [Supplier segmentation — `src/supplier_segmentation.py`](#6-supplier-segmentation)
7. [Weekly retail KPIs — `src/retail_kpi_metrics.py`](#7-weekly-retail-kpis)
8. [Assortment planning — `src/assortment_planning.py`](#8-assortment-planning)
9. [Trade-area modelling — `src/trade_area_modelling.py`](#9-trade-area-modelling)
10. [Hybrid SKU forecasting — `src/hybrid_forecasting.py`](#10-hybrid-sku-forecasting)

---

## 1. Inventory planning

**The business problem:** two of the most expensive mistakes in retail are
*stocking out* (a customer wants to buy something you don't have — lost
sale, sometimes a lost customer) and *overstocking* (cash tied up in
shelves of product that isn't moving, plus storage cost and markdown risk
if it never sells). Both come from the same root question, asked
per-product: **how much should I keep on hand, and when should I reorder?**

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Average daily demand** | mean of units sold per day | How fast a product normally sells | The baseline every other number below is built on |
| **Demand variability (`sd`)** | standard deviation of daily units sold | How *unpredictable* that demand is, day to day | A steady seller needs far less buffer stock than a spiky one with the same average — this is why average alone is a bad basis for stocking decisions |
| **ABC classification (`product_mix`)** | rank products by volume and by revenue, bucket each into the top 80% / next 15% / bottom 5% (Pareto rule) | Which products matter most, by two different measures at once | Focuses inventory attention (and safety stock spend) on the ~20% of products that drive ~80% of sales/revenue, instead of treating every SKU identically |
| **Target service level** | a % probability, set per ABC class (e.g. 95% for top-tier `A_A` products, 70% for long-tail `C_C`) | How often you're willing to risk running out before the next delivery | Lets the business make an explicit trade-off: guarantee availability on the products that matter most, accept more stockout risk on the ones that don't, rather than guessing one number for everything |
| **Reorder point** | expected demand during the supplier's lead time, plus a safety buffer sized to the target service level | The stock level that should trigger placing a new order | The single number a warehouse system or a person checks to decide "order now" vs. "wait" |
| **Safety stock (fixed vs. variable lead time)** | a buffer computed two ways — assuming the supplier's delivery time never varies, and accounting for the fact that it does | How much extra stock protects against running out | The variable-lead-time version is the realistic one: a supplier that's sometimes early, sometimes late, is a second source of risk on top of unpredictable demand. Comparing the two (`safety_stock_uplift_pct`) shows how much *extra* buffer that supplier unreliability alone is costing you |
| **Safety stock investment** | safety stock units × unit cost | The cash value tied up in that buffer, per product | Turns an operational number (units) into a financial one (dollars), so purchasing/finance can see exactly where working capital is locked up — and this repo ranks every output by this column for that reason |
| **Economic order quantity (EOQ)** | the order size that minimizes the sum of ordering cost (placing an order) and holding cost (carrying inventory) | How much to order each time you do reorder | Ordering too often wastes money on order-processing fees; ordering too rarely wastes money on warehouse space and tied-up cash. EOQ finds the size that minimizes the *total* of both, which neither "order a little often" nor "order a lot rarely" gets right on its own |
| **Annual logistics cost** | ordering cost + holding cost + cost of the goods themselves, all annualized | The full yearly cost of carrying a product at its EOQ | Lets you compare the true cost of stocking different products on an apples-to-apples basis, not just their sticker price |

**Bottom line for the business:** this pipeline turns raw transaction
history into a ranked list — which products need the most safety-stock
capital, what triggers a reorder, and how much to order — so purchasing
decisions are driven by actual sales patterns and real supplier data
(lead time, cost, ordering cost, holding rate — see `README.md`'s "Data
source" section) instead of gut feel or a single flat assumption applied
to every product alike.

---

## 2. Policy backtest

**The business problem:** the reorder point and EOQ above are *formulas* —
they tell you what to do in theory, under an assumed steady demand
pattern. But real demand is lumpy, especially for anything outside the
top sellers. Before trusting a formula-driven policy with real money,
it's worth asking: **if I had actually run this policy day-by-day against
this product's real sales history, would it have worked?**

| Term | What it means | Business use |
|---|---|---|
| **Review policy** (`min_Q`, `base_stock`, `min_max`, `periodic_review`, `hybrid`) | Different rules for *when* and *how much* to reorder — e.g. "reorder a fixed quantity whenever stock drops below X" vs. "review stock every 7 days and top up to a target" | Different policies suit different operational realities (can you check stock continuously, or only on a schedule?) — backtesting several side by side shows which one actually fits a given product |
| **Fill rate** | % of demand that was satisfied from stock on hand, simulated day by day | The real-world equivalent of "service level" — not a target, but what the policy would have *actually delivered* against real demand |
| **Average inventory level** | mean stock on hand across the simulated period | The real carrying cost implied by a policy, in units — some policies hit the same fill rate with much less stock sitting around |
| **Lost sales** | demand that arrived while stock was at zero | The direct, countable cost of a policy falling short |

**Bottom line for the business:** this answers "does the theory hold up
in practice?" for the SKUs where the most money is at stake (ranked by
safety-stock investment from the inventory-planning step) — surfacing,
for example, that a leaner policy can hit the same fill rate with far
less average inventory, which is money freed up for something else.

---

## 3. Advanced analytics

Three separate business questions live in this module.

### 3a. Demand-pattern classification

**The business problem:** not all "unpredictable" demand is unpredictable
in the same way, and different demand *shapes* call for different
forecasting and stocking approaches — one formula doesn't fit all products.

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **ADI** (Average Demand Interval) | average number of days between sales | How often a product sells at all | Distinguishes "sells every day" from "sells once a month" |
| **CV²** (squared coefficient of variation) | (standard deviation ÷ mean)² of demand, on days it sells | How erratic the *size* of each sale is, once it happens | Distinguishes "sells a steady amount" from "sells 1 unit sometimes, 50 units other times" |
| **Demand pattern** (smooth / intermittent / erratic / lumpy) | ADI and CV² each compared against a threshold (the standard Syntetos-Boylan-Croston cutoffs) | Which of four demand shapes a product falls into | Smooth-demand products suit the standard reorder-point math above; lumpy/intermittent ones need different treatment (e.g. the newsvendor model below, or manual review) rather than a formula tuned for steady sellers |

### 3b. Price elasticity and optimization

**The business problem:** **what happens to sales if I change a
product's price** — and is there a price that makes *more money* than
the current one?

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Price elasticity** | a fitted linear relationship between price and demand, per SKU | How sensitive a product's sales volume is to price changes | A product with high elasticity loses a lot of volume from a small price increase (be careful raising prices); a low-elasticity product barely changes (room to raise price without losing many sales) |
| **Price optimization** | fits demand curves (linear/logit/polynomial) and finds the price that maximizes revenue vs. the price that maximizes profit | The actual dollar-optimal price point, not just the direction to move | Revenue-maximizing and profit-maximizing prices are often different numbers — profit accounts for `unit_cost`, revenue doesn't. This shows both, so a pricing decision reflects which goal the business actually has |

This only runs on SKUs with enough real price variation in the data (most
don't have any — see the module's own numbers in `README.md`) since
fitting a price-response curve to a product that never changed price is
fitting noise, not a signal.

### 3c. Single-period ("newsvendor") ordering

**The business problem:** the reorder-point model above assumes a product
gets *reordered repeatedly*. Some products don't — seasonal, promotional,
or one-shot items get ordered **once** for a period, with no chance to
reorder if you guessed wrong. That needs a different formula.

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Critical ratio** | (price − cost) ÷ (price − salvage value + penalty cost) | The balance between the cost of ordering too little (a lost sale, plus goodwill) vs. too much (markdown/salvage loss on unsold stock) | Answers "how much should I order for a one-shot buy?" directly from the economics of over- vs. under-ordering, rather than a repeatable reorder-point formula that doesn't apply here |
| **Optimal order quantity** | the demand quantile that matches the critical ratio | The single order quantity that balances those two risks | The actual number to put on the purchase order for a seasonal/promotional item |

---

## 4. Customer lifetime value

**The business problem:** not all customers are worth the same to the
business. **Which customers deserve retention spend (a loyalty
discount, a personal outreach), and which segments' behavior is most at
risk?**

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Recency** | days since a customer's last purchase | How likely they are to still be an active customer | A customer who bought yesterday is a very different retention risk than one who bought eight months ago |
| **Frequency** | number of distinct purchase occasions | How habitual their buying is | Frequent buyers are more predictable revenue and often more responsive to re-engagement |
| **Monetary (LTV)** | total amount spent | How much revenue a customer represents | The direct dollar stake in keeping or losing that customer |
| **RFM score** | recency/frequency/monetary each bucketed into tertiles, recency's order reversed (low recency = best) | A simplified 1–3 scale per dimension | A quick, explainable way to rank customers without needing a full model |
| **LTV segment** (Low / Mid / High) | customers clustered by their LTV value (k-means), ranked by actual mean spend per cluster | Which value tier a customer falls into | Directly actionable for marketing spend: concentrate retention budget on High-value customers at risk of churning (low recency), not spread evenly across everyone |

**A caveat worth knowing for this specific dataset:** the classifier that
predicts segment from RFM behavior is trained on `monetary`, which is the
same number the segments were clustered from in the first place — so its
~100% accuracy reflects recovering its own label, not a genuinely learned
behavioral pattern. Documented in `README.md`'s customer LTV section; a
production version would train the classifier on features (recency,
frequency, product mix, etc.) that don't include the value the segments
were built from.

---

## 5. Market basket analysis

**The business problem:** **which products should be promoted, bundled,
or placed near each other because customers tend to buy them together**
— and specifically, is there a way to use that pattern to move
slow-selling stock that would otherwise sit on a shelf?

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Support** | % of all orders that contain a given item or item combination | How common a product (or combination) is | Filters out combinations too rare to act on — a "rule" based on 2 orders out of 10,000 isn't a real pattern |
| **Confidence** | of orders containing the antecedent (e.g. "product A"), what % also contain the consequent (e.g. "product B") | How reliably buying A predicts also buying B | Directly answers "if a customer has A in their basket, how likely are they to want B too?" — the basis for a checkout recommendation or bundle offer |
| **Lift** | confidence of the rule ÷ the consequent's overall support | Whether the association is *real*, not just because the consequent is popular on its own | A lift of 1.0 means no relationship (buying A tells you nothing about B); this pipeline only keeps rules with lift > 1.0 — a genuine positive association, not a coincidence of a generally popular item |
| **Slow movers** | the bottom octile of products by total quantity sold | Products that aren't selling well on their own | The targets for cross-sell: pairing a slow mover with something popular (high lift, appears as the rule's consequent) can move stock that wouldn't sell through the front door on its own |

**Bottom line for the business:** this turns "customers who bought X also
bought Y" from an intuition into a number you can rank and act on —
whether that's a "frequently bought together" recommendation, a physical
shelf placement, or a targeted promotion for stock that needs to move.

---

## 6. Supplier segmentation

Two separate business questions live in this module.

### 6a. Cross-country product mix

**The business problem:** the ABC classification in inventory planning
answers "which products matter most" for **one** market. A business
operating across many countries needs to know: **does the same product
matter equally everywhere, or does its importance shift by market?**

Same formula as ABC classification above (volume × revenue, Pareto
buckets), computed **independently per country** rather than pooled —
because a SKU that's a top seller in Germany can be a long-tail item in
Australia, and pooling them together would hide that difference. This
matters for the business because purchasing, stocking, and marketing
decisions made centrally (e.g. "we're deprioritizing this SKU") can be
wrong for a specific market if they're based on global averages alone.

### 6b. Supplier risk/value segmentation (Kraljic matrix)

**The business problem:** a procurement team can't give every supplier
relationship equal attention. **Which supplier relationships are worth
negotiating hard on, which need risk mitigation (backup suppliers,
buffer stock), and which are safe to leave on autopilot?**

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Procurement spend** | total `Cost × Quantity` purchased, per SKU | How much money flows through that SKU's supply chain | The financial weight of the relationship — a $50/year SKU and a $7,000/year SKU don't deserve the same procurement attention |
| **Risk index** | sum of four risk factors: availability, number of alternative suppliers, how standardized the part is, price fluctuation | How exposed the business is if that supply breaks down | A SKU with few alternative suppliers and volatile pricing is a bigger operational risk than one with many interchangeable suppliers at a stable price, regardless of spend |
| **Kraljic quadrant** (Strategic / Leverage / Critical / Routine) | high/low spend crossed with high/low risk (split at the median of each, from the real data) | Which of four supplier-management strategies applies | **Strategic** (high spend, high risk): negotiate partnerships, secure long-term contracts. **Leverage** (high spend, low risk): use competitive bidding to negotiate price, since alternatives are plentiful. **Critical** (low spend, high risk): secure supply with safety stock or backup suppliers even though the dollar value is small, because a stockout would still hurt. **Routine** (low spend, low risk): minimize administrative effort — these don't need active management. |

**Bottom line for the business:** this replaces "manage every supplier
relationship the same way" with a matrix that tells procurement exactly
where to spend negotiating effort, where to build risk mitigation, and
where to simply automate and move on — grounded in this business's actual
spend and risk data, not a generic rule of thumb.

---

## 7. Weekly retail KPIs

**The business problem:** the metrics above answer detailed
product/customer/supplier questions. Leadership also needs a small set
of **weekly headline numbers** to track whether the business is
healthier or worse this week than last — the retail equivalent of a
dashboard's top row.

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **ATV** (average transaction value) | mean revenue per invoice, per week | How much a typical order is worth | A rising ATV with flat order counts means customers are buying more per visit — useful for judging whether a promotion or bundling push is working |
| **UPT** (units per transaction) | mean units sold per invoice, per week | How many items a typical order contains | Distinguishes "customers buying more items" from "customers buying pricier items" as the driver behind a change in ATV |
| **ASP** (average selling price) | `ATV ÷ UPT` | The effective average price per unit across everything sold that week | A quick check on whether price realization is holding up — falling ASP with flat UPT signals discounting pressure |
| **Conversion rate** | invoices ÷ website visitors, per week | What share of traffic actually buys | The core metric for judging site/marketing performance, not just sales volume — a traffic spike with flat conversion means the extra visitors aren't the problem, the funnel is |

All four are computed **per country and combined across all of them**,
so a category or country-level trend doesn't get lost in a single
global average.

**A caveat worth knowing for this specific dataset:** the uploaded
footfall data covers a different calendar period (2016-2020) than the
transaction data (2009-2011), so conversion rate here is computed
against footfall dates *shifted* to overlap the transaction period —
reusing the real footfall pattern, not actual historical footfall for
those years. Treat conversion rate as an illustrative estimate for this
dataset, not a verified historical number — see `README.md`'s "Weekly
retail KPIs" section for the full explanation. ATV/UPT/ASP don't depend
on footfall and aren't affected by this caveat.

---

## 8. Assortment planning

**The business problem:** shelf space, catalog placement, and marketing
attention are all limited — you can't feature every category equally.
**Given a fixed amount of total space to split across the best-selling
categories, how much should each one get to maximize profit?**

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Assortment-breadth proxy** | a category's share of active SKUs among the top categories, per week | How much "space" a category effectively occupies, when there's no real shelf-space data to measure it directly | Lets a space-allocation model run on transaction data alone — more distinct products actively selling functions like more shelf space would in a physical store |
| **Cross-category elasticity model** | a log-log regression: each category's weekly unit sales as a function of *every* top category's space share, not just its own | Whether growing one category's space helps, hurts, or doesn't affect another's sales | Captures cannibalization (categories competing for the same customer attention) or complementarity (categories that sell better together) — a model based only on each category's own space would miss this entirely |
| **Average unit gross profit** | `(Price − Cost)`, averaged per unit sold, per category | How much profit one more unit sold actually contributes | Converts a sales *volume* prediction into a profit prediction — a category with high volume but thin margin can lose to a lower-volume, higher-margin one once profit is what's being optimized |
| **Optimized assortment allocation** | space shares (each bounded to a realistic 10-70% range, summing to 100%) chosen to maximize total predicted weekly gross profit | The recommended space split across categories | A concrete, numbers-backed starting point for a category/merchandising planning conversation — not a final decision, since (as the model itself flags via R²) assortment breadth is only one of many things that drive demand |

**Bottom line for the business:** this turns "which categories should we
feature more" from a judgment call into a testable hypothesis, grounded
in how this business's own categories have actually interacted
historically — while being explicit (via R²) about how much of demand
that hypothesis actually explains, so it's used as an input to a
merchandising decision, not a substitute for one.

---

## 9. Trade-area modelling

**The business problem:** when you're choosing between store locations,
or trying to understand which of several existing stores a given
market's customers are likely to shop at, you need a principled way to
answer **"how much of this market's demand will each store actually
capture?"** — not just "which store is closest" or "which store is
biggest," but both at once.

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Market potential** | households × average spend per household, per trade area | The total demand available in a market, independent of which store serves it | Sets the ceiling — a store can only ever capture a share of what's actually there to capture |
| **Store attractiveness** | each store's characteristics (size, parking, highway access, traffic, accessibility, design, surrounding business density), each scaled 0-1 and summed | A single "pulling power" score per store, comparable across stores despite the underlying characteristics being on completely different scales (square feet vs. number of parking spaces vs. a traffic index) | Lets a bigger, better-located, more accessible store be recognized as more competitive without needing a subjective "which store is better" judgment call |
| **Huff gravity model** | for each (market, store) pair: `attractiveness ÷ distance²`, then normalized so every store's share sums to 100% per market | The probability a given market's customers choose a given store, based on the classic retail-gravity principle that pull increases with attractiveness and drops off sharply (squared) with distance | Directly answers the question above — not a guess, but a probability grounded in both how good a store is and how far away it is |
| **Expected capture** | capture probability × that market's total potential | The actual predicted demand (not just a %) a store should expect from a given market | Rolls up across every market to answer "how much total demand should this store expect, given where it is and how good it is compared to competitors?" — the core number behind a site-selection or capacity-planning decision |

**Bottom line for the business:** this is the analytical backbone of
site selection and store-network planning — instead of choosing a new
location by intuition ("that area looks busy"), it quantifies exactly
how much of a market's spending power a store at a given location, with
given characteristics, competing against specific named competitors,
should expect to win. In this repo's run, it also surfaces a concrete
insight: raw attractiveness isn't destiny — a less "attractive" store
can still dominate total capture if it's dramatically closer to the
single largest market (see `README.md`'s Trade-area modelling section
for the numbers), which is exactly the kind of trade-off this model
exists to quantify.

---

## 10. Hybrid SKU forecasting

**The business problem:** every forecasting method has a blind spot.
A simple average is honest about a product that barely sells, but
misses a real trend. A sophisticated machine-learning model can find
subtle patterns, but needs enough regular data to learn from — and can
be confidently wrong on a product that sells three units a month.
**Which approach should forecast which product, and how do you know
before you commit to an order quantity based on it?**

| Term | Formula | What it means | Business use |
|---|---|---|---|
| **Demand classification** | ADI (how rarely a product sells) and CV² (how much its order size varies) compared against standard thresholds | Buckets every SKU into Smooth, Intermittent, Erratic, or Lumpy | Explains *why* a forecast looks the way it does — a "Lumpy" classification is a warning that no method will predict this SKU's week-to-week demand precisely, so the business decision should lean on safety stock, not forecast precision |
| **Backtest** | run a forecasting method on data up to 12 weeks ago, compare its prediction to what actually happened | A trust score for a forecasting method, specific to one SKU | Replaces "which forecasting method is best" (a question with no universal answer) with "which method actually worked for *this* product" |
| **Classical/intermittent-demand methods** (Naive, moving averages, exponential smoothing, Croston/TSB) | each a different, simple, well-established way of estimating a flat future demand rate from history | Reliable, explainable forecasts that don't need much data to work | The right choice for the large share of any retail catalog that sells occasionally and unpredictably — where a complex model has nothing real to learn from |
| **Machine-learning panel model** | one shared model trained across every SKU at once, using each week's sales history, calendar position, and product category as inputs | A forecast that can pick up on patterns too subtle for a simple formula — seasonality interacting with category, a product's own sales trend, similar products' behavior | The right choice for SKUs with enough regular history that there's a real pattern worth learning, not just noise |
| **Hybrid selection** | per SKU, whichever approach's backtest was more accurate wins | The forecast that actually goes into planning | Avoids the two failure modes of picking one method for the whole catalog: forcing a data-hungry ML model onto sparse sellers (where it just overfits noise), or forcing a flat statistical average onto high-volume regulars (where it misses a learnable trend) |

**Bottom line for the business:** instead of asking "what's our
forecasting model," this treats forecasting as 3,000+ separate small
decisions — one per SKU — each backed by evidence (a real backtest
against real recent demand) about which approach earns the right to
predict it. In this repo's run, the classical suite won for 70% of SKUs
and the ML model for the other 30%, and the 12-week forecast rolls up
directly into a revenue and gross-profit projection, so the output
feeds straight into the reorder and purchasing decisions the rest of
this pipeline is built around.
