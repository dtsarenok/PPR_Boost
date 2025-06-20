import pandas as pd
import logging

from src.database.db_manager import DBManager


logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

class SMEFilter:

    def __init__(self, db_manager: DBManager):

        self.db_manager = db_manager
        logger.info("SMEFilter initialized.")

    def filter_tenders_by_sme(self, tenders_df: pd.DataFrame) -> pd.DataFrame:

        logger.info("2. Applying SME exclusion filter to tenders...")

        if 'is_sme' not in tenders_df.columns:
            logger.warning("Column 'is_sme' not found in the DataFrame. SME filtering skipped.")
            return tenders_df

        filtered_df = tenders_df[tenders_df['is_sme'] == False].copy()

        logger.info(f"Tenders remaining after SME exclusion filter: {len(filtered_df)}")
        return filtered_df