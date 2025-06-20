import pandas as pd
import joblib
import os
import logging
from typing import Any, List

from config.settings import PREDICTOR_MODEL_PATH, FEATURES_LIST

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ModelPredictor:

    def __init__(self):

        self.model: Any = None
        self._load_model()

    def _load_model(self):

        if not os.path.exists(PREDICTOR_MODEL_PATH):
            logger.error(f"Model file not found at expected path: {PREDICTOR_MODEL_PATH}. "
                         "Please ensure the model has been trained and saved.")
            raise FileNotFoundError(f"Model not found: {PREDICTOR_MODEL_PATH}")
        try:
            self.model = joblib.load(PREDICTOR_MODEL_PATH)
            logger.info(f"Model successfully loaded from {PREDICTOR_MODEL_PATH}")
        except Exception as e:
            logger.exception(f"Error loading model from {PREDICTOR_MODEL_PATH}: {e}")
            self.model = None
            raise

    def predict_probability(self, features_df: pd.DataFrame) -> pd.Series:

        if self.model is None:
            logger.critical("Prediction attempted but model is not loaded.")
            raise RuntimeError("Model is not loaded. Cannot make prediction.")


        missing_features: List[str] = [col for col in FEATURES_LIST if col not in features_df.columns]
        if missing_features:
            logger.error(f"Missing required features for prediction: {missing_features}. "
                         f"Expected features: {FEATURES_LIST}. Received: {list(features_df.columns)}")
            raise ValueError(f"Missing required features for prediction: {missing_features}")


        features_df_ordered = features_df[FEATURES_LIST]
        logger.debug(f"Features reordered for prediction: {FEATURES_LIST}")


        probabilities = self.model.predict_proba(features_df_ordered)[:, 1]
        logger.info(f"Successfully predicted probabilities for {len(features_df)} samples.")
        return pd.Series(probabilities, index=features_df.index)