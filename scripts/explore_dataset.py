"""
ACRAS — Phase 1 Dataset Exploration
====================================
Dataset : data/raw/data.csv  (Taiwan Bankruptcy Dataset)
Target  : Bankrupt?  (binary, 0 = solvent, 1 = bankrupt)

Run from repo root:
    uv run python scripts/explore_dataset.py

Outputs (saved to reports/eda/):
    summary_stats.csv        — describe() on all 95 features + target
    class_imbalance.png      — target distribution bar chart
    missingness.png          — heatmap of null values
    correlation_heatmap.png  — top-N feature Pearson correlation matrix
    top_features_boxplot.png — box-plots of top features vs. target
    outlier_report.csv       — IQR-based outlier counts per feature
    feature_importance.png   — Random-Forest permutation importance (quick proxy)
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")  # headless — no display required

# ── repo root on sys.path so relative imports work when called from scripts/ ──
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
DATA_PATH   = REPO_ROOT / "data" / "raw" / "data.csv"
OUTPUT_DIR  = REPO_ROOT / "reports" / "eda"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COL  = "Bankrupt?"
TOP_N_CORR  = 30          # features shown in correlation heatmap
TOP_N_BOX   = 10          # features shown in box-plots
RF_TREES    = 100         # quick proxy RF for importance ranking
RANDOM_SEED = 42

PALETTE = {
    "solvent":   "#4A90D9",
    "bankrupt":  "#E05C5C",
    "neutral":   "#7F8C8D",
    "accent":    "#F39C12",
    "bg":        "#1C1C2E",
    "text":      "#ECF0F1",
}

plt.rcParams.update({
    "figure.facecolor":  PALETTE["bg"],
    "axes.facecolor":    "#252540",
    "axes.edgecolor":    PALETTE["neutral"],
    "axes.labelcolor":   PALETTE["text"],
    "xtick.color":       PALETTE["text"],
    "ytick.color":       PALETTE["text"],
    "text.color":        PALETTE["text"],
    "grid.color":        "#3A3A5C",
    "grid.linestyle":    "--",
    "grid.alpha":        0.4,
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
})

# ─────────────────────────────────────────────────────────────────────────────
# 1. Load & basic sanity
# ─────────────────────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    print(f"\n{'='*60}")
    print(" ACRAS — Dataset Exploration")
    print(f"{'='*60}")
    df = pd.read_csv(DATA_PATH)
    # Strip leading/trailing whitespace from column names (common in this dataset)
    df.columns = df.columns.str.strip()
    print(f"\n[1] Data loaded: {df.shape[0]:,} rows x {df.shape[1]} columns")
    return df


def basic_info(df: pd.DataFrame) -> None:
    print("\n[2] Basic Info")
    print(f"    Target column  : {TARGET_COL}")
    print(f"    Feature columns: {df.shape[1] - 1}")
    print(f"    Dtypes         :\n{df.dtypes.value_counts().to_string()}")

    null_totals = df.isnull().sum()
    null_cols   = (null_totals > 0).sum()
    print(f"    Columns with nulls: {null_cols}")
    if null_cols:
        print(null_totals[null_totals > 0].to_string())
    else:
        print("    No missing values detected.")

    # Summary stats — saved to CSV
    stats = df.describe(percentiles=[0.05, 0.25, 0.50, 0.75, 0.95]).T
    stats["skewness"] = df.skew(numeric_only=True)
    stats["kurtosis"] = df.kurtosis(numeric_only=True)
    out_path = OUTPUT_DIR / "summary_stats.csv"
    stats.to_csv(out_path)
    print(f"\n    -> Summary stats saved: {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Class imbalance
# ─────────────────────────────────────────────────────────────────────────────
def plot_class_imbalance(df: pd.DataFrame) -> None:
    counts = df[TARGET_COL].value_counts()
    labels = ["Solvent (0)", "Bankrupt (1)"]
    colors = [PALETTE["solvent"], PALETTE["bankrupt"]]
    pct    = counts / counts.sum() * 100

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Class Distribution — Bankrupt?", fontsize=15, fontweight="bold", y=1.02)

    # Bar chart
    bars = axes[0].bar(labels, counts.values, color=colors, width=0.45,
                       edgecolor="white", linewidth=0.6)
    for bar, cnt, p in zip(bars, counts.values, pct.values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 40,
                     f"{cnt:,}\n({p:.1f}%)", ha="center", va="bottom", fontsize=11)
    axes[0].set_ylabel("Count")
    axes[0].set_title("Absolute Counts")
    axes[0].set_ylim(0, counts.max() * 1.2)
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    axes[0].grid(axis="y")

    # Pie chart
    wedges, texts, autotexts = axes[1].pie(
        counts.values, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=140,
        wedgeprops={"edgecolor": "white", "linewidth": 0.8},
        textprops={"color": PALETTE["text"]},
    )
    for at in autotexts:
        at.set_fontsize(12)
    axes[1].set_title("Proportion")

    plt.tight_layout()
    out = OUTPUT_DIR / "class_imbalance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=PALETTE["bg"])
    plt.close(fig)

    ratio = counts[0] / counts[1]
    print("\n[3] Class Imbalance")
    print(f"    Solvent  : {counts[0]:,} ({pct[0]:.1f}%)")
    print(f"    Bankrupt : {counts[1]:,} ({pct[1]:.1f}%)")
    print(f"    Imbalance ratio: {ratio:.1f}:1  -> SMOTE / class-weight adjustment required")
    print(f"    -> Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Missingness heatmap
# ─────────────────────────────────────────────────────────────────────────────
def plot_missingness(df: pd.DataFrame) -> None:
    null_pct = df.isnull().mean() * 100
    missing = null_pct[null_pct > 0].sort_values(ascending=False)  # type: ignore

    if missing.empty:
        print("\n[4] Missingness: No missing values — heatmap skipped.")
        (OUTPUT_DIR / "missingness_NONE.txt").write_text("No missing values in this dataset.\n")
        return

    fig, ax = plt.subplots(figsize=(max(10, len(missing) * 0.4), 5))
    colors_bar = [
        PALETTE["bankrupt"] if v > 10 else PALETTE["accent"] if v > 1 else PALETTE["solvent"]
        for v in missing.values
    ]
    ax.bar(range(len(missing)), missing.values, color=colors_bar, edgecolor="white", linewidth=0.4)
    ax.set_xticks(range(len(missing)))
    ax.set_xticklabels(missing.index, rotation=90, fontsize=8)
    ax.set_ylabel("Missing %")
    ax.set_title("Missing Value Rate per Column")
    ax.axhline(5, color=PALETTE["accent"], linestyle="--", linewidth=0.8, label="> 5% threshold")
    ax.legend()
    plt.tight_layout()
    out = OUTPUT_DIR / "missingness.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=PALETTE["bg"])
    plt.close(fig)
    print(f"\n[4] Missingness -> Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Correlation heatmap (top N features by variance)
# ─────────────────────────────────────────────────────────────────────────────
def plot_correlation(df: pd.DataFrame) -> None:
    features = df.drop(columns=[TARGET_COL])
    # Select top-N highest-variance features for readability
    top_cols = features.var().nlargest(TOP_N_CORR).index.tolist()  # type: ignore
    corr = features[top_cols].corr()  # type: ignore

    fig, ax = plt.subplots(figsize=(16, 14))
    mask = np.triu(np.ones_like(corr, dtype=bool))
    cmap = sns.diverging_palette(220, 20, as_cmap=True)
    sns.heatmap(
        corr, mask=mask, cmap=cmap, center=0,
        annot=False, linewidths=0.3, linecolor="#252540",
        cbar_kws={"shrink": 0.8, "label": "Pearson r"},
        ax=ax,
    )
    ax.set_title(f"Correlation Matrix — Top {TOP_N_CORR} Features by Variance", pad=14)
    plt.xticks(rotation=45, ha="right", fontsize=7)
    plt.yticks(fontsize=7)
    plt.tight_layout()
    out = OUTPUT_DIR / "correlation_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=PALETTE["bg"])
    plt.close(fig)

    # Highly correlated pairs report
    corr_abs  = corr.abs()
    upper     = corr_abs.where(~mask)  # type: ignore
    high_pairs = (
        upper.stack()
             .reset_index()
             .rename(columns={"level_0": "feature_a", "level_1": "feature_b", 0: "abs_r"})
             .query("abs_r > 0.90")
             .sort_values("abs_r", ascending=False)
    )
    n_high = len(high_pairs)
    print("\n[5] Correlation Heatmap")
    print(f"    Highly correlated pairs (|r| > 0.90): {n_high}")
    if n_high:
        print(high_pairs.head(10).to_string(index=False))
    print(f"    -> Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Feature importance (quick Random Forest proxy)
# ─────────────────────────────────────────────────────────────────────────────
def plot_feature_importance(df: pd.DataFrame) -> pd.Index:
    print(f"\n[6] Feature Importance (Random Forest proxy — {RF_TREES} trees)")

    X            = df.drop(columns=[TARGET_COL]).values
    y            = df[TARGET_COL].values
    feature_names = df.drop(columns=[TARGET_COL]).columns

    # Stratified 70/30 split to keep it fast
    sss = StratifiedShuffleSplit(n_splits=1, test_size=0.30, random_state=RANDOM_SEED)
    train_idx, test_idx = next(sss.split(X, y))
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    scaler  = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    rf = RandomForestClassifier(
        n_estimators=RF_TREES,
        class_weight="balanced",
        max_depth=10,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)

    # Permutation importance on test set (more reliable than MDI)
    pi = permutation_importance(  # type: ignore
        rf, X_test, y_test,
        n_repeats=5, random_state=RANDOM_SEED, n_jobs=-1, scoring="roc_auc",
    )
    imp_df = (
        pd.DataFrame({
            "feature":    feature_names,
            "importance": pi.importances_mean,  # type: ignore
            "std":        pi.importances_std,   # type: ignore
        })
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    top_n    = TOP_N_BOX * 2
    top_plot = imp_df.head(top_n)

    fig, ax = plt.subplots(figsize=(12, max(6, top_n * 0.55)))
    ax.barh(
        top_plot["feature"][::-1],
        top_plot["importance"][::-1],
        xerr=top_plot["std"][::-1],
        color=PALETTE["accent"],
        edgecolor="white",
        linewidth=0.4,
        error_kw={"ecolor": PALETTE["neutral"], "capsize": 3},
    )
    ax.set_xlabel("Permutation Importance (delta AUC)")
    ax.set_title(f"Top {top_n} Features — Permutation Importance (RF proxy)")
    ax.axvline(0, color=PALETTE["neutral"], linewidth=0.8)
    plt.tight_layout()
    out = OUTPUT_DIR / "feature_importance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=PALETTE["bg"])
    plt.close(fig)

    top_features = imp_df.head(TOP_N_BOX)["feature"]
    print(f"    Top 5 features: {top_features.tolist()[:5]}")
    print(f"    -> Saved: {out}")
    return top_features  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# 6. Box-plots: top features vs. target
# ─────────────────────────────────────────────────────────────────────────────
def plot_top_feature_boxplots(df: pd.DataFrame, top_features: pd.Index) -> None:
    cols  = list(top_features[:TOP_N_BOX])
    ncols = 2
    nrows = int(np.ceil(len(cols) / ncols))

    fig, axes = plt.subplots(nrows, ncols, figsize=(16, nrows * 4))
    axes = axes.flatten()

    for i, col in enumerate(cols):
        ax       = axes[i]
        solvent  = df.loc[df[TARGET_COL] == 0, col].dropna()
        bankrupt = df.loc[df[TARGET_COL] == 1, col].dropna()

        bp = ax.boxplot(
            [solvent, bankrupt],
            patch_artist=True,
            notch=True,
            widths=0.4,
            medianprops={"color": "white", "linewidth": 1.5},
            whiskerprops={"color": PALETTE["neutral"]},
            capprops={"color": PALETTE["neutral"]},
            flierprops={"marker": "o", "markersize": 2, "alpha": 0.3, "markeredgewidth": 0},
        )
        bp["boxes"][0].set(facecolor=PALETTE["solvent"], alpha=0.75)
        bp["boxes"][1].set(facecolor=PALETTE["bankrupt"], alpha=0.75)

        ax.set_title(col[:55] + ("..." if len(col) > 55 else ""), fontsize=9)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Solvent", "Bankrupt"], fontsize=9)
        ax.grid(axis="y")

    for j in range(len(cols), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(
        f"Top {TOP_N_BOX} Features — Distribution by Bankruptcy Status",
        fontsize=13, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    out = OUTPUT_DIR / "top_features_boxplot.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=PALETTE["bg"])
    plt.close(fig)
    print(f"\n[7] Box-plots saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. IQR-based outlier report
# ─────────────────────────────────────────────────────────────────────────────
def outlier_report(df: pd.DataFrame) -> None:
    features = df.drop(columns=[TARGET_COL])
    Q1  = features.quantile(0.25)
    Q3  = features.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    outlier_counts = ((features < lower) | (features > upper)).sum()
    outlier_pct    = outlier_counts / len(df) * 100

    report = (
        pd.DataFrame({"outlier_count": outlier_counts, "outlier_pct": outlier_pct.round(2)})
        .sort_values("outlier_pct", ascending=False)
    )

    out = OUTPUT_DIR / "outlier_report.csv"
    report.to_csv(out)

    print("\n[8] Outlier Report (IQR x 1.5 rule)")
    print(f"    Features with > 5% outliers: {(outlier_pct > 5).sum()}")
    print("    Top 5 most affected features:")
    print(report.head(5).to_string())
    print(f"    -> Full report: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Summary printout with ACRAS-specific notes
# ─────────────────────────────────────────────────────────────────────────────
def print_summary(df: pd.DataFrame) -> None:
    features = df.drop(columns=[TARGET_COL])
    skewed   = (features.skew().abs() > 2).sum()  # type: ignore

    print(f"\n{'='*60}")
    print(" EDA Complete — Summary")
    print(f"{'='*60}")
    print(f"  Rows              : {len(df):,}")
    print(f"  Features          : {features.shape[1]}")
    print(f"  Target            : {TARGET_COL}")
    print(f"  Bankrupt rate     : {df[TARGET_COL].mean()*100:.2f}%")
    print(f"  Missing values    : {df.isnull().sum().sum()}")
    print(f"  Highly skewed (|skew| > 2): {skewed} features")
    print(f"\n  All outputs saved to: {OUTPUT_DIR.resolve()}")
    print("\n  Key findings for ACRAS Tier 1 (PD model):")
    print("    - Severe class imbalance (~3.2% bankrupt) -> use SMOTE + class_weight='balanced'")
    print(f"    - {skewed} features are heavily skewed -> consider log/Yeo-Johnson transforms")
    print("    - High inter-feature correlation expected -> consider VIF filtering or PCA")
    print("    - No missing values -> no imputation needed at this stage")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    df = load_data()
    basic_info(df)
    plot_class_imbalance(df)
    plot_missingness(df)
    plot_correlation(df)
    top_features = plot_feature_importance(df)
    plot_top_feature_boxplots(df, top_features)
    outlier_report(df)
    print_summary(df)


if __name__ == "__main__":
    main()
