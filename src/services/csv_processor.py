from pathlib import Path

import pandas as pd

from config.settings import settings
from src.utils.logger import logger


class CSVProcessor:
    """
    Service for processing CSV files and preparing data for the vector database.
    """

    def __init__(self, raw_data_dir: Path = settings.RAW_DATA_DIR):
        """
        Initialize CSV processor.

        Args:
            raw_data_dir: Path to the directory with source CSV files
        """
        self.raw_data_dir = raw_data_dir
        logger.info(f"CSVProcessor initialized. Data directory: {raw_data_dir}")

    def load_csv(self, filename: str, **kwargs) -> pd.DataFrame:
        """
        Load a CSV file with error handling and basic validation.

        Args:
            filename: CSV file name
            **kwargs: Additional parameters for pd.read_csv

        Returns:
            pd.DataFrame: Loaded data
        """
        try:
            file_path = self.raw_data_dir / filename
            logger.info(f"Loading CSV file: {file_path}")

            # Set default parameters for reading CSV
            default_params = {
                "encoding": "utf-8",
                "na_values": ["", "NULL", "null", "NaN", "nan"],
                "low_memory": False,
            }
            # Update parameters with user values
            params = {**default_params, **kwargs}

            df = pd.read_csv(file_path, **params)
            logger.info(f"File {filename} loaded successfully. Size: {len(df)} rows")

            return df

        except Exception as e:
            logger.error(f"Error loading file {filename}: {e!s}")
            raise

    def prepare_data_for_indexing(
        self,
        df: pd.DataFrame,
        text_columns: list[str],
        metadata_columns: list[str] | None = None,
    ) -> list[dict]:
        """
        Prepare data for indexing in the vector database.

        Args:
            df: DataFrame with data
            text_columns: List of columns with text content for indexing
            metadata_columns: List of columns with metadata (optional)

        Returns:
            List[Dict]: List of documents for indexing
        """
        try:
            documents = []

            # Check for required columns
            missing_columns = [
                col for col in text_columns + (metadata_columns or []) if col not in df.columns
            ]
            if missing_columns:
                raise ValueError(f"Missing columns: {missing_columns}")

            # Prepare each data row
            for idx, row in df.iterrows():
                # Combine text content from specified columns
                text_content = " ".join(str(row[col]) for col in text_columns if pd.notna(row[col]))

                # Collect metadata if specified
                metadata = {}
                if metadata_columns:
                    for col in metadata_columns:
                        if col in row and pd.notna(row[col]):
                            # For rule_ids save as string with separator
                            if col == "rule_ids":
                                metadata[col] = ",".join(row[col].split(","))
                            else:
                                metadata[col] = row[col]

                # Add basic metadata
                metadata.update({"document_id": f"doc_{idx}", "source": "csv_import"})

                if text_content.strip():  # Skip empty documents
                    documents.append({"text": text_content, "metadata": metadata})

            logger.info(f"Prepared {len(documents)} documents for indexing")
            return documents

        except Exception as e:
            logger.error(f"Error preparing data: {e!s}")
            raise

    def validate_data(self, df: pd.DataFrame, required_columns: list[str]) -> bool:
        """
        Validate data before processing.

        Args:
            df: DataFrame for validation
            required_columns: List of required columns

        Returns:
            bool: Validation result
        """
        try:
            # Check for required columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")

            # Check for null values in required columns
            null_counts = df[required_columns].isnull().sum()
            columns_with_nulls = null_counts[null_counts > 0]
            if not columns_with_nulls.empty:
                logger.warning(f"Found null values in columns: \n{columns_with_nulls}")

            # Check for duplicates
            duplicates = df.duplicated().sum()
            if duplicates > 0:
                logger.warning(f"Found {duplicates} duplicates")

            return True

        except Exception as e:
            logger.error(f"Data validation error: {e!s}")
            return False

    def clean_text(self, text: str) -> str:
        """
        Basic text cleaning.

        Args:
            text: Original text

        Returns:
            str: Cleaned text
        """
        if pd.isna(text):
            return ""

        # Convert to string
        text = str(text)

        # Basic cleaning
        text = text.strip()
        text = " ".join(text.split())  # Remove extra spaces

        return text

    def process_batch(
        self,
        filename: str,
        text_columns: list[str],
        metadata_columns: list[str] | None = None,
        batch_size: int = 1000,
    ) -> list[dict]:
        """
        Batch process a large CSV file.

        Args:
            filename: CSV file name
            text_columns: Columns with text
            metadata_columns: Columns with metadata
            batch_size: Batch size

        Returns:
            List[Dict]: All processed documents
        """
        try:
            file_path = self.raw_data_dir / filename
            all_documents = []

            # Read file in chunks
            for chunk in pd.read_csv(file_path, chunksize=batch_size):
                # Process each chunk
                documents = self.prepare_data_for_indexing(chunk, text_columns, metadata_columns)
                all_documents.extend(documents)

                logger.info(f"Processed {len(all_documents)} documents")

            return all_documents

        except Exception as e:
            logger.error(f"Error in batch processing: {e!s}")
            raise
