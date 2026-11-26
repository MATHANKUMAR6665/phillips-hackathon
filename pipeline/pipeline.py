#!/usr/bin/env python3
"""Spend Truth Engine - Business Deviation Analysis & Commentary Pipeline."""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl  # noqa: F401 - required engine / Excel output
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
UNIT_MULTIPLIER = 1000
ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_XLSX = ROOT_DIR / "advertising_promotion_data.xlsx"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DASHBOARD_PUBLIC_JSON = ROOT_DIR / "dashboard" / "public" / "dashboard_data.json"

TARGET_ANNUAL_AP_EUR = 650_000_000.0
RECON_TOLERANCE_PCT = 0.10

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

EXPECTED_METRICS = {
    "Advertising & Promotion Local",
    "Advertising & Promotion Central",
    "Total Sales",
    "Other Selling Expenses",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fmt_eur(val: float) -> str:
    """Format an EUR amount concisely for commentary."""
    sign = "-" if val < 0 else ""
    av = abs(val)
    if av >= 1_000_000:
        return f"{sign}EUR {av / 1_000_000:.2f}M"
    if av >= 1_000:
        return f"{sign}EUR {av / 1_000:.1f}K"
    return f"{sign}EUR {av:,.0f}"


def safe_div(num: float, den: float, default: float = 0.0) -> float:
    if den is None or den == 0 or not math.isfinite(den):
        return default
    res = num / den
    return res if math.isfinite(res) else default


def clean_float(val: Any, decimals: int | None = None) -> float:
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return 0.0
    f = float(val)
    if not math.isfinite(f):
        return 0.0
    return round(f, decimals) if decimals is not None else f


def compute_robust_stats(series: pd.Series) -> dict[str, Any]:
    """Compute robust z-scores (median/MAD, IQR fallback) and 1.5*IQR outlier flags."""
    vals = series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if len(vals) == 0:
        return {
            "z": pd.Series(dtype=float),
            "flag_mad": pd.Series(dtype=bool),
            "flag_iqr": pd.Series(dtype=bool),
            "confidence": pd.Series(dtype=str),
            "method": "none",
            "median": 0.0,
            "mad": 0.0,
            "iqr": 0.0,
        }

    med = float(np.median(vals))
    abs_dev = np.abs(vals - med)
    mad = float(np.median(abs_dev))
    q1 = float(np.percentile(vals, 25))
    q3 = float(np.percentile(vals, 75))
    iqr = q3 - q1

    if mad > 1e-12:
        z = 0.6745 * (vals - med) / mad
        method = "MAD"
    elif iqr > 1e-12:
        # Normal-equivalent scale from IQR: IQR ~= 1.34898 * sigma
        z = 1.34898 * (vals - med) / iqr
        method = "IQR_fallback"
    else:
        z = pd.Series(0.0, index=vals.index)
        method = "constant_zero"

    flag_mad = z.abs() > 3.5
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    if iqr > 1e-12:
        flag_iqr = (vals < lower_fence) | (vals > upper_fence)
    else:
        flag_iqr = vals != med

    both = flag_mad & flag_iqr
    either = flag_mad | flag_iqr
    confidence = pd.Series("none", index=vals.index)
    confidence[either] = "medium"
    confidence[both] = "high"

    return {
        "z": z,
        "flag_mad": flag_mad,
        "flag_iqr": flag_iqr,
        "confidence": confidence,
        "method": method,
        "median": med,
        "mad": mad,
        "iqr": iqr,
        "lower_fence": lower_fence,
        "upper_fence": upper_fence,
    }


def sanitize_for_json(obj: Any) -> Any:
    """Recursively ensure no NaN/Infinity/numpy scalars exist before json.dumps."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        if not math.isfinite(f):
            raise ValueError(f"Non-finite float encountered in JSON payload: {f}")
        return f
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


# ---------------------------------------------------------------------------
# Step 1: Load & Profile
# ---------------------------------------------------------------------------
def step1_load_and_profile(xlsx_path: Path) -> dict[str, pd.DataFrame]:
    print("=" * 80)
    print("STEP 1: LOAD & PROFILE WORKBOOK")
    print("=" * 80)
    assert xlsx_path.exists(), f"Input workbook not found: {xlsx_path}"

    sheets = {}
    for name in ["transactions", "products", "currencies", "markets"]:
        df = pd.read_excel(xlsx_path, sheet_name=name)
        sheets[name] = df
        print(f"\nSheet [{name}]: shape={df.shape}")
        print("  dtypes:", {c: str(t) for c, t in df.dtypes.items()})
        nulls = df.isna().sum()
        non_zero_nulls = {c: int(v) for c, v in nulls.items() if v > 0}
        print("  nulls:", non_zero_nulls if non_zero_nulls else "None")

    tx = sheets["transactions"]
    products = sheets["products"]
    currencies = sheets["currencies"]
    markets = sheets["markets"]

    # Profile assertions
    assert tx.shape == (8780, 15), f"Expected (8780, 15), got {tx.shape}"
    assert len(products) == 18, f"Expected 18 products, got {len(products)}"
    assert len(currencies) == 17, f"Expected 17 currencies, got {len(currencies)}"
    assert len(markets) == 6, f"Expected 6 markets, got {len(markets)}"

    tx_metrics = set(tx["metric_name"].astype(str).str.strip().unique())
    assert tx_metrics == EXPECTED_METRICS, f"Unexpected metrics: {tx_metrics}"

    actual_nulls = int(tx["actual_amount_local_currency"].isna().sum())
    budget_nulls = int(tx["budget_amount_local_currency"].isna().sum())
    print(f"\nProfiled assertions PASSED: transactions={tx.shape}, products=18, "
          f"currencies=17, markets=6, metrics={sorted(tx_metrics)}, "
          f"raw_nulls=(actual:{actual_nulls}, budget:{budget_nulls})")
    return sheets


# ---------------------------------------------------------------------------
# Step 2: Clean, Reconcile, Compute Finance & Statistics
# ---------------------------------------------------------------------------
def run_pipeline(stop_after_step3: bool = False) -> dict[str, Any]:
    sheets = step1_load_and_profile(INPUT_XLSX)
    tx_raw = sheets["transactions"].copy()
    products_df = sheets["products"].copy()
    currencies_df = sheets["currencies"].copy()
    markets_df = sheets["markets"].copy()

    quality_checks: list[dict[str, Any]] = []

    # 1. Exact duplicate rows
    raw_row_count = len(tx_raw)
    dup_mask = tx_raw.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    df = tx_raw.drop_duplicates(keep="first").copy()
    after_dedupe_count = len(df)
    assert dup_count == 28, f"Expected 28 duplicates, found {dup_count}"
    assert after_dedupe_count == 8752, f"Expected 8,752 rows after dedupe, got {after_dedupe_count}"
    quality_checks.append({
        "check": "Exact duplicate rows",
        "rows_affected": dup_count,
        "action": f"Dropped {dup_count} exact duplicate rows ({raw_row_count:,} -> {after_dedupe_count:,})",
        "status": "pass",
    })

    # Normalize metric_name whitespace
    df["metric_name"] = df["metric_name"].astype(str).str.strip()

    # Check Cost Center uniqueness per country+product (Issue 6)
    cc_per_pair = df.groupby(["country_code", "product_unit_code"])["cost_center_code"].nunique()
    assert int(cc_per_pair.max()) == 1, "cost_center_code is not 1-to-1 with country+product"
    quality_checks.append({
        "check": "Cost center grain redundancy",
        "rows_affected": int(len(cc_per_pair)),
        "action": "Verified 1 cost_center_code per country+product pair; kept in output, ignored for grouping",
        "status": "pass",
    })

    # Ignore Other Selling Expenses (before A&P/Sales processing)
    ose_mask = df["metric_name"] == "Other Selling Expenses"
    ose_count = int(ose_mask.sum())
    df = df[~ose_mask].copy()
    quality_checks.append({
        "check": "Ignore Other Selling Expenses",
        "rows_affected": ose_count,
        "action": (
            f"Excluded {ose_count:,} 'Other Selling Expenses' rows; "
            "A&P = Local + Central, sales base = Total Sales"
        ),
        "status": "pass",
    })

    # Issue 4: Clean dirty business_indicator & business_code (TRIM + UPPER)
    raw_bi = df["business_indicator"].astype(str)
    raw_bc = df["business_code"].astype(str)
    df["business_indicator"] = raw_bi.str.strip().str.upper()
    df["business_code"] = raw_bc.str.strip().str.upper()
    dirty_str_count = int(((raw_bi != df["business_indicator"]) | (raw_bc != df["business_code"])).sum())
    quality_checks.append({
        "check": "Dirty indicator & code strings",
        "rows_affected": dirty_str_count,
        "action": "Trimmed whitespace and uppercased business_indicator and business_code before rules",
        "status": "pass",
    })

    # Issue 5 & Rule R1: Map market codes via markets sheet, then reassign Business
    markets_df["market_short_name"] = markets_df["market_short_name"].astype(str).str.strip()
    markets_df["market_name"] = markets_df["market_name"].astype(str).str.strip()
    market_map = dict(zip(markets_df["market_short_name"], markets_df["market_name"]))

    df["market_name_raw"] = df["market_name"].astype(str).str.strip()
    short_mapped_count = int(df["market_name_raw"].isin(market_map).sum())
    df["market_base"] = df["market_name_raw"].map(lambda x: market_map.get(x, x))
    expected_mkt_names = set(markets_df["market_name"])
    assert set(df["market_base"]).issubset(expected_mkt_names), "Unmapped market names found"

    flag_only = (df["business_indicator"] == "Y") & (df["business_code"] != "NON")
    code_only = (df["business_indicator"] != "Y") & (df["business_code"] == "NON")
    both_biz = (df["business_indicator"] == "Y") & (df["business_code"] == "NON")
    biz_mask = (df["business_indicator"] == "Y") | (df["business_code"] == "NON")

    df["business_reassigned"] = biz_mask
    df["market"] = np.where(biz_mask, "Business", df["market_base"])

    n_flag_only = int(flag_only.sum())
    n_code_only = int(code_only.sum())
    n_both = int(both_biz.sum())
    n_biz_total = int(biz_mask.sum())
    # Note: totals across all 4 metrics vs 3 active metrics — verify both!
    # Recompute check on after_dedupe (including OSE) too for verification
    tx_dedup_bi = tx_raw.drop_duplicates(keep="first")
    bi_all = tx_dedup_bi["business_indicator"].astype(str).str.strip().str.upper()
    bc_all = tx_dedup_bi["business_code"].astype(str).str.strip().str.upper()
    all_flag_only = int(((bi_all == "Y") & (bc_all != "NON")).sum())
    all_code_only = int(((bi_all != "Y") & (bc_all == "NON")).sum())
    all_both = int(((bi_all == "Y") & (bc_all == "NON")).sum())
    all_biz_total = int(((bi_all == "Y") | (bc_all == "NON")).sum())
    assert all_both == 0, f"Expected 0 overlap in Business rule, found {all_both}"
    assert abs(all_flag_only - 480) <= 5, f"Unexpected flag_only count: {all_flag_only}"
    assert abs(all_code_only - 1192) <= 5, f"Unexpected code_only count: {all_code_only}"

    quality_checks.append({
        "check": "Market mapping & Business reassignment (R1)",
        "rows_affected": n_biz_total,
        "action": (
            f"Mapped {short_mapped_count:,} short market codes via markets sheet; reassigned "
            f"{n_biz_total:,} active rows ({all_flag_only} flag-only + {all_code_only} code-only = "
            f"{all_biz_total:,} across 4 metrics, 0 overlap) to 'Business'"
        ),
        "status": "pass",
    })

    # Issue 3 (before imputation): Fix A&P sign-entry errors (positive actual when budget < 0)
    is_ap = df["metric_name"].isin(["Advertising & Promotion Local", "Advertising & Promotion Central"])
    sign_err_mask = (
        is_ap
        & df["actual_amount_local_currency"].notna()
        & df["budget_amount_local_currency"].notna()
        & (df["actual_amount_local_currency"] > 0)
        & (df["budget_amount_local_currency"] < 0)
    )
    sign_fixed_count = int(sign_err_mask.sum())
    df["sign_fixed"] = False
    df.loc[sign_err_mask, "actual_amount_local_currency"] = -df.loc[sign_err_mask, "actual_amount_local_currency"]
    df.loc[sign_err_mask, "sign_fixed"] = True
    assert sign_fixed_count == 6, f"Expected 6 sign errors, found {sign_fixed_count}"

    # Issue 2: Impute missing actual or budget using median actual/budget ratio of country+product+metric
    both_present = df["actual_amount_local_currency"].notna() & df["budget_amount_local_currency"].notna()
    valid_ratio_rows = df[both_present & (df["budget_amount_local_currency"] != 0)].copy()
    valid_ratio_rows["_ratio"] = (
        valid_ratio_rows["actual_amount_local_currency"] / valid_ratio_rows["budget_amount_local_currency"]
    )
    median_ratios = (
        valid_ratio_rows.groupby(["country_code", "product_unit_code", "metric_name"])["_ratio"]
        .median()
        .to_dict()
    )

    df["imputed"] = False
    actual_null_mask = df["actual_amount_local_currency"].isna() & df["budget_amount_local_currency"].notna()
    budget_null_mask = df["budget_amount_local_currency"].isna() & df["actual_amount_local_currency"].notna()
    both_null_mask = df["actual_amount_local_currency"].isna() & df["budget_amount_local_currency"].isna()

    imputed_actual_count = 0
    imputed_budget_count = 0
    drop_indices = list(df.index[both_null_mask])

    for idx in df.index[actual_null_mask]:
        key = (df.at[idx, "country_code"], df.at[idx, "product_unit_code"], df.at[idx, "metric_name"])
        ratio = median_ratios.get(key)
        if ratio is None or not math.isfinite(ratio) or ratio == 0:
            drop_indices.append(idx)
        else:
            df.at[idx, "actual_amount_local_currency"] = df.at[idx, "budget_amount_local_currency"] * ratio
            df.at[idx, "imputed"] = True
            imputed_actual_count += 1

    for idx in df.index[budget_null_mask]:
        key = (df.at[idx, "country_code"], df.at[idx, "product_unit_code"], df.at[idx, "metric_name"])
        ratio = median_ratios.get(key)
        if ratio is None or not math.isfinite(ratio) or ratio == 0:
            drop_indices.append(idx)
        else:
            df.at[idx, "budget_amount_local_currency"] = df.at[idx, "actual_amount_local_currency"] / ratio
            df.at[idx, "imputed"] = True
            imputed_budget_count += 1

    dropped_null_count = len(drop_indices)
    if drop_indices:
        df = df.drop(index=drop_indices).copy()

    total_imputed = imputed_actual_count + imputed_budget_count
    assert df["actual_amount_local_currency"].isna().sum() == 0
    assert df["budget_amount_local_currency"].isna().sum() == 0

    quality_checks.append({
        "check": "Missing actual/budget amounts",
        "rows_affected": total_imputed + dropped_null_count,
        "action": (
            f"Imputed {total_imputed} nulls ({imputed_actual_count} actual, {imputed_budget_count} budget) "
            f"via median actual/budget ratio per country+product+metric; dropped {dropped_null_count} unresolvable"
        ),
        "status": "pass",
    })

    # Convert A&P spend to POSITIVE (costs stored negative -> spend = -amount; sales stays positive)
    df["actual_local_signed"] = np.where(
        df["metric_name"].isin(["Advertising & Promotion Local", "Advertising & Promotion Central"]),
        -df["actual_amount_local_currency"],
        df["actual_amount_local_currency"],
    )
    df["budget_local_signed"] = np.where(
        df["metric_name"].isin(["Advertising & Promotion Local", "Advertising & Promotion Central"]),
        -df["budget_amount_local_currency"],
        df["budget_amount_local_currency"],
    )

    quality_checks.append({
        "check": "Sign convention & 6 A&P sign anomalies",
        "rows_affected": sign_fixed_count,
        "action": (
            f"Fixed {sign_fixed_count} A&P Local rows with positive actual & negative budget (sign_fixed=True); "
            "converted all A&P costs to positive spend and kept Total Sales positive"
        ),
        "status": "pass",
    })

    # Issue 7: Verify Total Sales budget > 0 and non-null
    sales_rows = df[df["metric_name"] == "Total Sales"]
    unusable_sales = sales_rows[
        sales_rows["budget_local_signed"].isna() | (sales_rows["budget_local_signed"] <= 0)
    ]
    flagged_unusable = unusable_sales[["transaction_id", "country_code", "product_unit_code", "month"]].to_dict("records")
    assert len(flagged_unusable) == 0, f"Unusable sales rows found: {flagged_unusable}"
    quality_checks.append({
        "check": "Total Sales denominator usability",
        "rows_affected": len(flagged_unusable),
        "action": "Verified 0 remaining Total Sales rows have budget_sales <= 0 or null after imputation",
        "status": "pass",
    })

    # Rule R2: Currency conversion (DIVIDE by local_currency_per_eur, apply UNIT_MULTIPLIER=1000)
    currencies_df["currency_description"] = currencies_df["currency_description"].astype(str).str.strip()
    fx_map = dict(zip(currencies_df["currency_description"], currencies_df["local_currency_per_eur"]))
    df["currency_description"] = df["currency_description"].astype(str).str.strip()

    assert set(df["currency_description"]).issubset(set(fx_map.keys())), "Missing FX rate for currency"
    currencies_per_country = df.groupby("country_code")["currency_description"].nunique()
    assert int(currencies_per_country.max()) == 1, "Country maps to multiple currencies"

    df["local_currency_per_eur"] = df["currency_description"].map(fx_map)
    df["actual_eur"] = (df["actual_local_signed"] / df["local_currency_per_eur"]) * UNIT_MULTIPLIER
    df["budget_eur"] = (df["budget_local_signed"] / df["local_currency_per_eur"]) * UNIT_MULTIPLIER

    # Join product_unit_name
    products_df["product_unit_name"] = products_df["product_unit_name"].astype(str).str.strip()
    prod_map = dict(zip(products_df["product_unit_code"], products_df["product_unit_name"]))
    assert set(df["product_unit_code"]).issubset(set(prod_map.keys())), "Missing product name"
    df["product_unit_name"] = df["product_unit_code"].map(prod_map)

    quality_checks.append({
        "check": "Currency conversion & 1:1 country-currency check (R2)",
        "rows_affected": len(df),
        "action": (
            f"Divided local amounts by local_currency_per_eur across {len(fx_map)} currencies "
            f"(1 currency/country verified) and applied UNIT_MULTIPLIER={UNIT_MULTIPLIER:,}"
        ),
        "status": "pass",
    })

    # Issue 8: Coverage check on pair-channel month counts
    combo_months = (
        df.groupby(["country_code", "product_unit_code", "sales_channel"])["month"]
        .nunique()
        .reset_index(name="month_count")
    )
    incomplete_combos = combo_months[combo_months["month_count"] < 12]
    n_incomplete = int(len(incomplete_combos))
    assert n_incomplete == 8, f"Expected 8 incomplete 11-month pair-channel combos, got {n_incomplete}"
    quality_checks.append({
        "check": "Pair-channel 12-month coverage",
        "rows_affected": n_incomplete,
        "action": (
            f"Found {n_incomplete} country-product-channel combos with 11 months instead of 12 "
            "(left as-is; no synthetic months invented)"
        ),
        "status": "warn",
    })

    # -----------------------------------------------------------------------
    # Rule R3 & R4: Compute allowance at finest grain (country x product x sales_channel x month)
    # -----------------------------------------------------------------------
    grain_cols = [
        "market",
        "country_code",
        "country_name",
        "product_unit_code",
        "product_unit_name",
        "sales_channel",
        "month",
    ]
    # Verify market is invariant inside (country, product, sales_channel, month)
    mkt_nunique = df.groupby(["country_code", "product_unit_code", "sales_channel", "month"])["market"].nunique()
    assert int(mkt_nunique.max()) == 1, "Multiple markets within same channel-month grain"

    piv_actual = (
        df.pivot_table(index=grain_cols, columns="metric_name", values="actual_eur", aggfunc="sum", fill_value=0.0)
    )
    piv_budget = (
        df.pivot_table(index=grain_cols, columns="metric_name", values="budget_eur", aggfunc="sum", fill_value=0.0)
    )

    cm = pd.DataFrame(index=piv_actual.index).reset_index()
    cm["actual_local"] = piv_actual["Advertising & Promotion Local"].values
    cm["budget_local"] = piv_budget["Advertising & Promotion Local"].values
    cm["actual_central"] = piv_actual["Advertising & Promotion Central"].values
    cm["budget_central"] = piv_budget["Advertising & Promotion Central"].values
    cm["actual_ap"] = cm["actual_local"] + cm["actual_central"]
    cm["budget_ap"] = cm["budget_local"] + cm["budget_central"]
    cm["actual_sales"] = piv_actual["Total Sales"].values
    cm["budget_sales"] = piv_budget["Total Sales"].values

    assert len(cm) == 2188, f"Expected 2,188 channel-month rows, got {len(cm)}"
    assert (cm["budget_sales"] > 0).all(), "Zero/negative budget_sales at channel-month grain"

    sales_ratio = cm["actual_sales"] / cm["budget_sales"]
    cm["allowance_local"] = cm["budget_local"] * sales_ratio
    cm["allowance_central"] = cm["budget_central"] * sales_ratio
    cm["allowance"] = cm["budget_ap"] * sales_ratio
    cm["overspend_local"] = cm["actual_local"] - cm["allowance_local"]
    cm["overspend_central"] = cm["actual_central"] - cm["allowance_central"]
    cm["real_overspend"] = cm["actual_ap"] - cm["allowance"]
    cm["raw_variance"] = cm["actual_ap"] - cm["budget_ap"]
    cm["justified"] = cm["allowance"] - cm["budget_ap"]

    # Aggregate upward to pair x month (inside each market)
    pm_group = [
        "market", "country_code", "country_name",
        "product_unit_code", "product_unit_name", "month",
    ]
    sum_cols = [
        "actual_local", "budget_local", "actual_central", "budget_central",
        "actual_ap", "budget_ap", "actual_sales", "budget_sales",
        "allowance_local", "allowance_central", "allowance",
        "overspend_local", "overspend_central", "real_overspend",
        "raw_variance", "justified",
    ]
    pair_month = cm.groupby(pm_group, as_index=False)[sum_cols].sum()
    pair_month["real_overspend_pct"] = np.where(
        pair_month["allowance"] > 0,
        (pair_month["real_overspend"] / pair_month["allowance"]) * 100.0,
        0.0,
    )
    pair_month["sales_vs_plan_pct"] = np.where(
        pair_month["budget_sales"] > 0,
        ((pair_month["actual_sales"] - pair_month["budget_sales"]) / pair_month["budget_sales"]) * 100.0,
        0.0,
    )

    # -----------------------------------------------------------------------
    # Statistics: Pair x Month anomaly detection within each market
    # -----------------------------------------------------------------------
    pair_month["z"] = 0.0
    pair_month["flag_mad"] = False
    pair_month["flag_iqr"] = False
    pair_month["flag"] = False
    pair_month["confidence"] = "none"

    for mkt, idxs in pair_month.groupby("market").groups.items():
        stats = compute_robust_stats(pair_month.loc[idxs, "real_overspend_pct"])
        pair_month.loc[idxs, "z"] = stats["z"].values
        pair_month.loc[idxs, "flag_mad"] = stats["flag_mad"].values
        pair_month.loc[idxs, "flag_iqr"] = stats["flag_iqr"].values
        pair_month.loc[idxs, "confidence"] = stats["confidence"].values
        pair_month.loc[idxs, "flag"] = (stats["flag_mad"] | stats["flag_iqr"]).values

    # -----------------------------------------------------------------------
    # Monthly corrected-variance series per market (Jan-Dec)
    # -----------------------------------------------------------------------
    mkt_month = pair_month.groupby(["market", "month"], as_index=False)[sum_cols].sum()
    mkt_month["corrected_variance"] = mkt_month["real_overspend"]
    mkt_month["z"] = 0.0
    mkt_month["flag"] = False
    mkt_month["confidence"] = "none"

    for mkt, idxs in mkt_month.groupby("market").groups.items():
        stats = compute_robust_stats(mkt_month.loc[idxs, "corrected_variance"])
        mkt_month.loc[idxs, "z"] = stats["z"].values
        mkt_month.loc[idxs, "confidence"] = stats["confidence"].values
        mkt_month.loc[idxs, "flag"] = (stats["flag_mad"] | stats["flag_iqr"]).values

    # Also compute global totals & reconciliation assertions
    global_actual = float(cm["actual_ap"].sum())
    global_budget = float(cm["budget_ap"].sum())
    global_allowance = float(cm["allowance"].sum())
    global_raw_var = float(cm["raw_variance"].sum())
    global_justified = float(cm["justified"].sum())
    global_real_overspend = float(cm["real_overspend"].sum())
    global_sales_actual = float(cm["actual_sales"].sum())
    global_sales_budget = float(cm["budget_sales"].sum())

    ap_pct_of_sales = safe_div(global_actual, global_sales_actual) * 100.0
    recon_diff_pct = abs(global_actual - TARGET_ANNUAL_AP_EUR) / TARGET_ANNUAL_AP_EUR

    assert abs(global_raw_var - (global_justified + global_real_overspend)) < 1e-4, (
        "Global identity raw_variance == justified + real_overspend FAILED"
    )
    assert recon_diff_pct <= RECON_TOLERANCE_PCT, (
        f"Global A&P actual {global_actual:,.0f} is >10% away from {TARGET_ANNUAL_AP_EUR:,.0f}"
    )

    quality_checks.append({
        "check": "Unit scale & finance reconciliation (R3)",
        "rows_affected": len(cm),
        "action": (
            f"Global A&P actual={fmt_eur(global_actual)} ({recon_diff_pct*100:.2f}% from EUR 650M benchmark; "
            f"{ap_pct_of_sales:.2f}% of Total Sales). Verified raw_variance == justified + real_overspend"
        ),
        "status": "pass",
    })

    # -----------------------------------------------------------------------
    # Market-level summary & Bridge
    # -----------------------------------------------------------------------
    market_summary_df = pair_month.groupby("market", as_index=False)[sum_cols].sum()
    market_summary_df["overspend_pct"] = np.where(
        market_summary_df["allowance"] > 0,
        (market_summary_df["real_overspend"] / market_summary_df["allowance"]) * 100.0,
        0.0,
    )
    market_summary_df["sales_vs_plan_pct"] = np.where(
        market_summary_df["budget_sales"] > 0,
        ((market_summary_df["actual_sales"] - market_summary_df["budget_sales"]) / market_summary_df["budget_sales"]) * 100.0,
        0.0,
    )
    market_summary_df = market_summary_df.sort_values("market").reset_index(drop=True)

    # Assert market totals == global total
    for col in ["actual_ap", "budget_ap", "allowance", "raw_variance", "justified", "real_overspend"]:
        mkt_sum = float(market_summary_df[col].sum())
        glob_sum = float(cm[col].sum())
        assert abs(mkt_sum - glob_sum) < 1e-4, f"Market sum mismatch on {col}: {mkt_sum} vs {glob_sum}"

    # -----------------------------------------------------------------------
    # Pair x Year aggregation & Market Rankings (all 6 markets incl Business)
    # -----------------------------------------------------------------------
    pair_agg = pair_month.groupby(
        ["market", "country_code", "country_name", "product_unit_code", "product_unit_name"],
        as_index=False,
    )[sum_cols].sum()

    pair_month_counts = pair_month.groupby(
        ["market", "country_code", "product_unit_code"]
    ).agg(
        months_count=("month", "nunique"),
        months_flagged=("flag", "sum"),
        months_overspent=("real_overspend", lambda s: int((s > 0).sum())),
    ).reset_index()

    pair_agg = pair_agg.merge(
        pair_month_counts,
        on=["market", "country_code", "product_unit_code"],
        how="left",
    )

    pair_agg["overspend_pct"] = np.where(
        pair_agg["allowance"] > 0,
        (pair_agg["real_overspend"] / pair_agg["allowance"]) * 100.0,
        0.0,
    )
    pair_agg["sales_vs_plan_pct"] = np.where(
        pair_agg["budget_sales"] > 0,
        ((pair_agg["actual_sales"] - pair_agg["budget_sales"]) / pair_agg["budget_sales"]) * 100.0,
        0.0,
    )
    pair_agg["spend_vs_budget_pct"] = np.where(
        pair_agg["budget_ap"] > 0,
        ((pair_agg["actual_ap"] - pair_agg["budget_ap"]) / pair_agg["budget_ap"]) * 100.0,
        0.0,
    )

    # Local share of overspend (positive Local overspend / total positive overspend when overspent;
    # otherwise |Local overspend| / (|Local overspend| + |Central overspend|))
    def calc_local_share(row: pd.Series) -> float:
        ov_loc = float(row["overspend_local"])
        ov_cen = float(row["overspend_central"])
        net_ov = float(row["real_overspend"])
        if net_ov > 0:
            pos_loc = max(ov_loc, 0.0)
            pos_cen = max(ov_cen, 0.0)
            denom = pos_loc + pos_cen
            return safe_div(pos_loc, denom, 0.5)
        abs_loc = abs(ov_loc)
        abs_cen = abs(ov_cen)
        return safe_div(abs_loc, abs_loc + abs_cen, 0.5)

    pair_agg["local_share_of_overspend"] = pair_agg.apply(calc_local_share, axis=1)

    # Top month & top-2 concentration per pair
    top_month_map: dict[tuple[str, str, int], int] = {}
    top2_share_map: dict[tuple[str, str, int], float] = {}
    for (mkt, cc, puc), grp in pair_month.groupby(["market", "country_code", "product_unit_code"]):
        # Month with highest positive overspend (or highest |overspend| if net <= 0)
        pos_months = grp[grp["real_overspend"] > 0].sort_values("real_overspend", ascending=False)
        if len(pos_months) > 0:
            top_m = int(pos_months.iloc[0]["month"])
            pos_sum = float(pos_months["real_overspend"].sum())
            top2_sum = float(pos_months.head(2)["real_overspend"].sum())
            top2_share = safe_div(top2_sum, pos_sum, 0.0)
        else:
            abs_sorted = grp.assign(_abs=grp["real_overspend"].abs()).sort_values("_abs", ascending=False)
            top_m = int(abs_sorted.iloc[0]["month"])
            top2_share = 0.0
        top_month_map[(mkt, cc, int(puc))] = top_m
        top2_share_map[(mkt, cc, int(puc))] = top2_share

    pair_agg["top_month"] = [
        top_month_map[(r["market"], r["country_code"], int(r["product_unit_code"]))]
        for _, r in pair_agg.iterrows()
    ]
    pair_agg["_top2_share"] = [
        top2_share_map[(r["market"], r["country_code"], int(r["product_unit_code"]))]
        for _, r in pair_agg.iterrows()
    ]

    # Market peer robust z, percentile, eligibility filter & best/worst ranking
    pair_agg["z"] = 0.0
    pair_agg["percentile"] = 50.0
    pair_agg["rank_type"] = "none"
    pair_agg["eligible_for_ranking"] = False

    relaxed_markets: list[str] = []
    market_spend_totals = pair_agg.groupby("market")["actual_ap"].sum().to_dict()

    for mkt, idxs in pair_agg.groupby("market").groups.items():
        sub = pair_agg.loc[idxs]
        stats = compute_robust_stats(sub["overspend_pct"])
        pair_agg.loc[idxs, "z"] = stats["z"].values

        # Percentile rank in market (0 to 100 based on overspend_pct)
        pct_ranks = sub["overspend_pct"].rank(pct=True, method="average") * 100.0
        pair_agg.loc[idxs, "percentile"] = pct_ranks.values

        mkt_spend = market_spend_totals[mkt]
        elig_mask = (sub["months_count"] >= 6) & (sub["actual_ap"] >= 0.01 * mkt_spend)
        if int(elig_mask.sum()) < 6:
            # Relax 1% spend filter first; keep >= 6 months if enough remain
            relaxed_mask = sub["months_count"] >= 6
            if int(relaxed_mask.sum()) >= 6:
                elig_mask = relaxed_mask
                relaxed_markets.append(f"{mkt} (relaxed <1% spend filter; kept >=6 months)")
            else:
                elig_mask = pd.Series(True, index=sub.index)
                relaxed_markets.append(f"{mkt} (relaxed both size & month filters)")

        pair_agg.loc[elig_mask.index[elig_mask], "eligible_for_ranking"] = True
        elig_sub = pair_agg.loc[elig_mask.index[elig_mask]]

        # 3 BEST: lowest overspend_pct, tie-break by higher sales_vs_plan_pct
        best_idxs = elig_sub.sort_values(
            by=["overspend_pct", "sales_vs_plan_pct"], ascending=[True, False]
        ).head(3).index
        # 3 WORST: highest overspend_pct, tie-break by lower sales_vs_plan_pct
        worst_idxs = elig_sub.sort_values(
            by=["overspend_pct", "sales_vs_plan_pct"], ascending=[False, True]
        ).head(3).index

        assert len(set(best_idxs) & set(worst_idxs)) == 0, f"Overlap in best/worst for {mkt}"
        pair_agg.loc[best_idxs, "rank_type"] = "best"
        pair_agg.loc[worst_idxs, "rank_type"] = "worst"

    quality_checks.append({
        "check": "Minimum-size ranking filter (>=6m & >=1% market spend)",
        "rows_affected": len(relaxed_markets),
        "action": (
            "Applied filter cleanly across all 6 markets (>=6 eligible pairs each)"
            if not relaxed_markets
            else "Relaxed filter for: " + "; ".join(relaxed_markets)
        ),
        "status": "warn" if relaxed_markets else "pass",
    })

    # -----------------------------------------------------------------------
    # Auto-Commentary Engine (rule-based templates, every number from data)
    # -----------------------------------------------------------------------
    def build_pair_commentary(row: pd.Series) -> str:
        prod = row["product_unit_name"]
        country = row["country_name"]
        mkt = row["market"]
        actual = float(row["actual_ap"])
        budget = float(row["budget_ap"])
        allow = float(row["allowance"])
        rov = float(row["real_overspend"])
        ov_pct = float(row["overspend_pct"])
        z_val = float(row["z"])
        m_flag = int(row["months_flagged"])
        m_ov = int(row["months_overspent"])
        sales_pct = float(row["sales_vs_plan_pct"])
        loc_share = float(row["local_share_of_overspend"])
        top_m = int(row["top_month"])
        top2_share = float(row["_top2_share"])

        # Determine primary & driver pattern labels
        labels: list[str] = []
        if rov > 0:
            if m_ov <= 2 or (top2_share >= 0.70 and m_ov <= 4):
                labels.append(f"one-off / timing, review campaign in {MONTH_NAMES[top_m]}")
            elif m_ov >= 6:
                labels.append("structural: reset budget or add spend-approval gate")
            if sales_pct > 2.0 and ov_pct <= 10.0:
                labels.append("justified growth investment")
            if loc_share >= 0.60:
                labels.append("local execution issue")
            elif loc_share <= 0.40:
                labels.append("central allocation issue")
        else:
            if sales_pct >= 0.0:
                labels.append(f"efficiency benchmark for {mkt}")
            elif float(row["raw_variance"]) > 0 and sales_pct > 0:
                labels.append("justified growth investment")
            else:
                labels.append(f"disciplined spend control in {mkt}")

        label_text = " | ".join(labels) if labels else "in-line execution"
        direction_word = "overspent" if rov > 0 else "underspent"
        sales_word = "above" if sales_pct >= 0 else "below"
        split_word = (
            f"{loc_share * 100:.0f}% Local / {(1 - loc_share) * 100:.0f}% Central"
        )

        s1 = (
            f"{country} {prod} ({mkt}) spent {fmt_eur(actual)} against {fmt_eur(budget)} budget "
            f"and {fmt_eur(allow)} sales-adjusted allowance, ending with {direction_word} variance of "
            f"{fmt_eur(rov)} ({ov_pct:+.1f}% vs allowance, peer z={z_val:+.2f})."
        )
        s2 = (
            f"Sales finished {abs(sales_pct):.1f}% {sales_word} plan with {m_flag} flagged months "
            f"(peak variance in {MONTH_NAMES[top_m]}; variance split {split_word})."
        )
        s3 = f"Pattern: {label_text}."
        return f"{s1} {s2} {s3}"

    pair_agg["commentary"] = pair_agg.apply(build_pair_commentary, axis=1)

    # Market summaries & Strategy actions
    market_summaries: list[dict[str, str]] = []
    strategy_actions: list[dict[str, Any]] = []
    market_list = sorted(market_summary_df["market"].tolist())

    for mkt in market_list:
        mrow = market_summary_df[market_summary_df["market"] == mkt].iloc[0]
        m_pairs = pair_agg[pair_agg["market"] == mkt]
        worst3 = m_pairs[m_pairs["rank_type"] == "worst"].sort_values("overspend_pct", ascending=False)
        best3 = m_pairs[m_pairs["rank_type"] == "best"].sort_values("overspend_pct", ascending=True)

        m_flagged_months = mkt_month[(mkt_month["market"] == mkt) & (mkt_month["flag"])]
        spike_text = (
            ", ".join(f"{MONTH_NAMES[int(r['month'])]} ({fmt_eur(r['corrected_variance'])})" for _, r in m_flagged_months.iterrows())
            if len(m_flagged_months) > 0
            else "no single statistical monthly outlier"
        )

        w1 = worst3.iloc[0]
        b1 = best3.iloc[0]
        est_saving = float(worst3["real_overspend"].clip(lower=0.0).sum())

        summary = (
            f"{mkt}: A&P spend was {fmt_eur(mrow['actual_ap'])} vs {fmt_eur(mrow['budget_ap'])} budget "
            f"and {fmt_eur(mrow['allowance'])} fair allowance ({mrow['overspend_pct']:+.2f}% real variance, "
            f"{fmt_eur(mrow['real_overspend'])}), while Total Sales finished {mrow['sales_vs_plan_pct']:+.2f}% vs plan. "
            f"Justified growth accounted for {fmt_eur(mrow['justified'])} of the raw {fmt_eur(mrow['raw_variance'])} variance; "
            f"monthly anomalies occurred in {spike_text}. "
            f"Biggest drag: {w1['country_name']} {w1['product_unit_name']} ({w1['overspend_pct']:+.1f}% vs allowance); "
            f"top benchmark: {b1['country_name']} {b1['product_unit_name']} ({b1['overspend_pct']:+.1f}%)."
        )
        market_summaries.append({"market": mkt, "summary": summary})

        w_names = ", ".join(f"{r['country_name']} {r['product_unit_name']} ({fmt_eur(r['real_overspend'])})" for _, r in worst3.iterrows())
        strategy_actions.append({
            "market": mkt,
            "action": (
                f"Cap overspend on worst 3 pairs [{w_names}] back to allowance and "
                f"move budget from {w1['country_name']} {w1['product_unit_name']} to "
                f"{b1['country_name']} {b1['product_unit_name']}."
            ),
            "est_saving_eur": clean_float(est_saving, 2),
        })

    # Top-5 global score-maximising action list ranked by EUR impact
    top5_global = (
        pair_agg[pair_agg["real_overspend"] > 0]
        .sort_values("real_overspend", ascending=False)
        .head(5)
    )
    for rank_i, (_, r) in enumerate(top5_global.iterrows(), start=1):
        mkt = r["market"]
        best_in_mkt = pair_agg[(pair_agg["market"] == mkt) & (pair_agg["rank_type"] == "best")].iloc[0]
        driver = "Local A&P" if r["local_share_of_overspend"] >= 0.5 else "Central A&P"
        strategy_actions.append({
            "market": f"Global #{rank_i} ({mkt})",
            "action": (
                f"[{mkt}] Bring {r['country_name']} {r['product_unit_name']} ({r['overspend_pct']:+.1f}% vs allowance, "
                f"driven primarily by {driver}, peak in {MONTH_NAMES[int(r['top_month'])]}) back to fair allowance; "
                f"reallocate growth headroom toward {best_in_mkt['country_name']} {best_in_mkt['product_unit_name']}."
            ),
            "est_saving_eur": clean_float(r["real_overspend"], 2),
        })

    # Global summary
    glob_sales_pct = safe_div(global_sales_actual - global_sales_budget, global_sales_budget) * 100.0
    glob_ov_pct = safe_div(global_real_overspend, global_allowance) * 100.0
    glob_flagged_pm = int((pair_month["confidence"] != "none").sum())
    glob_high_pm = int((pair_month["confidence"] == "high").sum())
    worst_mkt = market_summary_df.sort_values("real_overspend", ascending=False).iloc[0]
    best_mkt = market_summary_df.sort_values("overspend_pct", ascending=True).iloc[0]

    # Monthly global corrected variance to check July or peak month
    glob_monthly = pair_month.groupby("month", as_index=False)[["raw_variance", "real_overspend"]].sum()
    peak_glob_m = glob_monthly.assign(_abs=glob_monthly["real_overspend"].abs()).sort_values("_abs", ascending=False).iloc[0]
    jul_row = glob_monthly[glob_monthly["month"] == 7].iloc[0]

    global_summary = (
        f"Across {len(pair_agg)} market-country-product pairs, actual A&P spend reached {fmt_eur(global_actual)} "
        f"vs {fmt_eur(global_budget)} budget ({ap_pct_of_sales:.2f}% of {fmt_eur(global_sales_actual)} Total Sales; "
        f"sales {glob_sales_pct:+.2f}% vs plan). Naive raw variance of {fmt_eur(global_raw_var)} masks "
        f"{fmt_eur(global_justified)} of sales-justified investment and leaves {fmt_eur(global_real_overspend)} "
        f"({glob_ov_pct:+.2f}% vs allowance) in real overspend across {glob_flagged_pm} flagged pair-month deviations "
        f"({glob_high_pm} high-confidence). {worst_mkt['market']} drove the largest net overspend ({fmt_eur(worst_mkt['real_overspend'])}), "
        f"while {best_mkt['market']} was most efficient ({best_mkt['overspend_pct']:+.2f}% vs allowance). "
        f"Globally, peak monthly corrected variance occurred in {MONTH_NAMES[int(peak_glob_m['month'])]} "
        f"({fmt_eur(peak_glob_m['real_overspend'])}; July={fmt_eur(jul_row['real_overspend'])})."
    )

    # Trust score (deterministic from observed data hygiene)
    deductions = 0.0
    deductions += min(3.0, dup_count * 0.05)          # 28 dupes -> 1.4
    deductions += min(3.0, total_imputed * 0.15)      # 13 imputed -> 1.95
    deductions += min(2.0, sign_fixed_count * 0.25)   # 6 sign fixes -> 1.5
    deductions += min(2.0, n_incomplete * 0.20)       # 8 incomplete combos -> 1.6
    trust_score = round(max(0.0, 100.0 - deductions), 1)

    # Assemble frozen dashboard_data.json
    bridge_list = [
        {
            "market": r["market"],
            "budget": clean_float(r["budget_ap"], 2),
            "justified": clean_float(r["justified"], 2),
            "real_overspend": clean_float(r["real_overspend"], 2),
            "actual": clean_float(r["actual_ap"], 2),
        }
        for _, r in market_summary_df.iterrows()
    ]

    monthly_list = [
        {
            "market": r["market"],
            "month": int(r["month"]),
            "raw_variance": clean_float(r["raw_variance"], 2),
            "corrected_variance": clean_float(r["corrected_variance"], 2),
            "z": clean_float(r["z"], 3),
            "flag": bool(r["flag"]),
            "confidence": r["confidence"],
        }
        for _, r in mkt_month.sort_values(["market", "month"]).iterrows()
    ]

    pairs_list = [
        {
            "market": r["market"],
            "country": r["country_name"],
            "product": r["product_unit_name"],
            "actual": clean_float(r["actual_ap"], 2),
            "budget": clean_float(r["budget_ap"], 2),
            "allowance": clean_float(r["allowance"], 2),
            "real_overspend": clean_float(r["real_overspend"], 2),
            "overspend_pct": clean_float(r["overspend_pct"], 2),
            "z": clean_float(r["z"], 3),
            "percentile": clean_float(r["percentile"], 1),
            "months_flagged": int(r["months_flagged"]),
            "sales_vs_plan_pct": clean_float(r["sales_vs_plan_pct"], 2),
            "spend_vs_budget_pct": clean_float(r["spend_vs_budget_pct"], 2),
            "local_share_of_overspend": clean_float(r["local_share_of_overspend"], 4),
            "top_month": int(r["top_month"]),
            "rank_type": r["rank_type"],
            "commentary": r["commentary"],
        }
        for _, r in pair_agg.sort_values(["market", "overspend_pct"], ascending=[True, False]).iterrows()
    ]

    payload = sanitize_for_json({
        "meta": {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "currency": "EUR",
            "unit_multiplier": UNIT_MULTIPLIER,
            "trust_score": trust_score,
            "rows": {
                "raw": raw_row_count,
                "after_dedupe": after_dedupe_count,
                "clean": len(df),
            },
        },
        "kpis": {
            "actual": clean_float(global_actual, 2),
            "budget": clean_float(global_budget, 2),
            "allowance": clean_float(global_allowance, 2),
            "raw_variance": clean_float(global_raw_var, 2),
            "justified": clean_float(global_justified, 2),
            "real_overspend": clean_float(global_real_overspend, 2),
            "real_overspend_pct_of_spend": clean_float(safe_div(global_real_overspend, global_actual) * 100.0, 2),
            "flagged_deviations": glob_flagged_pm,
        },
        "markets": market_list,
        "bridge": bridge_list,
        "monthly": monthly_list,
        "pairs": pairs_list,
        "market_summaries": market_summaries,
        "global_summary": global_summary,
        "strategy": strategy_actions,
        "quality_checks": quality_checks,
    })

    # -----------------------------------------------------------------------
    # Step 3: Sanity Printout & Assertions
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP 3: SANITY VERIFICATION OUTPUT")
    print("=" * 80)
    print(f"Rows: raw={raw_row_count:,}, after_dedupe={after_dedupe_count:,}, clean(active A&P+Sales)={len(df):,}")
    print(f"Business-reassigned rows: active={n_biz_total:,} | all-4-metrics={all_biz_total:,} "
          f"(flag_only={all_flag_only}, code_only={all_code_only}, overlap={all_both})")
    print(f"Global A&P Actual (EUR, x{UNIT_MULTIPLIER}): {global_actual:,.2f}  ({fmt_eur(global_actual)})")
    print(f"Global A&P Budget (EUR, x{UNIT_MULTIPLIER}): {global_budget:,.2f}  ({fmt_eur(global_budget)})")
    print(f"Global Allowance  (EUR, x{UNIT_MULTIPLIER}): {global_allowance:,.2f}  ({fmt_eur(global_allowance)})")
    print(f"Global Total Sales Actual: {global_sales_actual:,.2f}  ({fmt_eur(global_sales_actual)})")
    print(f"A&P % of Total Sales: {ap_pct_of_sales:.2f}% | Diff from EUR 650M benchmark: {recon_diff_pct*100:.2f}%")
    print(f"Global Raw Variance = {global_raw_var:,.2f} | Justified = {global_justified:,.2f} | "
          f"Real Overspend = {global_real_overspend:,.2f}")
    print("ASSERTION PASSED: raw_variance == justified + real_overspend")
    print("ASSERTION PASSED: sum(market totals) == global total across all metrics")
    print(f"Pair-month flagged deviations: total={glob_flagged_pm} (high={glob_high_pm}, medium={glob_flagged_pm - glob_high_pm})")

    print("\n--- Per-Market Pair Counts & Totals ---")
    for mkt in market_list:
        mrow = market_summary_df[market_summary_df["market"] == mkt].iloc[0]
        sub = pair_agg[pair_agg["market"] == mkt]
        elig_n = int(sub["eligible_for_ranking"].sum())
        print(
            f"  {mkt:25s} | pairs={len(sub):2d} (elig={elig_n:2d}) | "
            f"actual={fmt_eur(mrow['actual_ap']):12s} | allow={fmt_eur(mrow['allowance']):12s} | "
            f"real_ov={fmt_eur(mrow['real_overspend']):12s} ({mrow['overspend_pct']:+6.2f}%)"
        )

    print("\n--- Top-3 BEST & Top-3 WORST per Market ---")
    for mkt in market_list:
        print(f"  [{mkt}]")
        sub = pair_agg[pair_agg["market"] == mkt]
        for rt in ["best", "worst"]:
            asc = (rt == "best")
            grp = sub[sub["rank_type"] == rt].sort_values("overspend_pct", ascending=asc)
            for idx_r, (_, r) in enumerate(grp.iterrows(), start=1):
                print(
                    f"    {rt.upper():5s} #{idx_r}: {r['country_name']:14s} | {r['product_unit_name']:24s} | "
                    f"ov={fmt_eur(r['real_overspend']):11s} ({r['overspend_pct']:+6.2f}%) | "
                    f"sales={r['sales_vs_plan_pct']:+5.1f}% | z={r['z']:+5.2f} | "
                    f"m_flag={int(r['months_flagged'])}"
                )

    print("\n--- Monthly Corrected-Variance Series (per market & flagged months) ---")
    for mkt in market_list:
        msub = mkt_month[mkt_month["market"] == mkt].sort_values("month")
        parts = []
        for _, r in msub.iterrows():
            tag = f"*{r['confidence'][0].upper()}" if r["flag"] else ""
            parts.append(f"{MONTH_NAMES[int(r['month'])]}:{r['corrected_variance']/1e6:+.2f}M(z={r['z']:+.2f}){tag}")
        print(f"  {mkt:25s} -> " + " | ".join(parts))

    print("\n--- Global Monthly Raw vs Corrected Variance ---")
    gm_stats = compute_robust_stats(glob_monthly["real_overspend"])
    for i, (_, r) in enumerate(glob_monthly.sort_values("month").iterrows()):
        m_int = int(r["month"])
        print(
            f"  {MONTH_NAMES[m_int]}: raw={r['raw_variance']/1e6:+7.3f}M | "
            f"corrected={r['real_overspend']/1e6:+7.3f}M | "
            f"z={gm_stats['z'].iloc[i]:+6.2f} | conf={gm_stats['confidence'].iloc[i]}"
        )

    print("\n--- Quality Checks ---")
    for qc in quality_checks:
        print(f"  [{qc['status'].upper():4s}] {qc['check']} (rows={qc['rows_affected']}): {qc['action']}")

    if stop_after_step3:
        print("\n[STOPPED AFTER STEP 3 as requested: no output files written yet.]")
        return payload

    # -----------------------------------------------------------------------
    # Step 4: Write Outputs (JSON + Excel)
    # -----------------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "dashboard_data.json"
    xlsx_out_path = OUTPUT_DIR / "transformed_data.xlsx"

    json_str = json.dumps(payload, indent=2, allow_nan=False)
    json_path.write_text(json_str, encoding="utf-8")

    DASHBOARD_PUBLIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PUBLIC_JSON.write_text(json_str, encoding="utf-8")

    clean_cols = [
        "transaction_id", "market", "market_base", "country_code", "country_name",
        "product_unit_code", "product_unit_name", "company_code", "cost_center_code",
        "sales_channel", "month", "metric_name", "currency_description",
        "local_currency_per_eur", "actual_amount_local_currency", "budget_amount_local_currency",
        "actual_eur", "budget_eur", "imputed", "sign_fixed", "business_reassigned",
    ]
    with pd.ExcelWriter(xlsx_out_path, engine="openpyxl") as writer:
        df[clean_cols].to_excel(writer, sheet_name="clean_data", index=False)
        pair_month.to_excel(writer, sheet_name="pair_month", index=False)
        pair_agg.drop(columns=["_top2_share"]).to_excel(writer, sheet_name="pair_summary", index=False)
        market_summary_df.to_excel(writer, sheet_name="market_summary", index=False)
        pd.DataFrame(quality_checks).to_excel(writer, sheet_name="quality_checks", index=False)

    print(f"\nSTEP 4 COMPLETE: wrote {json_path}, {DASHBOARD_PUBLIC_JSON}, and {xlsx_out_path}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spend Truth Engine pipeline")
    parser.add_argument(
        "--stop-after-step3",
        action="store_true",
        help="Run Steps 1-3, print sanity checks and assertions, and exit before writing files.",
    )
    args = parser.parse_args()
    run_pipeline(stop_after_step3=args.stop_after_step3)
