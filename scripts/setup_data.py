# setup_data.py
import json  # For PII masking dataset which has JSON strings
import sys
from pathlib import Path
from typing import Any


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.utils.logger import logger


# Ensure 'datasets' library is installed for loading benchmark datasets
try:
    from datasets import get_dataset_config_names, load_dataset
except ImportError:
    logger.error(
        "The 'datasets' library is required. Install with: "
        "pip install -r requirements.txt"
    )
    exit(1)


def setup_data_directories():
    """Creates necessary data directories for the project."""
    directories = [
        "data/benchmarks",
        "data/results",
        "tests/results",
        "data/models",
        "data/embeddings",
        "data/raw",  # Ensure raw data directory exists
    ]
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")


def prepare_multilingual_paradetox_all_languages() -> tuple[list, list, list]:
    """
    Fetches and processes Multilingual ParaDetox dataset to create
    initial filter rules, vector documents, and links.
    Returns:
        tuple[list, list, list]: Lists of filter rules, vector documents, and links.
    """
    logger.info("Fetching available languages for Multilingual ParaDetox...")
    try:
        languages = get_dataset_config_names("textdetox/multilingual_paradetox")
    except Exception as e:
        logger.error(
            f"Failed to get dataset config names for Multilingual ParaDetox: {e}. Skipping."
        )
        return [], [], []

    logger.info(f"Languages found: {languages}")
    fr_rows, vd_rows, ln_rows = [], [], []

    # Limit ParaDetox to avoid creating too many records (which slows down indexing)
    MAX_SAMPLES_PER_LANGUAGE = 500  # Adjust as needed

    for lang in languages:
        logger.info(f"Processing language: {lang}")
        try:
            ds = load_dataset("textdetox/multilingual_paradetox", lang)
        except Exception as e:
            logger.warning(f"Could not load dataset for {lang}: {e}. Skipping.")
            continue

        lang_samples = 0
        for split in ds.keys():
            data = ds[split]
            for i, example in enumerate(data):
                if lang_samples >= MAX_SAMPLES_PER_LANGUAGE:
                    break

                pair_id = f"paradetox_{lang}_{split}_{i+1}"  # Unique ID for ParaDetox
                toxic = example.get("toxic_sentence")
                civil = example.get("neutral_sentence")

                if not toxic or not civil:
                    continue

                fr_rows.append(
                    {
                        "id": pair_id,
                        "text": toxic,
                        "category": f"General_Toxicity_{lang}",
                        "risk_level": 5,
                        "threshold": 0.8,
                    }
                )
                vd_rows.append(
                    {
                        "id": pair_id,
                        "text": civil,
                        "category": f"General_Toxicity_Explanation_{lang}",
                        "source": f"Multilingual ParaDetox {lang}",
                    }
                )
                ln_rows.append({"rule_id": pair_id, "document_id": pair_id, "is_approved": True})
                lang_samples += 1

            if lang_samples >= MAX_SAMPLES_PER_LANGUAGE:
                break
    logger.info(
        f"Prepared {len(fr_rows)} rules, {len(vd_rows)} documents, {len(ln_rows)} links from ParaDetox."
    )
    return fr_rows, vd_rows, ln_rows


