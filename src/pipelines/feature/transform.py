"""Yeo-Johnson Feature Transformation Module.

Governed by:
    D-1.11 (ADR-025): Yeo-Johnson power transformation applied as a shared preprocessing
        step feeding all three candidate models. Supports both positive and negative values
        without data deletion (honoring D-1.12 / ADR-026: no outlier removal).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import PowerTransformer

from src.schemas.features import CANONICAL_FEATURES, DROPPED_DUPLICATE_FEATURE


class YeoJohnsonTransformer(BaseEstimator, TransformerMixin):
    """Clean Yeo-Johnson power transformer wrapper.

    Applies scikit-learn's PowerTransformer(method='yeo-johnson') to canonical
    features while ensuring that column names, ordering, and data integrity
    are rigorously preserved across pandas DataFrame and numpy ndarray interfaces.
    """

    def __init__(
        self,
        standardize: bool = True,
        feature_names: tuple[str, ...] | list[str] = CANONICAL_FEATURES,
    ) -> None:
        """Initialize the transformer.

        Args:
            standardize: Whether to apply zero-mean, unit-variance normalization.
            feature_names: Expected feature columns (defaults to CANONICAL_FEATURES).
        """
        self.standardize = standardize
        self.feature_names = list(feature_names)
        self.pt = PowerTransformer(method="yeo-johnson", standardize=self.standardize)
        self._is_fitted = False

    def fit(self, X: pd.DataFrame | np.ndarray, y: Any = None) -> YeoJohnsonTransformer:
        """Fit the Yeo-Johnson transformation parameters (lambdas, mean, scale).

        Args:
            X: Input dataframe or 2D array of shape (n_samples, n_features).
            y: Ignored (present for scikit-learn API compatibility).

        Returns:
            Fitted transformer instance.
        """
        df = self._validate_and_format_input(X)
        self.pt.fit(df.values)
        self._is_fitted = True
        return self

    def transform(self, X: pd.DataFrame | np.ndarray) -> pd.DataFrame:
        """Transform features using fitted Yeo-Johnson parameters.

        Args:
            X: Input dataframe or 2D array of shape (n_samples, n_features).

        Returns:
            Transformed pandas DataFrame with original canonical feature names.
        """
        if not self._is_fitted:
            raise RuntimeError("YeoJohnsonTransformer must be fitted before calling transform().")

        df = self._validate_and_format_input(X)
        transformed_arr = self.pt.transform(df.values)
        return pd.DataFrame(transformed_arr, columns=pd.Index(self.feature_names), index=df.index)

    def fit_transform(
        self, X: pd.DataFrame | np.ndarray, y: Any = None, **fit_params: Any
    ) -> pd.DataFrame:
        """Fit to data, then transform it.

        Args:
            X: Input dataframe or 2D array of shape (n_samples, n_features).
            y: Ignored.
            **fit_params: Additional fitting parameters.

        Returns:
            Transformed pandas DataFrame with original canonical feature names.
        """
        return self.fit(X, y).transform(X)

    def _validate_and_format_input(self, X: pd.DataFrame | np.ndarray) -> pd.DataFrame:
        """Validate feature presence and align column ordering."""
        if isinstance(X, pd.DataFrame):
            # Check for the dropped duplicate feature
            if DROPPED_DUPLICATE_FEATURE in X.columns:
                raise ValueError(
                    f"Forbidden duplicate column '{DROPPED_DUPLICATE_FEATURE}' found in "
                    "input data. Data must be filtered against canonical features "
                    "(D-1.10 / ADR-024)."
                )

            # Check for missing expected features
            missing = [col for col in self.feature_names if col not in X.columns]
            if missing:
                raise ValueError(
                    f"Input DataFrame is missing {len(missing)} canonical features: "
                    f"{missing[:5]}..."
                )

            subset = X[self.feature_names]
            assert isinstance(subset, pd.DataFrame)
            return subset.copy()

        elif isinstance(X, np.ndarray):
            if X.ndim != 2:
                raise ValueError(f"Expected 2D array, got shape {X.shape}")
            if X.shape[1] != len(self.feature_names):
                raise ValueError(
                    f"Expected {len(self.feature_names)} features, got array with "
                    f"{X.shape[1]} columns."
                )
            return pd.DataFrame(X, columns=pd.Index(self.feature_names))

        else:
            raise TypeError(
                f"Unsupported input type: {type(X).__name__}. Expected DataFrame or ndarray."
            )
