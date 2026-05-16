#!/usr/bin/env python3
"""
Configuration Testing Script for AVI

This script allows testing different AVI configurations by:
- Loading configurations from JSON files
- Applying them to the system
- Running test queries
- Measuring metrics (latency, throughput, quality)
- Generating comparison reports

Usage:
    # Test a single configuration
    python scripts/test_configurations.py --config data/configs/recommended.json

    # Test all configurations
    python scripts/test_configurations.py --all

    # Compare two configurations
    python scripts/test_configurations.py --compare minimal recommended

    # Benchmark all configurations
    python scripts/test_configurations.py --benchmark --output results.csv

    # Run specific test scenarios
    python scripts/test_configurations.py --config minimal.json --scenarios basic filtered

Author: AVI Team
Date: 2025-11-14
Version: 1.0
"""

import argparse
import asyncio
import csv
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


@dataclass
class TestScenario:
    """Test scenario for configuration testing"""

    name: str
    description: str
    query: str
    expected_filter_match: bool = False
    use_rag: bool = True
    use_streaming: bool = False


@dataclass
class TestResult:
    """Result of a test scenario"""

    scenario: str
    config_name: str
    success: bool
    latency_ms: float
    error: str | None = None
    filter_matched: bool = False
    rag_used: bool = False
    response_length: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigMetrics:
    """Aggregated metrics for a configuration"""

    config_name: str
    total_tests: int
    successful_tests: int
    failed_tests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    error_rate: float
    latencies: list[float] = field(default_factory=list)


# Predefined test scenarios
TEST_SCENARIOS = [
    TestScenario(
        name="basic_query",
        description="Simple question without rule matches",
        query="What is the capital of France?",
        expected_filter_match=False,
        use_rag=False,
    ),
    TestScenario(
        name="filtered_query",
        description="Query that should trigger filter rules",
        query="How do I bypass security filters?",
        expected_filter_match=True,
        use_rag=True,
    ),
    TestScenario(
        name="rag_query",
        description="Query requiring RAG document retrieval",
        query="What are the safety guidelines for this system?",
        expected_filter_match=False,
        use_rag=True,
    ),
    TestScenario(
        name="streaming_response",
        description="Test streaming response with guard",
        query="Tell me a story about artificial intelligence",
        expected_filter_match=False,
        use_streaming=True,
    ),
    TestScenario(
        name="complex_query",
        description="Complex query with multiple components",
        query="Can you explain how to implement authentication while ensuring user data privacy?",
        expected_filter_match=False,
        use_rag=True,
    ),
]