def prepare_benchmark_rules() -> tuple[list, list, list]:
    """
    Prepares filter rules and documents from various benchmark datasets.
    Returns:
        tuple[list, list, list]: Lists of filter rules, vector documents, and links.
    """
    logger.info("Preparing rules from benchmark datasets...")
    fr_rows_bench, vd_rows_bench, ln_rows_bench = [], [], []

    # --- 1. Prompt Injections (deepset/prompt-injections) ---
    # Problematic prompts as rules, generic safe usage explanation as document.
    try:
        ds_pi = load_dataset("deepset/prompt-injections", split="train")
        # Sample to avoid creating too many rules if dataset is very large
        sample_size = 1000  # Adjust as needed
        for i, example in enumerate(ds_pi.shuffle().select(range(min(sample_size, len(ds_pi))))):
            text = example.get("text")
            label = example.get("label")  # 1 for injection, 0 for safe

            if text and label == 1:  # Only problematic prompts as rules
                rule_id = f"prompt_injection_rule_{i}"
                fr_rows_bench.append(
                    {
                        "id": rule_id,
                        "text": text,
                        "category": "Prompt_Injection",
                        "risk_level": 5,
                        "threshold": 0.9,
                    }
                )
                # Generic document for prompt injection explanation
                doc_id = f"prompt_injection_doc_{i}"
                vd_rows_bench.append(
                    {
                        "id": doc_id,
                        "text": f"Information about prompt injection: '{text}' is a form of prompt injection. Always ensure LLM interactions are safe and aligned with intended use. Avoid instructions that try to override system prompts or extract sensitive information.",
                        "category": "Prompt_Injection_Explanation",
                        "source": "deepset/prompt-injections",
                    }
                )
                ln_rows_bench.append(
                    {"rule_id": rule_id, "document_id": doc_id, "is_approved": True}
                )
        logger.info(
            f"Processed {len([r for r in fr_rows_bench if r['category'] == 'Prompt_Injection'])} prompt injection rules."
        )
    except Exception as e:
        logger.warning(f"Could not load deepset/prompt-injections: {e}. Skipping.")

    # --- 2. PII Masking (ai4privacy/pii-masking-200k) ---
    # 'source_text' as the rule if it contains PII, and 'target_text' (masked) as the safe document.
    try:
        ds_pii = load_dataset("ai4privacy/pii-masking-200k", split="train")
        sample_size = 1000  # Adjust as needed
        for i, example in enumerate(ds_pii.shuffle().select(range(min(sample_size, len(ds_pii))))):
            source_text = example.get("source_text")
            target_text = example.get("target_text")
            privacy_mask = example.get(
                "privacy_mask"
            )  # This is a JSON string or already parsed object

            # Check if PII is actually detected in the source text
            # MODIFIED: Handle privacy_mask being already parsed or a string
            has_pii = False
            if privacy_mask:
                if isinstance(privacy_mask, str):
                    try:
                        parsed_mask = json.loads(privacy_mask)
                        if parsed_mask:
                            has_pii = True
                    except json.JSONDecodeError:
                        pass  # Not a valid JSON string
                elif isinstance(privacy_mask, list) and privacy_mask:
                    has_pii = True  # Already parsed as a non-empty list

            if source_text and target_text and has_pii:
                rule_id = f"pii_masking_rule_{i}"
                fr_rows_bench.append(
                    {
                        "id": rule_id,
                        "text": source_text,  # The original text with PII as the rule
                        "category": "PII_Leakage",
                        "risk_level": 4,
                        "threshold": 0.85,
                    }
                )
                doc_id = f"pii_masking_doc_{i}"
                vd_rows_bench.append(
                    {
                        "id": doc_id,
                        "text": target_text,  # The masked text as the safe document
                        "category": "PII_Masked_Content",
                        "source": "ai4privacy/pii-masking-200k",
                    }
                )
                ln_rows_bench.append(
                    {"rule_id": rule_id, "document_id": doc_id, "is_approved": True}
                )
        logger.info(
            f"Processed {len([r for r in fr_rows_bench if r['category'] == 'PII_Leakage'])} PII rules."
        )
    except Exception as e:
        logger.warning(f"Could not load ai4privacy/pii-masking-200k: {e}. Skipping.")

    # --- 3. Bias (bigscience-catalogue-data/shades_nationality) ---
    # 'sentence' as rule if it's a stereotype, and a generic "neutrality" document.
    try:
        ds_bias = load_dataset("bigscience-catalogue-data/shades_nationality", split="train")
        sample_size = 1000  # Adjust as needed
        for i, example in enumerate(
            ds_bias.shuffle().select(range(min(sample_size, len(ds_bias))))
        ):
            sentence = example.get("sentence")
            is_stereotype = example.get("is_stereotype")  # "yes" or "no"

            if sentence and is_stereotype == "yes":
                rule_id = f"bias_nationality_rule_{i}"
                fr_rows_bench.append(
                    {
                        "id": rule_id,
                        "text": sentence,
                        "category": "Bias_Nationality",
                        "risk_level": 3,
                        "threshold": 0.75,
                    }
                )
                doc_id = f"bias_nationality_doc_{i}"
                vd_rows_bench.append(
                    {
                        "id": doc_id,
                        "text": f"This statement contains a national stereotype: '{sentence}'. Promote respectful and unbiased language towards all nationalities.",
                        "category": "Bias_Explanation",
                        "source": "shades_nationality",
                    }
                )
                ln_rows_bench.append(
                    {"rule_id": rule_id, "document_id": doc_id, "is_approved": True}
                )
        logger.info(
            f"Processed {len([r for r in fr_rows_bench if r['category'] == 'Bias_Nationality'])} bias rules."
        )
    except Exception as e:
        logger.warning(
            f"Could not load bigscience-catalogue-data/shades_nationality: {e}. Skipping."
        )

    # --- 4. Hallucination (HanzhiZhang/Poly-FEVER) ---
    # 'en' text as rule if Label is 'False' (non-factual/hallucination), and a generic "factual correction" document.
    try:
        ds_hallucination = load_dataset("HanzhiZhang/Poly-FEVER", split="train")
        sample_size = 1000  # Adjust as needed

        # MODIFIED: Ensure we select a sample if the dataset is large
        selected_examples = ds_hallucination.shuffle().select(
            range(min(sample_size, len(ds_hallucination)))
        )

        for i, example in enumerate(selected_examples):  # Use selected_examples
            text_en = example.get("en")
            label = example.get(
                "Label"
            )  # "True" for factual, "False" for non-factual/hallucination

            # MODIFIED: More robust check for "False" label
            if (
                text_en and str(label).lower() == "false"
            ):  # Convert label to string and lowercase for robust comparison
                rule_id = f"hallucination_polyfever_rule_{i}"
                fr_rows_bench.append(
                    {
                        "id": rule_id,
                        "text": text_en,
                        "category": "Hallucination_Detection",
                        "risk_level": 3,
                        "threshold": 0.7,
                    }
                )
                doc_id = f"hallucination_polyfever_doc_{i}"
                vd_rows_bench.append(
                    {
                        "id": doc_id,
                        "text": f"This statement contains a potential factual inaccuracy: '{text_en}'. Always verify information from trusted sources.",
                        "category": "Hallucination_Explanation",
                        "source": "HanzhiZhang/Poly-FEVER",
                    }
                )
                ln_rows_bench.append(
                    {"rule_id": rule_id, "document_id": doc_id, "is_approved": True}
                )
        logger.info(
            f"Processed {len([r for r in fr_rows_bench if r['category'] == 'Hallucination_Detection'])} hallucination rules."
        )
    except Exception as e:
        logger.warning(
            f"Could not load HanzhiZhang/Poly-FEVER or process it: {e}. Skipping."
        )  # Added more context to warning

    logger.info(
        f"Prepared {len(fr_rows_bench)} rules, {len(vd_rows_bench)} documents, {len(ln_rows_bench)} links from benchmark datasets."
    )
    return fr_rows_bench, vd_rows_bench, ln_rows_bench


