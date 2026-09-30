"""Feature Pipeline: Preprocessing, Stratified Split, and Artifact Persistence.

Governed by:
    D-1.2 (ADR-018): Stratified train/test split holding out test set, with CV
        restricted strictly to the training portion.
    D-1.10 (ADR-024): Elimination of exact duplicate feature column
        (' Current Liability to Liability').
    D-1.11 (ADR-025): Yeo-Johnson transformation fit strictly on training data
        to prevent data leakage, applied across all models.
    D-1.12 (ADR-026): Outliers untouched (explicitly no IQR-based removal or
        winsorization), preserving tail signal for Tier 2/Tier 3.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import joblib
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

from src.config.loader import ProjectParams, load_params
from src.pipelines.feature.transform import YeoJohnsonTransformer
from src.schemas.features import (
    CANONICAL_FEATURES,
    DROPPED_DUPLICATE_FEATURE,
    TARGET_COLUMN,
)


@dataclass(frozen=True)
class SplitArtifacts:
    """Container holding preprocessed train/test partitions and metadata."""

    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    transformer: YeoJohnsonTransformer
    train_positive_ratio: float
    test_positive_ratio: float
    fold_positive_ratios: list[float]



def prepare_and_split_data(
    raw_data_path: str | Path = "data/raw/data.csv",
    params: ProjectParams | None = None,
    output_dir: str | Path | None = "data/processed",
    artifact_dir: str | Path | None = "artifacts",
) -> SplitArtifacts:
    """Load raw data, apply canonical feature schema, stratify split, and transform.

    This function represents the Stage 2 Feature Pipeline:
    1. Loads raw dataset and validates target column presence.
    2. Enforces canonical 94-feature schema (drops duplicate column).
    3. Performs stratified split holding out test portion completely.
    4. Fits YeoJohnsonTransformer on X_train ONLY (strictly preventing leakage).
    5. Transforms both X_train and X_test.
    6. Ensures zero outlier removal or winsorization takes place (D-1.12/ADR-026).
    7. Optionally persists outputs to disk.

    Args:
        raw_data_path: Path to raw dataset CSV file.
        params: Validated project parameters from params.yaml.
        output_dir: Directory where processed parquet files will be stored.
        artifact_dir: Directory where fitted transformer joblib bundle will be stored.

    Returns:
        SplitArtifacts with transformed datasets, fitted transformer, and ratios.
    """
    if params is None:
        params = load_params()

    raw_path = Path(raw_data_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw data file not found at: {raw_path}")

    # Load dataset
    df = pd.read_csv(raw_path)

    # Validate target presence
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Missing target column '{TARGET_COLUMN}' in dataset.")

    # Explicitly enforce removal of duplicate feature (ADR-024)
    # The canonical feature list already excludes DROPPED_DUPLICATE_FEATURE.
    assert DROPPED_DUPLICATE_FEATURE not in CANONICAL_FEATURES

    # Missing column check
    missing_cols = [col for col in CANONICAL_FEATURES if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Dataset is missing {len(missing_cols)} canonical features: {missing_cols[:5]}"
        )

    # Extract X (canonical features only) and y (target)
    X = cast(pd.DataFrame, df[list(CANONICAL_FEATURES)].copy())
    y = cast(pd.Series, df[TARGET_COLUMN].copy())

    # Stratified Train/Test Split (ADR-018)
    # Test set is held out and remains completely untouched
    split_res = train_test_split(
        X,
        y,
        test_size=params.split.test_size,
        stratify=y if params.split.stratify else None,
        random_state=params.seed,
    )
    X_train_raw = cast(pd.DataFrame, split_res[0])
    X_test_raw = cast(pd.DataFrame, split_res[1])
    y_train = cast(pd.Series, split_res[2])
    y_test = cast(pd.Series, split_res[3])

    # Calculate class ratios for validation/falsification
    train_positive_ratio = float(y_train.mean())
    test_positive_ratio = float(y_test.mean())

    # Compute CV fold positive ratios within training split (ADR-018)
    skf = StratifiedKFold(
        n_splits=params.cv.n_splits,
        shuffle=params.cv.shuffle,
        random_state=params.seed,
    )
    fold_positive_ratios: list[float] = []
    for _, val_idx in skf.split(X_train_raw, y_train):
        fold_ratio = float(y_train.iloc[val_idx].mean())
        fold_positive_ratios.append(fold_ratio)

    # Fit Yeo-Johnson on X_train ONLY (ADR-025)
    transformer = YeoJohnsonTransformer(
        standardize=params.preprocessing.standardize,
        feature_names=CANONICAL_FEATURES,
    )
    transformer.fit(X_train_raw)

    # Transform both splits using parameters learned strictly on X_train
    X_train_transformed = transformer.transform(X_train_raw)
    X_test_transformed = transformer.transform(X_test_raw)

    # Note on ADR-026: Outliers are intentionally untouched. Zero rows or values removed.
    assert len(X_train_transformed) == len(X_train_raw)
    assert len(X_test_transformed) == len(X_test_raw)

    # Persist artifacts if directories are specified
    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        X_train_transformed.to_parquet(out_path / "X_train.parquet")
        X_test_transformed.to_parquet(out_path / "X_test.parquet")
        pd.DataFrame(y_train).to_parquet(out_path / "y_train.parquet")
        pd.DataFrame(y_test).to_parquet(out_path / "y_test.parquet")

    if artifact_dir is not None:
        art_path = Path(artifact_dir)
        art_path.mkdir(parents=True, exist_ok=True)
        transformer_file = art_path / "preprocessor.joblib"
        joblib.dump(transformer, transformer_file)

    return SplitArtifacts(
        X_train=X_train_transformed,
        X_test=X_test_transformed,
        y_train=y_train,
        y_test=y_test,
        transformer=transformer,
        train_positive_ratio=train_positive_ratio,
        test_positive_ratio=test_positive_ratio,
        fold_positive_ratios=fold_positive_ratios,
    )


def load_processed_data(
    processed_dir: str | Path = "data/processed",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Load previously persisted processed feature sets.

    Args:
        processed_dir: Directory containing processed parquet files.

    Returns:
        Tuple of (X_train, X_test, y_train, y_test).
    """
    proc_path = Path(processed_dir)
    x_train_path = proc_path / "X_train.parquet"
    x_test_path = proc_path / "X_test.parquet"
    y_train_path = proc_path / "y_train.parquet"
    y_test_path = proc_path / "y_test.parquet"

    for p in (x_train_path, x_test_path, y_train_path, y_test_path):
        if not p.exists():
            raise FileNotFoundError(f"Processed file missing: {p}")

    X_train = cast(pd.DataFrame, pd.read_parquet(x_train_path))
    X_test = cast(pd.DataFrame, pd.read_parquet(x_test_path))
    y_train = cast(pd.Series, pd.read_parquet(y_train_path).iloc[:, 0])
    y_test = cast(pd.Series, pd.read_parquet(y_test_path).iloc[:, 0])

    return X_train, X_test, y_train, y_test


