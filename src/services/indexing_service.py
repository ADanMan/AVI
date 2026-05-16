"""Service for loading structured CSV data into the vector database."""

import time
import pandas as pd
from fastapi import HTTPException
from pathlib import Path

from config.settings import directory_manager, settings
from src.models.schemas import FilteredContent, IndexingStatus
from src.services.indexing_state import indexing_state
from src.services.vector_db import VectorDBClient, VectorDBService
from src.monitoring.metrics import content_filter_metrics
from src.utils.logger import logger


class IndexingService:
    def __init__(self, vector_db: VectorDBClient | None = None):
        self.vector_db = vector_db or VectorDBService()

    def validate_links_csv(self, df: pd.DataFrame) -> list[str]:
        """
        Validate the structure and content of a links CSV DataFrame.
        Args:
            df: Pandas DataFrame with columns 'rule_id' and 'document_id'.
        Returns:
            List of error messages (empty if valid).
        """
        errors = []
        required_columns = {"rule_id", "document_id"}
        if not required_columns.issubset(df.columns):
            missing = required_columns - set(df.columns)
            errors.append(f"Missing columns: {list(missing)}")
        # Check for duplicate links
        duplicates = df.duplicated(subset=["rule_id", "document_id"])
        if duplicates.any():
            errors.append("Duplicate rule_id/document_id pairs found.")
        return errors

    async def reindex_all(self, skip_export: bool = False) -> dict:
        """
        Rebuild rule, document, and link collections from the source CSV files.

        Args:
            skip_export: If True, skips exporting current data before reindexing.
                        Use this when CSV files are already up-to-date (e.g., just uploaded).
        """
        start_time = time.perf_counter()
        items_processed = {"rules": 0, "documents": 0, "links": 0}
        status = "success"

        try:
            # Ensure RAW_DATA_DIR exists
            directory_manager.ensure_directory(settings.RAW_DATA_DIR)

            # Export current data before reindexing to prevent data loss
            # Skip if we just uploaded new CSV files
            if not skip_export:
                # Check if database has any data before exporting
                # This prevents overwriting source CSV files with empty exports on first run
                try:
                    existing_rules = await self.vector_db.get_all_rules()
                    existing_docs = await self.vector_db.get_all_documents()
                    has_data = bool(existing_rules) or bool(existing_docs)
                except Exception:
                    has_data = False

                if has_data:
                    logger.info("Exporting current data before reindexing...")
                    try:
                        await self.export_to_csv()
                        logger.info("Current data exported successfully")
                    except Exception as export_error:
                        logger.warning(f"Failed to export current data: {export_error}")
                else:
                    logger.info("Database is empty - skipping export to preserve source CSV files")
            else:
                logger.info("Skipping export step - using provided CSV files directly")

            # Load CSV files
            rules_path = settings.RAW_DATA_DIR / "filter_rules.csv"
            docs_path = settings.RAW_DATA_DIR / "vector_documents.csv"
            links_path = settings.RAW_DATA_DIR / "links.csv"

            # Check if CSV files exist
            if not rules_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Rules CSV file not found: {rules_path}. Please upload CSV files first using /api/v1/upload/csv endpoint."
                )
            if not docs_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Documents CSV file not found: {docs_path}. Please upload CSV files first using /api/v1/upload/csv endpoint."
                )

            rules_df = pd.read_csv(rules_path)
            docs_df = pd.read_csv(docs_path)
            links_df = pd.read_csv(links_path) if links_path.exists() else pd.DataFrame()

            # Initialize indexing state with totals
            total_rules = len(rules_df)
            total_docs = len(docs_df)
            total_links = len(links_df) if not links_df.empty else 0
            await indexing_state.start_indexing(
                total_rules=total_rules, total_documents=total_docs, total_links=total_links
            )
            logger.info(
                f"Starting reindexing: {total_rules} rules, {total_docs} documents, {total_links} links"
            )

            # Validate links
            if not links_df.empty:
                await indexing_state.update_progress(current_operation="Validating links CSV")
                errors = self.validate_links_csv(links_df)
                if errors:
                    logger.error(f"Links CSV validation errors: {errors}")
                    await indexing_state.fail_indexing(f"Links CSV errors: {errors}")
                    raise HTTPException(status_code=400, detail=f"Links CSV errors: {errors}")

            # Reindex rules
            await indexing_state.update_progress(current_operation="Indexing rules")
            rules_to_add = []
            rule_ids_to_add = []
            for _, row in rules_df.iterrows():
                rule = FilteredContent(
                    text=row["text"],
                    category=row.get("category", "other"),
                    risk_level=row["risk_level"],
                    threshold=row.get("threshold", 0.75),
                )
                rules_to_add.append(rule)
                rule_ids_to_add.append(str(row["id"]))

            # Reset and add rules
            self.vector_db.reset_filter_collection()
            self.vector_db.add_filter_rules_batch(rules_to_add, ids=rule_ids_to_add)
            items_processed["rules"] = total_rules
            await indexing_state.update_progress(
                indexed_rules=total_rules, current_operation="Rules indexed successfully"
            )
            logger.info(f"Indexed {total_rules} rules")

            # Load and index documents
            await indexing_state.update_progress(current_operation="Indexing documents")
            documents = []
            for idx, row in docs_df.iterrows():
                doc = {
                    "text": row["text"],
                    "metadata": {
                        "document_id": row.get("id", f"doc_{idx}"),
                        "category": row.get("category"),
                        "source": row.get("source"),
                    },
                }
                documents.append(doc)

            self.vector_db.reset_documents_collection()
            self.vector_db.add_documents(documents)
            items_processed["documents"] = total_docs
            await indexing_state.update_progress(
                indexed_documents=total_docs, current_operation="Documents indexed successfully"
            )
            logger.info(f"Indexed {total_docs} documents")

            # Rebuild links
            await indexing_state.update_progress(current_operation="Creating rule-document links")
            self.vector_db.reset_links_collection()
            if not links_df.empty:
                # Group links by rule_id for batch processing
                from collections import defaultdict

                links_by_rule = defaultdict(lambda: {"docs": [], "approved": []})
                for _, row in links_df.iterrows():
                    rule_id = str(row["rule_id"])
                    doc_id = str(row["document_id"])
                    is_approved = row.get("is_approved", True)
                    links_by_rule[rule_id]["docs"].append(doc_id)
                    links_by_rule[rule_id]["approved"].append(is_approved)

                links_processed = 0
                total_rules = len(links_by_rule)
                for idx, (rule_id, data) in enumerate(links_by_rule.items(), 1):
                    # For now, we assume all docs for a rule have the same approval status
                    # If mixed, we need to split into separate calls
                    is_approved = data["approved"][0] if data["approved"] else True
                    await self.vector_db.link_rule_to_documents(
                        rule_id=rule_id,
                        document_ids=data["docs"],
                        is_approved=is_approved,
                    )
                    links_processed += len(data["docs"])
                    # Update progress periodically
                    if idx % 10 == 0 or idx == total_rules:
                        await indexing_state.update_progress(
                            indexed_links=links_processed,
                            current_operation=f"Creating links ({links_processed}/{total_links})",
                        )
                items_processed["links"] = total_links
                logger.info(f"Created {total_links} rule-document links for {total_rules} rules")

            # Mark as completed
            await indexing_state.complete_indexing()

            # Record metrics
            duration = time.perf_counter() - start_time
            content_filter_metrics.record_indexing_operation(
                operation="reindex_all",
                duration_seconds=duration,
                status="success",
                items_processed=items_processed,
            )

            logger.info(f"Full reindexing completed successfully in {duration:.2f}s")
            return {"status": "success", "message": "Reindexing completed"}

        except HTTPException as e:
            status = "error"
            duration = time.perf_counter() - start_time
            content_filter_metrics.record_indexing_operation(
                operation="reindex_all",
                duration_seconds=duration,
                status="error",
                items_processed=items_processed,
            )
            await indexing_state.fail_indexing(str(e.detail))
            raise
        except Exception as e:
            status = "error"
            duration = time.perf_counter() - start_time
            content_filter_metrics.record_indexing_operation(
                operation="reindex_all",
                duration_seconds=duration,
                status="error",
                items_processed=items_processed,
            )
            error_msg = f"Error during reindexing: {e!s}"
            logger.error(error_msg)
            await indexing_state.fail_indexing(str(e))
            raise HTTPException(status_code=500, detail=str(e))

    def validate_documents_csv(self, df: pd.DataFrame) -> list[str]:
        errors = []

        # Check if DataFrame is empty
        if df.empty:
            errors.append("CSV file is empty or has no data rows")
            return errors

        # Check required columns
        required_columns = {"id", "text"}
        available_columns = set(df.columns)

        # Provide detailed error message about available columns
        if not required_columns.issubset(available_columns):
            missing = required_columns - available_columns
            errors.append(
                f"Missing required columns: {list(missing)}. "
                f"Available columns: {list(available_columns)}. "
                f"Required format: id, text (optional: category, source)"
            )
            return errors  # Return early to avoid KeyError on missing columns

        # Check for duplicates only if 'id' column exists
        if "id" in df.columns and df["id"].duplicated().any():
            duplicate_ids = df[df["id"].duplicated(keep=False)]["id"].unique().tolist()
            errors.append(f"Duplicate document IDs found: {duplicate_ids}")

        # Check for empty required fields
        if df["id"].isnull().any() or (df["id"] == "").any():
            errors.append("Some document IDs are empty")
        if df["text"].isnull().any() or (df["text"] == "").any():
            errors.append("Some document texts are empty")

        return errors

    def validate_rules_csv(self, df: pd.DataFrame) -> list[str]:
        errors = []

        # Check if DataFrame is empty
        if df.empty:
            errors.append("CSV file is empty or has no data rows")
            return errors

        # Check required columns
        required_columns = {"id", "text", "risk_level"}
        available_columns = set(df.columns)

        # Provide detailed error message about available columns
        if not required_columns.issubset(available_columns):
            missing = required_columns - available_columns
            errors.append(
                f"Missing required columns: {list(missing)}. "
                f"Available columns: {list(available_columns)}. "
                f"Required format: id, text, risk_level (optional: category, threshold)"
            )
            return errors  # Return early to avoid KeyError on missing columns

        # Check for duplicates only if 'id' column exists
        if "id" in df.columns and df["id"].duplicated().any():
            duplicate_ids = df[df["id"].duplicated(keep=False)]["id"].unique().tolist()
            errors.append(f"Duplicate rule IDs found: {duplicate_ids}")

        # Check for empty required fields
        if df["id"].isnull().any() or (df["id"] == "").any():
            errors.append("Some rule IDs are empty")
        if df["text"].isnull().any() or (df["text"] == "").any():
            errors.append("Some rule texts are empty")

        # Validate risk_level is numeric
        if "risk_level" in df.columns:
            try:
                df["risk_level"].astype(int)
            except (ValueError, TypeError):
                errors.append("risk_level column must contain numeric values")

        return errors

    async def get_indexing_status(self) -> IndexingStatus:
        """
        Get the current indexing status.

        Returns:
            IndexingStatus object with current state
        """
        return await indexing_state.get_status()

    def is_indexing_in_progress(self) -> bool:
        """
        Check if indexing is currently in progress.

        Returns:
            True if indexing is in progress, False otherwise
        """
        return indexing_state.is_indexing_in_progress()

    async def export_to_csv(self, output_dir: Path | None = None) -> dict:
        """
        Export current vector database data to CSV files.

        This creates a backup of the current state before reindexing.

        Args:
            output_dir: Directory to save CSV files (defaults to RAW_DATA_DIR)

        Returns:
            Dict with export statistics
        """
        start_time = time.perf_counter()
        items_exported = {"rules": 0, "documents": 0, "links": 0}

        try:
            # Use RAW_DATA_DIR if output_dir not specified
            if output_dir is None:
                output_dir = settings.RAW_DATA_DIR

            # Ensure output directory exists
            directory_manager.ensure_directory(output_dir)

            logger.info(f"Starting data export to {output_dir}")

            # Export rules
            rules = await self.vector_db.get_all_rules()
            if rules:
                rules_df = pd.DataFrame(rules)
                # Ensure required columns are present and in correct order
                rules_columns = ['id', 'text', 'category', 'risk_level', 'threshold']
                # Add missing columns with defaults
                for col in rules_columns:
                    if col not in rules_df.columns:
                        if col == 'category':
                            rules_df[col] = 'other'
                        elif col == 'threshold':
                            rules_df[col] = 0.75
                        else:
                            rules_df[col] = ''
                rules_df = rules_df[rules_columns]
                rules_path = output_dir / "filter_rules.csv"
                rules_df.to_csv(rules_path, index=False)
                items_exported["rules"] = len(rules)
                logger.info(f"Exported {len(rules)} rules to {rules_path}")
            else:
                logger.warning("No rules found to export")

            # Export documents
            documents = await self.vector_db.get_all_documents()
            if documents:
                # Transform documents data structure
                docs_data = []
                for doc in documents:
                    doc_dict = {
                        'id': doc.get('metadata', {}).get('document_id', doc.get('id', '')),
                        'text': doc.get('text', ''),
                        'category': doc.get('metadata', {}).get('category', ''),
                        'source': doc.get('metadata', {}).get('source', ''),
                    }
                    docs_data.append(doc_dict)

                docs_df = pd.DataFrame(docs_data)
                # Ensure required columns
                docs_columns = ['id', 'text', 'category', 'source']
                for col in docs_columns:
                    if col not in docs_df.columns:
                        docs_df[col] = ''
                docs_df = docs_df[docs_columns]
                docs_path = output_dir / "vector_documents.csv"
                docs_df.to_csv(docs_path, index=False)
                items_exported["documents"] = len(documents)
                logger.info(f"Exported {len(documents)} documents to {docs_path}")
            else:
                logger.warning("No documents found to export")

            # Export links
            links = await self.vector_db.get_all_links()
            if links:
                links_df = pd.DataFrame(links)
                # Ensure required columns are present and in correct order
                links_columns = ['rule_id', 'document_id', 'is_approved']
                for col in links_columns:
                    if col not in links_df.columns:
                        if col == 'is_approved':
                            links_df[col] = True
                        else:
                            links_df[col] = ''
                links_df = links_df[links_columns]
                links_path = output_dir / "links.csv"
                links_df.to_csv(links_path, index=False)
                items_exported["links"] = len(links)
                logger.info(f"Exported {len(links)} links to {links_path}")
            else:
                logger.info("No links found to export (this is normal for new installations)")

            # Record metrics
            duration = time.perf_counter() - start_time
            content_filter_metrics.record_indexing_operation(
                operation="export_csv",
                duration_seconds=duration,
                status="success",
                items_processed=items_exported,
            )

            result = {
                "status": "success",
                "exported_rules": len(rules) if rules else 0,
                "exported_documents": len(documents) if documents else 0,
                "exported_links": len(links) if links else 0,
                "output_directory": str(output_dir)
            }
            logger.info(f"Export completed in {duration:.2f}s: {result}")
            return result

        except Exception as e:
            # Record error metrics
            duration = time.perf_counter() - start_time
            content_filter_metrics.record_indexing_operation(
                operation="export_csv",
                duration_seconds=duration,
                status="error",
                items_processed=items_exported,
            )
            error_msg = f"Error during export: {e!s}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=str(e))