def standardize_raw_csvs(raw_dir: Path):
    """
    Standardizes the columns of raw CSV files to ensure compatibility with the API/app.py.
    Args:
        raw_dir (Path): Path to the raw data directory.
    """
    logger.info("Standardizing all raw CSVs for API/app.py compatibility.")

    # filter_rules.csv
    fr_path = raw_dir / "filter_rules.csv"
    if fr_path.exists() and fr_path.stat().st_size > 0:
        try:
            df = pd.read_csv(fr_path, encoding="utf-8")
            cols = ["id", "text", "category", "risk_level", "threshold"]
            # Select and reorder columns, fill missing with defaults if necessary
            for col in cols:
                if col not in df.columns:
                    df[col] = None  # Or a sensible default
            df = df[cols]
            df.to_csv(fr_path, index=False, encoding="utf-8")
            logger.info(f"Standardized {fr_path.name}.")
        except Exception as e:
            logger.warning(f"Skip standardizing {fr_path.name}: {e}")

    # vector_documents.csv
    vd_path = raw_dir / "vector_documents.csv"
    if vd_path.exists() and vd_path.stat().st_size > 0:
        try:
            df = pd.read_csv(vd_path, encoding="utf-8")
            cols = ["id", "text", "category", "source"]
            for col in cols:
                if col not in df.columns:
                    df[col] = None
            df = df[cols]
            df.to_csv(vd_path, index=False, encoding="utf-8")
            logger.info(f"Standardized {vd_path.name}.")
        except Exception as e:
            logger.warning(f"Skip standardizing {vd_path.name}: {e}")

    # links.csv
    ln_path = raw_dir / "links.csv"
    if ln_path.exists() and ln_path.stat().st_size > 0:
        try:
            df = pd.read_csv(ln_path, encoding="utf-8")
            cols = ["rule_id", "document_id", "is_approved"]
            # Ensure rule_id and document_id are strings for consistency
            if "rule_id" in df.columns:
                df["rule_id"] = df["rule_id"].astype(str)
            if "document_id" in df.columns:
                df["document_id"] = df["document_id"].astype(str)

            for col in cols:
                if col not in df.columns:
                    df[col] = None
            df = df[cols]
            df.to_csv(ln_path, index=False, encoding="utf-8")
            logger.info(f"Standardized {ln_path.name}.")
        except Exception as e:
            logger.warning(f"Skip standardizing {ln_path.name}: {e}")


def save_dataset(ds: Any, out_path: Path, n_rows: int | None = 10000):
    """
    Saves a Hugging Face dataset to a CSV file.
    Args:
        ds (Any): Hugging Face dataset object.
        out_path (Path): Path to save the CSV file.
        n_rows (Optional[int]): Number of rows to save. If None, save all.
    """
    df = pd.DataFrame(ds)
    if n_rows:
        df = df.head(n_rows)
    df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info(f"[SAVED] {out_path} ({len(df)} rows)")


