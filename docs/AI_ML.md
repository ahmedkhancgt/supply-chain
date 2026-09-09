# AI/ML Algorithms & Statistical Optimization

## 1. Time-Series Demand Forecasting Engine

The demand forecasting engine processes historical sales data using Pandas, NumPy, and Statsmodels to forecast future SKU demand per warehouse facility.

### Methodology
1. **Daily Resampling**: Aggregates daily transaction volume and fills zero-sales days to maintain uniform time intervals.
2. **Exponential Smoothing & Trend Decomposition**: Calculates rolling averages and linear trend components.
3. **Weekly Seasonality**: Adjusts daily predictions for weekend consumption spikes.
4. **Confidence Intervals**: Computes 95% confidence bounds ($\pm 1.96 \cdot \sigma$).
5. **Accuracy Metrics**: Calculates MAE (Mean Absolute Error) and RMSE (Root Mean Squared Error) on test splits.

## 2. Inventory Optimization Formulas

Deterministic calculations compute optimal safety stock and reorder points:

- **Daily Demand Average ($D$)**:
  $$D = \frac{1}{N} \sum_{i=1}^{N} \text{Sales}_i$$

- **Safety Stock ($SS$)**:
  $$SS = \max\left(\text{SS}_{\text{min}}, Z \cdot \sigma_D \cdot \sqrt{L}\right)$$
  *(where $Z = 1.65$ for 95% service level, $\sigma_D$ is demand std dev, $L$ is lead time in days)*

- **Reorder Point ($ROP$)**:
  $$ROP = (D \cdot L) + SS$$

- **Recommended Order Quantity ($ROQ$)**:
  $$ROQ = \max\left(0, ROP + SS - \text{Current Stock}\right)$$

## 3. Inventory Risk Engine

Classifies stockout risk into 4 tiers:
- `CRITICAL`: Current Stock < Safety Stock OR Days of Inventory < Lead Time.
- `HIGH`: Current Stock <= Reorder Point.
- `MEDIUM`: Operating normally within Reorder Point bounds.
- `LOW`: Excess Stock (Days of Inventory > 60 days).
