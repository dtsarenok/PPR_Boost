import os
import pickle
import logging
from typing import Any

from config.settings import MODELS_PATH, MODEL_FILENAME

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ModelLoader:

    def __init__(self):

        self.model: Any = None
        self.model_path: str = os.path.join(MODELS_PATH, MODEL_FILENAME)
        logger.info(f"ModelLoader initialized. Expected model path: {self.model_path}")

    def load_model(self) -> Any:

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found at: {self.model_path}")
            raise FileNotFoundError(f"Model file not found: {self.model_path}. Please train the model first.")

        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            logger.info(f"Model successfully loaded from {self.model_path}")
            return self.model
        except Exception as e:
            logger.error(f"Error loading model from {self.model_path}: {e}", exc_info=True)
            self.model = None
            raise

    def get_model(self) -> Any:

        if self.model is None:
            logger.info("Model not yet loaded. Attempting to load now...")
            self.load_model()
        return self.model



if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    import random


    os.makedirs(MODELS_PATH, exist_ok=True)


    class MockModel:
        def predict_proba(self, X: pd.DataFrame) -> List[List[float]]:
            logger.info(f"MockModel: predict_proba called with {len(X)} samples.")

            return [[random.uniform(0.1, 0.9), random.uniform(0.1, 0.9)] for _ in range(len(X))]

        def predict(self, X: pd.DataFrame) -> List[int]:
            logger.info(f"MockModel: predict called with {len(X)} samples.")

            return [random.randint(0, 1) for _ in range(len(X))]

    mock_model_instance = MockModel()
    mock_model_path = os.path.join(MODELS_PATH, MODEL_FILENAME)

    try:

        with open(mock_model_path, 'wb') as f:
            pickle.dump(mock_model_instance, f)
        logger.info(f"Mock model saved for testing at: {mock_model_path}")


        loader = ModelLoader()
        loaded_model = loader.get_model()

        if loaded_model:
            logger.info("Testing: Model successfully loaded.")
            import pandas as pd
            from typing import List

            test_data = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
            probabilities = loaded_model.predict_proba(test_data)
            logger.info(f"Predicted probabilities: {probabilities}")
            predictions = loaded_model.predict(test_data)
            logger.info(f"Predicted classes: {predictions}")
        else:
            logger.error("Testing: Model was not loaded, something went wrong.")


        logger.info("\n--- Testing FileNotFoundError handling ---")
        temp_loader = ModelLoader()
        temp_loader.model_path = os.path.join(MODELS_PATH, "non_existent_model.pkl")
        try:
            temp_loader.load_model()
        except FileNotFoundError as fnfe:
            logger.info(f"Caught expected error: {fnfe}")
        except Exception as e:
            logger.error(f"Caught unexpected error: {e}")


    except Exception as e:
        logger.exception(f"An error occurred during test model saving/loading: {e}")
    finally:
        if os.path.exists(mock_model_path):
            os.remove(mock_model_path)
            logger.info(f"Mock model removed: {mock_model_path}")