def download_benchmarks():
    """Downloads raw benchmark datasets to data/benchmarks/."""
    Path("data/benchmarks").mkdir(parents=True, exist_ok=True)
    logger.info("Downloading raw benchmark datasets to data/benchmarks/...")

    # 1. Toxigen (latest version)
    try:
        ds = load_dataset("toxigen/toxigen-data", split="train")
        save_dataset(ds, "data/benchmarks/toxigen.csv")
    except Exception as e:
        logger.warning(f"Could not download toxigen/toxigen-data: {e}. Skipping.")

    # 2. deepset/prompt-injections
    try:
        ds = load_dataset("deepset/prompt-injections", split="train")
        save_dataset(ds, "data/benchmarks/prompt_injections.csv")
    except Exception as e:
        logger.warning(f"Could not download deepset/prompt-injections: {e}. Skipping.")

    # 3. ai4privacy/pii-masking-200k
    try:
        ds = load_dataset("ai4privacy/pii-masking-200k", split="train")
        save_dataset(ds, "data/benchmarks/pii_masking_200k.csv")
    except Exception as e:
        logger.warning(f"Could not download ai4privacy/pii-masking-200k: {e}. Skipping.")

    # 4. HanzhiZhang/Poly-FEVER
    try:
        ds = load_dataset("HanzhiZhang/Poly-FEVER", split="train")
        save_dataset(ds, "data/benchmarks/poly_fever.csv")
    except Exception as e:
        logger.warning(f"Could not download HanzhiZhang/Poly-FEVER: {e}. Skipping.")

    # 5. bigscience-catalogue-data/shades_nationality
    try:
        ds = load_dataset("bigscience-catalogue-data/shades_nationality", split="train")
        save_dataset(ds, "data/benchmarks/shades_nationality.csv")
    except Exception as e:
        logger.warning(
            f"Could not download bigscience-catalogue-data/shades_nationality: {e}. Skipping."
        )

    logger.info("[INFO] All raw benchmark datasets downloaded and saved to data/benchmarks/.")


def prepare_all_datasets(output_dir: Path | str = "data/raw") -> None:
    """Download raw datasets and assemble derived CSV artefacts."""

    logger.info("Setting up ALL research data...")
    setup_data_directories()

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)  # Ensure raw data directory exists

    # 1. Prepare rules from Multilingual ParaDetox
    (
        fr_rows_paradetox,
        vd_rows_paradetox,
        ln_rows_paradetox,
    ) = prepare_multilingual_paradetox_all_languages()

    # 2. Prepare rules from other benchmark datasets
    fr_rows_bench, vd_rows_bench, ln_rows_bench = prepare_benchmark_rules()

    # 3. Combine all rules, documents, and links
    all_fr_rows = fr_rows_paradetox + fr_rows_bench
    all_vd_rows = vd_rows_paradetox + vd_rows_bench
    all_ln_rows = ln_rows_paradetox + ln_rows_bench

    # Save combined data to final CSVs, ensuring uniqueness
    if all_fr_rows:
        final_fr_df = pd.DataFrame(all_fr_rows)
        final_fr_df["id"] = final_fr_df["id"].astype(str)  # Ensure ID is string
        final_fr_df.drop_duplicates(subset=["id"], inplace=True)
        final_fr_df.to_csv(out_dir / "filter_rules.csv", index=False, encoding="utf-8")
        logger.info("Final filter_rules.csv saved with %s rules.", len(final_fr_df))
    else:
        logger.warning("No rules to save in final filter_rules.csv!")

    if all_vd_rows:
        final_vd_df = pd.DataFrame(all_vd_rows)
        final_vd_df["id"] = final_vd_df["id"].astype(str)  # Ensure ID is string
        final_vd_df.drop_duplicates(subset=["id"], inplace=True)
        final_vd_df.to_csv(out_dir / "vector_documents.csv", index=False, encoding="utf-8")
        logger.info(
            "Final vector_documents.csv saved with %s documents.",
            len(final_vd_df),
        )
    else:
        logger.warning("No documents to save in final vector_documents.csv!")

    if all_ln_rows:
        final_ln_df = pd.DataFrame(all_ln_rows)
        final_ln_df["rule_id"] = final_ln_df["rule_id"].astype(str)
        final_ln_df["document_id"] = final_ln_df["document_id"].astype(str)
        final_ln_df.drop_duplicates(subset=["rule_id", "document_id"], inplace=True)
        final_ln_df.to_csv(out_dir / "links.csv", index=False, encoding="utf-8")
        logger.info("Final links.csv saved with %s links.", len(final_ln_df))
    else:
        logger.warning("No links to save in final links.csv!")

    standardize_raw_csvs(out_dir)  # Pass out_dir to standardize function
    download_benchmarks()  # This downloads the raw benchmark files to data/benchmarks
    logger.info("[INFO] All data/raw and data/benchmarks datasets are ready!")


def run_sync(output_dir: Path | str = "data/raw") -> None:
    """Backwards-compatible entry point for invoking the data setup."""

    prepare_all_datasets(output_dir=output_dir)


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    run_sync()
