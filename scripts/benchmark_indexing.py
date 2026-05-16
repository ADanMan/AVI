"""
Benchmark script for measuring indexing performance at different data sizes.

This script:
1. Generates test datasets of varying sizes
2. Measures indexing time and memory usage for each size
3. Tests both ChromaDB and Qdrant backends
4. Outputs detailed results and recommendations
"""

import asyncio
import csv
import gc
import json
import shutil
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.services.indexing_service import IndexingService
from src.services.vector_db import ChromaVectorDBService, QdrantVectorDBService
from src.utils.logger import logger


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark test."""

    name: str
    num_rules: int
    num_documents: int
    num_links_per_rule: int = 5


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    config_name: str
    db_type: str
    num_rules: int
    num_documents: int
    num_links: int
    indexing_time_seconds: float
    peak_memory_mb: float
    rules_per_second: float
    documents_per_second: float
    links_per_second: float
    errors: list[str] = field(default_factory=list)


# Benchmark configurations
BENCHMARK_CONFIGS = [
    BenchmarkConfig(name="Small", num_rules=100, num_documents=500, num_links_per_rule=5),
    BenchmarkConfig(name="Medium", num_rules=1000, num_documents=5000, num_links_per_rule=5),
    BenchmarkConfig(name="Large", num_rules=10000, num_documents=50000, num_links_per_rule=5),
    # X-Large may take very long and consume a lot of memory - uncomment if needed
    # BenchmarkConfig(name="X-Large", num_rules=100000, num_documents=500000, num_links_per_rule=5),
]


class TestDataGenerator:
    """Generate realistic test data for benchmarking."""

    # Sample data for realistic generation
    CATEGORIES = [
        "security",
        "privacy",
        "compliance",
        "performance",
        "quality",
        "accessibility",
    ]

    RISK_LEVELS = [1, 2, 3, 4, 5]

    RULE_TEMPLATES = [
        "Do not expose {category} information in responses",
        "Filter out {category} content that matches pattern {pattern}",
        "Block requests containing {category} indicators",
        "Sanitize {category} data before processing",
        "Validate {category} compliance for all outputs",
        "Prevent {category} leakage in error messages",
        "Enforce {category} policies on user inputs",
        "Monitor {category} violations and alert",
    ]

    DOC_TEMPLATES = [
        "This document describes {category} guidelines for {topic}",
        "Best practices for handling {category} in {topic} scenarios",
        "Policy documentation for {category} compliance",
        "{category} requirements and implementation details",
        "Security considerations for {category} in production",
        "Operational procedures for {category} management",
    ]

    TOPICS = [
        "API endpoints",
        "database queries",
        "user authentication",
        "file uploads",
        "data exports",
        "system logs",
        "chat interactions",
        "admin operations",
    ]

    @classmethod
    def generate_rules(cls, num_rules: int) -> pd.DataFrame:
        """Generate filter rules dataset."""
        rules = []
        for i in range(num_rules):
            category = cls.CATEGORIES[i % len(cls.CATEGORIES)]
            template = cls.RULE_TEMPLATES[i % len(cls.RULE_TEMPLATES)]
            pattern = f"pattern_{i % 20}"

            text = template.format(category=category, pattern=pattern)
            risk_level = cls.RISK_LEVELS[i % len(cls.RISK_LEVELS)]
            threshold = 0.7 + (i % 3) * 0.1  # 0.7, 0.8, 0.9

            rules.append(
                {
                    "id": f"rule_{i}",
                    "text": text,
                    "category": category,
                    "risk_level": risk_level,
                    "threshold": threshold,
                }
            )

        return pd.DataFrame(rules)

    @classmethod
    def generate_documents(cls, num_documents: int) -> pd.DataFrame:
        """Generate documents dataset."""
        documents = []
        for i in range(num_documents):
            category = cls.CATEGORIES[i % len(cls.CATEGORIES)]
            template = cls.DOC_TEMPLATES[i % len(cls.DOC_TEMPLATES)]
            topic = cls.TOPICS[i % len(cls.TOPICS)]

            text = template.format(category=category, topic=topic)

            documents.append(
                {
                    "id": f"doc_{i}",
                    "text": text,
                    "category": category,
                    "source": f"source_{i % 10}",
                }
            )

        return pd.DataFrame(documents)

    @classmethod
    def generate_links(
        cls, num_rules: int, num_documents: int, links_per_rule: int
    ) -> pd.DataFrame:
        """Generate rule-document links."""
        links = []
        for rule_idx in range(num_rules):
            # Link each rule to multiple documents (round-robin)
            for link_idx in range(links_per_rule):
                doc_idx = (rule_idx * links_per_rule + link_idx) % num_documents
                links.append(
                    {
                        "rule_id": f"rule_{rule_idx}",
                        "document_id": f"doc_{doc_idx}",
                        "is_approved": True,
                    }
                )

        return pd.DataFrame(links)


class BenchmarkRunner:
    """Run indexing benchmarks and collect results."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[BenchmarkResult] = []

    def create_test_data(self, config: BenchmarkConfig, data_dir: Path) -> None:
        """Generate and save test data to CSV files."""
        logger.info(f"Generating test data for {config.name} benchmark...")

        # Generate data
        rules_df = TestDataGenerator.generate_rules(config.num_rules)
        docs_df = TestDataGenerator.generate_documents(config.num_documents)
        links_df = TestDataGenerator.generate_links(
            config.num_rules, config.num_documents, config.num_links_per_rule
        )

        # Save to CSV
        data_dir.mkdir(parents=True, exist_ok=True)
        rules_df.to_csv(data_dir / "filter_rules.csv", index=False)
        docs_df.to_csv(data_dir / "vector_documents.csv", index=False)
        links_df.to_csv(data_dir / "links.csv", index=False)

        logger.info(
            f"Generated {len(rules_df)} rules, {len(docs_df)} documents, {len(links_df)} links"
        )

    async def run_benchmark(
        self, config: BenchmarkConfig, db_type: str, data_dir: Path
    ) -> BenchmarkResult:
        """Run a single benchmark test."""
        logger.info(f"Running {config.name} benchmark with {db_type}...")

        # Setup vector DB
        if db_type == "chroma":
            vector_db = ChromaVectorDBService()
        elif db_type == "qdrant":
            vector_db = QdrantVectorDBService()
        else:
            raise ValueError(f"Unknown db_type: {db_type}")

        indexing_service = IndexingService(vector_db)

        # Calculate expected links
        num_links = config.num_rules * config.num_links_per_rule

        # Override settings to use test data directory
        original_raw_data_dir = settings.RAW_DATA_DIR
        settings.RAW_DATA_DIR = data_dir

        errors = []
        indexing_time = 0.0
        peak_memory_mb = 0.0

        try:
            # Force garbage collection before benchmark
            gc.collect()

            # Start memory tracking
            tracemalloc.start()

            # Measure indexing time
            start_time = time.time()
            await indexing_service.reindex_all(skip_export=True)
            end_time = time.time()

            indexing_time = end_time - start_time

            # Get peak memory usage
            _current, peak = tracemalloc.get_traced_memory()
            peak_memory_mb = peak / (1024 * 1024)  # Convert to MB
            tracemalloc.stop()

            logger.info(
                f"Indexing completed in {indexing_time:.2f}s, peak memory: {peak_memory_mb:.2f}MB"
            )

        except Exception as e:
            logger.error(f"Benchmark failed: {e}")
            errors.append(str(e))
            tracemalloc.stop()

        finally:
            # Restore original settings
            settings.RAW_DATA_DIR = original_raw_data_dir

            # Cleanup vector DB
            try:
                if hasattr(vector_db, "aclose"):
                    await vector_db.aclose()
            except Exception as e:
                logger.warning(f"Error closing vector DB: {e}")

        # Calculate throughput
        rules_per_second = config.num_rules / indexing_time if indexing_time > 0 else 0
        documents_per_second = config.num_documents / indexing_time if indexing_time > 0 else 0
        links_per_second = num_links / indexing_time if indexing_time > 0 else 0

        return BenchmarkResult(
            config_name=config.name,
            db_type=db_type,
            num_rules=config.num_rules,
            num_documents=config.num_documents,
            num_links=num_links,
            indexing_time_seconds=indexing_time,
            peak_memory_mb=peak_memory_mb,
            rules_per_second=rules_per_second,
            documents_per_second=documents_per_second,
            links_per_second=links_per_second,
            errors=errors,
        )

    async def run_all_benchmarks(self, configs: list[BenchmarkConfig], db_types: list[str]) -> None:
        """Run benchmarks for all configurations and database types."""
        temp_dir = Path(tempfile.mkdtemp(prefix="avi_benchmark_"))

        try:
            for config in configs:
                # Create test data (once per config)
                data_dir = temp_dir / config.name.lower()
                self.create_test_data(config, data_dir)

                # Run benchmarks for each DB type
                for db_type in db_types:
                    result = await self.run_benchmark(config, db_type, data_dir)
                    self.results.append(result)

                    # Save intermediate results
                    self.save_results()

        finally:
            # Cleanup temporary data
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")

    def save_results(self) -> None:
        """Save benchmark results to files."""
        # Save as JSON
        json_path = self.output_dir / "indexing_benchmark_results.json"
        with open(json_path, "w") as f:
            json.dump([vars(r) for r in self.results], f, indent=2)

        # Save as CSV
        csv_path = self.output_dir / "indexing_benchmark_results.csv"
        if self.results:
            keys = [
                "config_name",
                "db_type",
                "num_rules",
                "num_documents",
                "num_links",
                "indexing_time_seconds",
                "peak_memory_mb",
                "rules_per_second",
                "documents_per_second",
                "links_per_second",
            ]
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for result in self.results:
                    row = {k: getattr(result, k) for k in keys}
                    writer.writerow(row)

        logger.info(f"Results saved to {json_path} and {csv_path}")

    def generate_report(self) -> str:
        """Generate markdown report with results and recommendations."""
        lines = ["# Indexing Performance Benchmark Results\n"]
        lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("## Overview\n")
        lines.append(
            "This report contains benchmark results for the AVI indexing process across different data sizes and vector database backends.\n"
        )

        # Summary table
        lines.append("## Results Summary\n")
        lines.append(
            "| Configuration | DB Type | Rules | Documents | Links | Time (s) | Memory (MB) | Rules/s | Docs/s |"
        )
        lines.append(
            "|---------------|---------|-------|-----------|-------|----------|-------------|---------|--------|"
        )

        for result in self.results:
            lines.append(
                f"| {result.config_name} | {result.db_type} | {result.num_rules:,} | {result.num_documents:,} | "
                f"{result.num_links:,} | {result.indexing_time_seconds:.2f} | {result.peak_memory_mb:.2f} | "
                f"{result.rules_per_second:.1f} | {result.documents_per_second:.1f} |"
            )

        lines.append("\n")

        # Performance analysis
        lines.append("## Performance Analysis\n")

        # Group results by config
        configs = {}
        for result in self.results:
            if result.config_name not in configs:
                configs[result.config_name] = []
            configs[result.config_name].append(result)

        for config_name, results in configs.items():
            lines.append(f"### {config_name} Dataset\n")

            for result in results:
                lines.append(f"**{result.db_type.upper()}:**")
                lines.append(f"- Indexing time: {result.indexing_time_seconds:.2f}s")
                lines.append(f"- Peak memory: {result.peak_memory_mb:.2f} MB")
                lines.append(
                    f"- Throughput: {result.rules_per_second:.1f} rules/s, {result.documents_per_second:.1f} docs/s"
                )

                if result.errors:
                    lines.append(f"- **Errors:** {', '.join(result.errors)}")

                lines.append("")

        # Comparison
        lines.append("## Database Comparison\n")

        chroma_results = [r for r in self.results if r.db_type == "chroma"]
        qdrant_results = [r for r in self.results if r.db_type == "qdrant"]

        if chroma_results and qdrant_results:
            lines.append("### Average Performance")
            lines.append("")

            chroma_avg_time = sum(r.indexing_time_seconds for r in chroma_results) / len(
                chroma_results
            )
            qdrant_avg_time = sum(r.indexing_time_seconds for r in qdrant_results) / len(
                qdrant_results
            )

            chroma_avg_mem = sum(r.peak_memory_mb for r in chroma_results) / len(chroma_results)
            qdrant_avg_mem = sum(r.peak_memory_mb for r in qdrant_results) / len(qdrant_results)

            lines.append("**ChromaDB:**")
            lines.append(f"- Average indexing time: {chroma_avg_time:.2f}s")
            lines.append(f"- Average memory usage: {chroma_avg_mem:.2f} MB\n")

            lines.append("**Qdrant:**")
            lines.append(f"- Average indexing time: {qdrant_avg_time:.2f}s")
            lines.append(f"- Average memory usage: {qdrant_avg_mem:.2f} MB\n")

            # Winner
            if chroma_avg_time < qdrant_avg_time:
                speedup = ((qdrant_avg_time - chroma_avg_time) / qdrant_avg_time) * 100
                lines.append(f"ChromaDB is **{speedup:.1f}% faster** on average.\n")
            else:
                speedup = ((chroma_avg_time - qdrant_avg_time) / chroma_avg_time) * 100
                lines.append(f"Qdrant is **{speedup:.1f}% faster** on average.\n")

        # Recommendations
        lines.append("## Recommendations\n")
        lines.append("### For Small to Medium Datasets (< 5,000 documents)")
        lines.append("- Both ChromaDB and Qdrant perform well")
        lines.append("- ChromaDB is simpler to set up and requires no external services")
        lines.append("- Recommended for development and small production deployments\n")

        lines.append("### For Large Datasets (5,000 - 50,000 documents)")
        lines.append("- Monitor memory usage carefully")
        lines.append("- Consider Qdrant for better scalability")
        lines.append("- Implement batch processing with progress tracking\n")

        lines.append("### For X-Large Datasets (> 50,000 documents)")
        lines.append("- Qdrant is recommended for production use")
        lines.append("- Implement incremental indexing to avoid full reindexing")
        lines.append("- Consider distributed deployment for Qdrant")
        lines.append("- Monitor memory and disk usage")
        lines.append("- Implement batching with configurable batch sizes\n")

        lines.append("### Optimization Opportunities\n")
        lines.append("Based on the benchmarks, consider these optimizations:")
        lines.append("")
        lines.append("1. **Parallel Processing:** Implement parallel document vectorization")
        lines.append("2. **Batch Sizing:** Optimize batch sizes for vector DB operations")
        lines.append("3. **Incremental Indexing:** Only reindex changed data")
        lines.append("4. **Memory Management:** Implement streaming for large datasets")
        lines.append("5. **Caching:** Cache embeddings for unchanged documents")
        lines.append(
            "6. **Progress Tracking:** Add detailed progress reporting for long operations"
        )

        return "\n".join(lines)


async def main():
    """Main benchmark execution."""
    print("=" * 80)
    print("AVI Indexing Performance Benchmark")
    print("=" * 80)
    print()

    # Create output directory
    output_dir = PROJECT_ROOT / "data" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize benchmark runner
    runner = BenchmarkRunner(output_dir)

    # Database types to test
    db_types = ["chroma", "qdrant"]

    print(f"Running benchmarks for: {', '.join(db_types)}")
    print(f"Configurations: {', '.join(c.name for c in BENCHMARK_CONFIGS)}")
    print()

    # Run benchmarks
    await runner.run_all_benchmarks(BENCHMARK_CONFIGS, db_types)

    # Generate and save report
    report = runner.generate_report()
    report_path = output_dir / "indexing_results.md"
    with open(report_path, "w") as f:
        f.write(report)

    print()
    print("=" * 80)
    print("Benchmark Complete!")
    print("=" * 80)
    print(f"Results saved to: {output_dir}")
    print("- JSON: indexing_benchmark_results.json")
    print("- CSV: indexing_benchmark_results.csv")
    print("- Report: indexing_results.md")
    print()
    print("Summary:")
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