def load_transformer(
    artifact_path: str | Path = "artifacts/preprocessor.joblib",
) -> YeoJohnsonTransformer:
    """Load fitted YeoJohnsonTransformer artifact.

    Args:
        artifact_path: Path to serialized joblib transformer.

    Returns:
        Fitted YeoJohnsonTransformer instance.
    """
    art_path = Path(artifact_path)
    if not art_path.exists():
        raise FileNotFoundError(f"Transformer artifact not found at: {art_path}")

    loaded: Any = joblib.load(art_path)
    if not isinstance(loaded, YeoJohnsonTransformer):
        raise TypeError(f"Expected YeoJohnsonTransformer, got {type(loaded).__name__}")
    return loaded


def main() -> None:
    """CLI entrypoint for running the feature split pipeline."""
    parser = argparse.ArgumentParser(description="ACRAS Stage 2: Feature Pipeline & Split")
    parser.add_argument(
        "--raw-data",
        default="data/raw/data.csv",
        help="Path to raw dataset CSV (default: data/raw/data.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory to save preprocessed parquet files (default: data/processed)",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts",
        help="Directory to save transformer joblib artifact (default: artifacts)",
    )
    args = parser.parse_args()

    print(f"[feature_pipeline] Starting Feature Pipeline using raw data: {args.raw_data}")
    try:
        artifacts = prepare_and_split_data(
            raw_data_path=args.raw_data,
            output_dir=args.output_dir,
            artifact_dir=args.artifact_dir,
        )
    except Exception as exc:
        print(f"[feature_pipeline] ERROR: Pipeline execution failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[feature_pipeline] Success! Preprocessed partitions saved to: {args.output_dir}\n"
        f"  - X_train shape: {artifacts.X_train.shape} | "
        f"Positive ratio: {artifacts.train_positive_ratio:.4%}\n"
        f"  - X_test shape:  {artifacts.X_test.shape} | "
        f"Positive ratio: {artifacts.test_positive_ratio:.4%}\n"
        f"  - CV folds positive ratios: {[round(r, 4) for r in artifacts.fold_positive_ratios]}\n"
        f"  - Transformer saved to: {args.artifact_dir}/preprocessor.joblib"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

