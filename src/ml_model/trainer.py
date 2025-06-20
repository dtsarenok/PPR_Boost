import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import os
import logging
from typing import Any, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from config.settings import MODELS_PATH, PREDICTOR_MODEL_PATH, FEATURES_LIST

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ModelTrainer:

    def __init__(self):

        logger.info("Initializing ModelTrainer.")

        os.makedirs(MODELS_PATH, exist_ok=True)

    def train_model(self, X: pd.DataFrame, y: pd.Series) -> None:

        if X.empty or y.empty:
            logger.warning("No data provided for model training. Skipping training.")
            return


        missing_features = [feature for feature in FEATURES_LIST if feature not in X.columns]
        if missing_features:
            logger.error(
                f"Missing required features for model training: {missing_features}. "
                f"Expected features: {FEATURES_LIST}. Training skipped."
            )
            return


        X = X[FEATURES_LIST]
        logger.info(f"Training data aligned to required features: {FEATURES_LIST}")

        logger.info(f"Starting model training with {len(X)} samples...")


        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        logger.info(f"Data split: {len(X_train)} training samples, {len(X_test)} test samples.")


        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('logistic_regression', LogisticRegression(
                random_state=42,
                solver='liblinear',
                class_weight='balanced'
            ))
        ])


        pipeline.fit(X_train, y_train)
        logger.info("Model training completed.")


        y_pred = pipeline.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        logger.info("Model evaluation on test data:")
        logger.info(f"  Accuracy (Correct Predictions / Total): {accuracy:.4f}")
        logger.info(f"  Precision (True Positives / All Predicted Positives): {precision:.4f}")
        logger.info(f"  Recall (True Positives / All Actual Positives): {recall:.4f}")
        logger.info(f"  F1-Score (Harmonic Mean of Precision and Recall): {f1:.4f}")


        joblib.dump(pipeline, PREDICTOR_MODEL_PATH)
        logger.info(f"Trained model (pipeline) saved to {PREDICTOR_MODEL_PATH}")