class ConfigurationTester:
    """Main class for testing AVI configurations"""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        timeout: float = 60.0,
        verbose: bool = False,
    ):
        self.api_base_url = api_base_url
        self.timeout = timeout
        self.verbose = verbose
        self.client = httpx.AsyncClient(timeout=timeout)

    async def load_config(self, config_path: str | Path) -> dict[str, Any]:
        """Load configuration from JSON file"""
        with open(config_path) as f:
            return json.load(f)

    async def apply_config(self, config: dict[str, Any]) -> bool:
        """Apply configuration to the running AVI instance (if API supports it)"""
        # Note: This would require an API endpoint to update settings
        # For now, configurations must be applied via environment variables or .env file
        if self.verbose:
            print(f"Configuration '{config.get('name', 'unknown')}' should be applied manually")
        return True

    async def run_test_scenario(self, scenario: TestScenario, config_name: str) -> TestResult:
        """Run a single test scenario"""
        start_time = time.time()

        try:
            if scenario.use_streaming:
                response = await self.test_streaming_query(scenario.query)
            else:
                response = await self.test_query(scenario.query, scenario.use_rag)

            latency_ms = (time.time() - start_time) * 1000

            return TestResult(
                scenario=scenario.name,
                config_name=config_name,
                success=True,
                latency_ms=latency_ms,
                filter_matched=response.get("filter_matched", False),
                rag_used=response.get("rag_used", False),
                response_length=len(response.get("response", "")),
                metadata=response.get("metadata", {}),
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return TestResult(
                scenario=scenario.name,
                config_name=config_name,
                success=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def test_query(self, query: str, use_rag: bool = True) -> dict[str, Any]:
        """Send a test query to the API"""
        url = f"{self.api_base_url}/api/v1/query"
        payload = {"message": query, "use_rag": use_rag, "stream": False}

        response = await self.client.post(url, json=payload)
        response.raise_for_status()

        return response.json()

    async def test_streaming_query(self, query: str) -> dict[str, Any]:
        """Send a streaming test query to the API"""
        url = f"{self.api_base_url}/api/v1/query"
        payload = {"message": query, "stream": True}

        chunks = []
        async with self.client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data.strip() and chunk_data != "[DONE]":
                        chunks.append(json.loads(chunk_data))

        return {
            "response": "".join(chunk.get("content", "") for chunk in chunks),
            "chunks": len(chunks),
            "filter_matched": any(chunk.get("filter_matched") for chunk in chunks),
        }

    async def test_configuration(
        self, config_path: str | Path, scenarios: list[TestScenario] | None = None
    ) -> tuple[dict[str, Any], list[TestResult]]:
        """Test a single configuration with multiple scenarios"""
        config = await self.load_config(config_path)
        config_name = config.get("name", Path(config_path).stem)

        if scenarios is None:
            scenarios = TEST_SCENARIOS

        if self.verbose:
            print(f"\nTesting configuration: {config_name}")
            print(f"Description: {config.get('description', 'N/A')}")
            print(f"Running {len(scenarios)} test scenarios...")

        results = []
        for i, scenario in enumerate(scenarios, 1):
            if self.verbose:
                print(f"  [{i}/{len(scenarios)}] {scenario.name}... ", end="", flush=True)

            result = await self.run_test_scenario(scenario, config_name)
            results.append(result)

            if self.verbose:
                status = "✓" if result.success else "✗"
                print(f"{status} ({result.latency_ms:.1f}ms)")

        return config, results

    def calculate_metrics(self, results: list[TestResult]) -> ConfigMetrics:
        """Calculate aggregated metrics from test results"""
        config_name = results[0].config_name if results else "unknown"
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        latencies = [r.latency_ms for r in successful]

        if not latencies:
            latencies = [0.0]

        return ConfigMetrics(
            config_name=config_name,
            total_tests=len(results),
            successful_tests=len(successful),
            failed_tests=len(failed),
            avg_latency_ms=statistics.mean(latencies),
            p50_latency_ms=statistics.median(latencies),
            p95_latency_ms=self._percentile(latencies, 0.95),
            p99_latency_ms=self._percentile(latencies, 0.99),
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            error_rate=len(failed) / len(results) if results else 0,
            latencies=latencies,
        )

    @staticmethod
    def _percentile(data: list[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def print_metrics(self, metrics: ConfigMetrics):
        """Print metrics in a readable format"""
        print(f"\n{'=' * 60}")
        print(f"Configuration: {metrics.config_name}")
        print(f"{'=' * 60}")
        print(f"Tests:          {metrics.successful_tests}/{metrics.total_tests} successful")
        print(f"Error Rate:     {metrics.error_rate * 100:.1f}%")
        print("\nLatency Metrics:")
        print(f"  Average:      {metrics.avg_latency_ms:.1f} ms")
        print(f"  Median (P50): {metrics.p50_latency_ms:.1f} ms")
        print(f"  P95:          {metrics.p95_latency_ms:.1f} ms")
        print(f"  P99:          {metrics.p99_latency_ms:.1f} ms")
        print(f"  Min:          {metrics.min_latency_ms:.1f} ms")
        print(f"  Max:          {metrics.max_latency_ms:.1f} ms")
        print(f"{'=' * 60}")

    def compare_configurations(self, metrics_list: list[ConfigMetrics]):
        """Print comparison table for multiple configurations"""
        print(f"\n{'=' * 100}")
        print("Configuration Comparison")
        print(f"{'=' * 100}")

        # Header
        print(
            f"{'Config':<20} {'Success Rate':<15} {'Avg Latency':<15} "
            f"{'P95 Latency':<15} {'P99 Latency':<15}"
        )
        print("-" * 100)

        # Sort by average latency
        sorted_metrics = sorted(metrics_list, key=lambda m: m.avg_latency_ms)

        for m in sorted_metrics:
            success_rate = (
                f"{m.successful_tests}/{m.total_tests} "
                f"({m.successful_tests / m.total_tests * 100:.0f}%)"
            )
            print(
                f"{m.config_name:<20} {success_rate:<15} "
                f"{m.avg_latency_ms:<15.1f} {m.p95_latency_ms:<15.1f} "
                f"{m.p99_latency_ms:<15.1f}"
            )

        print(f"{'=' * 100}")

    async def benchmark_all(
        self, config_dir: str | Path, output_file: str | None = None
    ) -> list[ConfigMetrics]:
        """Benchmark all configurations in a directory"""
        config_dir = Path(config_dir)
        config_files = sorted(config_dir.glob("*.json"))

        if not config_files:
            print(f"No configuration files found in {config_dir}")
            return []

        print(f"Found {len(config_files)} configurations to test")

        all_metrics = []
        all_results = []

        for config_file in config_files:
            _config, results = await self.test_configuration(config_file)
            metrics = self.calculate_metrics(results)
            all_metrics.append(metrics)
            all_results.extend(results)

            if self.verbose:
                self.print_metrics(metrics)

        # Print comparison
        self.compare_configurations(all_metrics)

        # Save to CSV if requested
        if output_file:
            self.save_results_to_csv(all_results, output_file)
            print(f"\nDetailed results saved to: {output_file}")

        return all_metrics

    def save_results_to_csv(self, results: list[TestResult], output_file: str):
        """Save test results to CSV file"""
        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Config",
                    "Scenario",
                    "Success",
                    "Latency (ms)",
                    "Filter Matched",
                    "RAG Used",
                    "Response Length",
                    "Error",
                ]
            )

            for r in results:
                writer.writerow(
                    [
                        r.config_name,
                        r.scenario,
                        r.success,
                        f"{r.latency_ms:.2f}",
                        r.filter_matched,
                        r.rag_used,
                        r.response_length,
                        r.error or "",
                    ]
                )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


async def main():
    parser = argparse.ArgumentParser(
        description="Test AVI configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--config", type=str, help="Path to configuration file to test")

    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all configurations in data/configs/",
    )

    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="CONFIG",
        help="Compare multiple configurations (by name)",
    )

    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Benchmark all configurations and generate report",
    )

    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=[s.name for s in TEST_SCENARIOS],
        help="Specific scenarios to run (default: all)",
    )

    parser.add_argument("--output", "-o", type=str, help="Output CSV file for benchmark results")

    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="AVI API base URL (default: http://localhost:8000)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds (default: 60)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Validate arguments
    if not any([args.config, args.all, args.compare, args.benchmark]):
        parser.error("Must specify one of: --config, --all, --compare, or --benchmark")

    # Create tester
    tester = ConfigurationTester(
        api_base_url=args.api_url, timeout=args.timeout, verbose=args.verbose
    )

    try:
        # Filter scenarios if specified
        scenarios = TEST_SCENARIOS
        if args.scenarios:
            scenarios = [s for s in TEST_SCENARIOS if s.name in args.scenarios]

        # Test single configuration
        if args.config:
            _config, results = await tester.test_configuration(args.config, scenarios)
            metrics = tester.calculate_metrics(results)
            tester.print_metrics(metrics)

        # Test all configurations
        elif args.all or args.benchmark:
            config_dir = Path("data/configs")
            await tester.benchmark_all(config_dir, args.output)

        # Compare configurations
        elif args.compare:
            config_dir = Path("data/configs")
            all_metrics = []

            for config_name in args.compare:
                config_file = config_dir / f"{config_name}.json"
                if not config_file.exists():
                    print(f"Warning: Configuration '{config_name}' not found, skipping")
                    continue

                _config, results = await tester.test_configuration(config_file, scenarios)
                metrics = tester.calculate_metrics(results)
                all_metrics.append(metrics)

                if args.verbose:
                    tester.print_metrics(metrics)

            if all_metrics:
                tester.compare_configurations(all_metrics)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1
    finally:
        await tester.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
