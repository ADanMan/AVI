"""Utilities for tracking content filtering metrics across the system."""

from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass, field

# Import SafetyMode type for type hints
# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram

from config.settings import settings
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.core.content_filter import SafetyMode


# Optional dependencies are imported lazily to avoid hard requirements during tests.
_mlflow_module = None
if settings.ENABLE_MLFLOW:
    mlflow_spec = importlib.util.find_spec("mlflow")
    if mlflow_spec is None:
        logger.warning("MLflow logging requested but mlflow package is not installed.")
    else:
        _mlflow_module = importlib.import_module("mlflow")

_wandb_module = None
if settings.ENABLE_WANDB:
    wandb_spec = importlib.util.find_spec("wandb")
    if wandb_spec is None:
        logger.warning("Weights & Biases logging requested but wandb package is not installed.")
    else:
        _wandb_module = importlib.import_module("wandb")


@dataclass
class LatencyStats:
    """Aggregate latency statistics."""

    count: int = 0
    total: float = 0.0
    min_value: float | None = None
    max_value: float | None = None

    def update(self, value: float) -> None:
        self.count += 1
        self.total += value
        if self.min_value is None or value < self.min_value:
            self.min_value = value
        if self.max_value is None or value > self.max_value:
            self.max_value = value

    @property
    def average(self) -> float | None:
        if self.count == 0:
            return None
        return self.total / self.count

    def as_dict(self) -> dict[str, float | None]:
        return {
            "count": self.count,
            "total": self.total,
            "min": self.min_value,
            "max": self.max_value,
            "avg": self.average,
        }


@dataclass
class ModeStats:
    """Confusion-matrix counters and latency stats for a particular safety mode."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    detection_latency: LatencyStats = field(default_factory=LatencyStats)
    sanitization_latency: LatencyStats = field(default_factory=LatencyStats)

    def record(self, predicted: bool, actual: bool | None) -> None:
        if actual is None:
            return
        if predicted and actual:
            self.true_positive += 1
        elif predicted and not actual:
            self.false_positive += 1
        elif not predicted and actual:
            self.false_negative += 1
        else:
            self.true_negative += 1

    def as_dict(self) -> dict[str, int | dict[str, float | None]]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "true_negative": self.true_negative,
            "detection_latency": self.detection_latency.as_dict(),
            "sanitization_latency": self.sanitization_latency.as_dict(),
        }


_prometheus_namespace = settings.METRICS_NAMESPACE or "avi"
_detection_latency_metric = Histogram(
    "content_filter_detection_latency_seconds",
    "Latency of ContentFilterService.check_content rule matching",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)
_sanitization_latency_metric = Histogram(
    "content_filter_sanitization_latency_seconds",
    "Latency of ContentFilterService.check_content sanitization attempts",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)
_tp_metric = Counter(
    "content_filter_true_positives_total",
    "Number of content filter true positives",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)
_fp_metric = Counter(
    "content_filter_false_positives_total",
    "Number of content filter false positives",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)
_fn_metric = Counter(
    "content_filter_false_negatives_total",
    "Number of content filter false negatives",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)
_tn_metric = Counter(
    "content_filter_true_negatives_total",
    "Number of content filter true negatives",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)

# Component-level metrics for granular filtering control
_component_applied_metric = Counter(
    "content_filter_component_applied_total",
    "Number of times a specific filtering component was applied",
    labelnames=(
        "component",
        "stage",
    ),  # component: vector_rules, safety_llm, etc. / stage: input, output
    namespace=_prometheus_namespace,
)
_component_modified_metric = Counter(
    "content_filter_component_modified_total",
    "Number of times a component modified content",
    labelnames=("component", "stage"),
    namespace=_prometheus_namespace,
)

# Input-specific metrics
_input_filter_latency_metric = Histogram(
    "input_filter_latency_seconds",
    "Latency of input filtering by component",
    labelnames=("mode", "component"),
    namespace=_prometheus_namespace,
)
_input_filter_rules_matched_metric = Counter(
    "input_filter_rules_matched_total",
    "Number of rules matched during input filtering",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)

# Output-specific metrics
_output_filter_latency_metric = Histogram(
    "output_filter_latency_seconds",
    "Latency of output filtering by component",
    labelnames=("mode", "component"),
    namespace=_prometheus_namespace,
)
_output_filter_modifications_metric = Counter(
    "output_filter_modifications_total",
    "Number of modifications made during output filtering",
    labelnames=("mode",),
    namespace=_prometheus_namespace,
)

# Linked documents retrieval metrics
_linked_docs_retrieval_latency_metric = Histogram(
    "linked_docs_retrieval_latency_seconds",
    "Latency of linked documents retrieval",
    labelnames=("rule_id",),
    namespace=_prometheus_namespace,
)
_linked_docs_count_metric = Histogram(
    "linked_docs_count",
    "Number of linked documents retrieved per rule",
    labelnames=("rule_id",),
    namespace=_prometheus_namespace,
)

# Indexing metrics
_indexing_duration_metric = Histogram(
    "indexing_duration_seconds",
    "Duration of indexing operations",
    labelnames=(
        "operation",
        "status",
    ),  # operation: reindex_all, export_csv, etc. / status: success, error
    namespace=_prometheus_namespace,
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)
_indexing_total_metric = Counter(
    "indexing_operations_total",
    "Total number of indexing operations",
    labelnames=("operation", "status"),
    namespace=_prometheus_namespace,
)
_indexing_items_processed_metric = Counter(
    "indexing_items_processed_total",
    "Total number of items processed during indexing",
    labelnames=("item_type",),  # item_type: rules, documents, links
    namespace=_prometheus_namespace,
)
_csv_upload_size_metric = Histogram(
    "csv_upload_size_bytes",
    "Size of uploaded CSV files",
    labelnames=("file_type",),  # file_type: rules, documents, links
    namespace=_prometheus_namespace,
)

# Filter quality metrics (precision, recall, F1)
_filter_precision_metric = Gauge(
    "filter_precision",
    "Precision of content filter (TP / (TP + FP))",
    labelnames=("direction",),  # direction: input, output
    namespace=_prometheus_namespace,
)
_filter_recall_metric = Gauge(
    "filter_recall",
    "Recall of content filter (TP / (TP + FN))",
    labelnames=("direction",),
    namespace=_prometheus_namespace,
)
_filter_f1_score_metric = Gauge(
    "filter_f1_score",
    "F1 score of content filter (2 * precision * recall / (precision + recall))",
    labelnames=("direction",),
    namespace=_prometheus_namespace,
)

# Detailed indexing metrics
_indexing_embedding_latency_metric = Histogram(
    "indexing_embedding_latency_seconds",
    "Latency of embedding generation during indexing",
    labelnames=("operation",),  # operation: rules, documents
    namespace=_prometheus_namespace,
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
)
_indexing_vector_insert_latency_metric = Histogram(
    "indexing_vector_insert_latency_seconds",
    "Latency of vector insertion during indexing",
    labelnames=("operation",),
    namespace=_prometheus_namespace,
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
)
_indexing_items_per_second_metric = Gauge(
    "indexing_items_per_second",
    "Rate of items processed during indexing",
    labelnames=("operation",),
    namespace=_prometheus_namespace,
)


class ContentFilterMetrics:
    """Centralized tracker for ContentFilterService statistics."""

    def __init__(self) -> None:
        self._stats: dict[str, ModeStats] = {}
        self._lock = threading.Lock()
        self._mlflow_run_active = False
        self._wandb_run = None

    def reset(self) -> None:
        """Reset in-memory statistics (useful for tests)."""
        with self._lock:
            self._stats = {}

    def _ensure_mlflow_run(self) -> None:
        if not settings.ENABLE_MLFLOW or _mlflow_module is None:
            return
        try:
            if settings.MLFLOW_TRACKING_URI:
                _mlflow_module.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            experiment_name = settings.MLFLOW_EXPERIMENT_NAME or "content_filter_metrics"
            _mlflow_module.set_experiment(experiment_name)
            run_name = settings.MLFLOW_RUN_NAME or "content_filter_metrics"

            # Check if there's an active run and if it's in a valid state
            active_run = _mlflow_module.active_run()
            if active_run is not None:
                # Check if the run is actually active (not ended/deleted)
                run_info = active_run.info
                if run_info.lifecycle_stage == "active":
                    self._mlflow_run_active = True
                    return
                # If the run is not active, we need to start a new one
                logger.debug(
                    "Existing MLflow run is not active (state: {}), starting new run",
                    run_info.lifecycle_stage,
                )

            # Start a new run if none exists or the existing one is not active
            _mlflow_module.start_run(run_name=run_name)
            self._mlflow_run_active = True
        except Exception as mlflow_error:  # pragma: no cover - external dependency
            logger.warning("Failed to initialize MLflow tracking: {}", mlflow_error)
            self._mlflow_run_active = False

    def _log_mlflow(self, mode: str, snapshot: dict[str, int | dict[str, float | None]]) -> None:
        if not settings.ENABLE_MLFLOW or _mlflow_module is None:
            return
        self._ensure_mlflow_run()
        if not self._mlflow_run_active:
            return
        try:
            _mlflow_module.log_metrics(
                {
                    f"{mode}_tp": snapshot["true_positive"],
                    f"{mode}_fp": snapshot["false_positive"],
                    f"{mode}_fn": snapshot["false_negative"],
                    f"{mode}_tn": snapshot["true_negative"],
                }
            )
            detection_latency = snapshot["detection_latency"]
            if detection_latency.get("avg") is not None:
                _mlflow_module.log_metric(
                    f"{mode}_detection_latency_ms", detection_latency["avg"] * 1000
                )
            sanitization_latency = snapshot["sanitization_latency"]
            if sanitization_latency.get("avg") is not None:
                _mlflow_module.log_metric(
                    f"{mode}_sanitization_latency_ms",
                    sanitization_latency["avg"] * 1000,
                )
        except Exception as mlflow_error:  # pragma: no cover - external dependency
            # Check if the error is due to a deleted/ended run
            error_msg = str(mlflow_error)
            if "deleted" in error_msg.lower() or "not be in the 'active' state" in error_msg:
                # Reset the flag so a new run will be created on the next call
                self._mlflow_run_active = False
                logger.warning(
                    "MLflow run is no longer active, will create new run on next log attempt"
                )
            else:
                logger.warning("Failed to log metrics to MLflow: {}", mlflow_error)

    def _ensure_wandb_run(self) -> None:
        if not settings.ENABLE_WANDB or _wandb_module is None or self._wandb_run is not None:
            return
        try:
            init_kwargs = {
                "project": settings.WANDB_PROJECT or "avi-content-filter",
                "reinit": True,
            }
            if settings.WANDB_ENTITY:
                init_kwargs["entity"] = settings.WANDB_ENTITY
            if settings.WANDB_RUN_NAME:
                init_kwargs["name"] = settings.WANDB_RUN_NAME
            self._wandb_run = _wandb_module.init(**init_kwargs)
        except Exception as wandb_error:  # pragma: no cover - external dependency
            logger.warning("Failed to initialize Weights & Biases logging: {}", wandb_error)
            self._wandb_run = None

    def _log_wandb(
        self,
        mode: str,
        snapshot: dict[str, int | dict[str, float | None]],
        detection_latency: float,
        sanitization_latency: float | None,
    ) -> None:
        if not settings.ENABLE_WANDB or _wandb_module is None:
            return
        self._ensure_wandb_run()
        if self._wandb_run is None:
            return
        payload = {
            f"{mode}/detection_latency_ms": detection_latency * 1000,
            f"{mode}/true_positive": snapshot["true_positive"],
            f"{mode}/false_positive": snapshot["false_positive"],
            f"{mode}/false_negative": snapshot["false_negative"],
            f"{mode}/true_negative": snapshot["true_negative"],
        }
        if sanitization_latency is not None:
            payload[f"{mode}/sanitization_latency_ms"] = sanitization_latency * 1000
        try:
            _wandb_module.log(payload)
        except Exception as wandb_error:  # pragma: no cover - external dependency
            logger.warning("Failed to log metrics to Weights & Biases: {}", wandb_error)

    def record(
        self,
        mode: str | SafetyMode,
        predicted_positive: bool,
        detection_latency_seconds: float,
        actual_positive: bool | None = None,
        sanitization_latency_seconds: float | None = None,
    ) -> None:
        """Record a single observation for a given safety mode."""

        mode_key = mode.value if hasattr(mode, "value") else str(mode)
        with self._lock:
            stats = self._stats.setdefault(mode_key, ModeStats())
            stats.detection_latency.update(detection_latency_seconds)
            if sanitization_latency_seconds is not None:
                stats.sanitization_latency.update(sanitization_latency_seconds)
            stats.record(predicted_positive, actual_positive)
            snapshot = stats.as_dict()
        if settings.PROMETHEUS_ENABLED:
            _detection_latency_metric.labels(mode=mode_key).observe(detection_latency_seconds)
            if sanitization_latency_seconds is not None:
                _sanitization_latency_metric.labels(mode=mode_key).observe(
                    sanitization_latency_seconds
                )
            if actual_positive is not None:
                if predicted_positive and actual_positive:
                    _tp_metric.labels(mode=mode_key).inc()
                elif predicted_positive and not actual_positive:
                    _fp_metric.labels(mode=mode_key).inc()
                elif not predicted_positive and actual_positive:
                    _fn_metric.labels(mode=mode_key).inc()
                else:
                    _tn_metric.labels(mode=mode_key).inc()
        self._log_mlflow(mode_key, snapshot)
        self._log_wandb(
            mode_key,
            snapshot,
            detection_latency_seconds,
            sanitization_latency_seconds,
        )

    def record_component_usage(
        self,
        components_applied: dict[str, bool],
        was_modified: bool,
        is_input: bool = True,
    ) -> None:
        """
        Record which filtering components were applied and whether they modified content.

        Args:
            components_applied: Dict mapping component names to whether they were applied
            was_modified: Whether any component modified the content
            is_input: Whether this is input (True) or output (False) filtering
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        stage = "input" if is_input else "output"

        # Record which components were applied
        for component, was_applied in components_applied.items():
            if was_applied:
                _component_applied_metric.labels(component=component, stage=stage).inc()

        # Record if any modification occurred
        # Track modification per component that was applied
        if was_modified:
            for component, was_applied in components_applied.items():
                if was_applied:
                    # We don't know which specific component did the modification,
                    # so we increment for all applied components
                    _component_modified_metric.labels(component=component, stage=stage).inc()

    def record_input_filter_latency(
        self,
        mode: str,
        component_latencies: dict[str, float],
    ) -> None:
        """
        Record latency for each component during input filtering.

        Args:
            mode: Safety mode (e.g., 'disabled', 'local', 'external', 'hybrid')
            component_latencies: Dict mapping component names to latency in seconds
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        for component, latency in component_latencies.items():
            if latency is not None and latency > 0:
                _input_filter_latency_metric.labels(mode=mode, component=component).observe(latency)

    def record_input_filter_rules_matched(
        self,
        mode: str,
        num_rules: int,
    ) -> None:
        """
        Record the number of rules matched during input filtering.

        Args:
            mode: Safety mode
            num_rules: Number of rules matched
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        if num_rules > 0:
            _input_filter_rules_matched_metric.labels(mode=mode).inc(num_rules)

    def record_output_filter_latency(
        self,
        mode: str,
        component_latencies: dict[str, float],
    ) -> None:
        """
        Record latency for each component during output filtering.

        Args:
            mode: Safety mode
            component_latencies: Dict mapping component names to latency in seconds
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        for component, latency in component_latencies.items():
            if latency is not None and latency > 0:
                _output_filter_latency_metric.labels(mode=mode, component=component).observe(
                    latency
                )

    def record_output_filter_modification(
        self,
        mode: str,
    ) -> None:
        """
        Record that a modification was made during output filtering.

        Args:
            mode: Safety mode
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        _output_filter_modifications_metric.labels(mode=mode).inc()

    def record_linked_docs_retrieval(
        self,
        rule_id: str,
        latency_seconds: float,
        num_docs: int,
    ) -> None:
        """
        Record metrics for linked documents retrieval.

        Args:
            rule_id: ID of the rule for which documents were retrieved
            latency_seconds: Time taken to retrieve documents in seconds
            num_docs: Number of documents retrieved
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        _linked_docs_retrieval_latency_metric.labels(rule_id=rule_id).observe(latency_seconds)
        _linked_docs_count_metric.labels(rule_id=rule_id).observe(num_docs)

    def snapshot(self) -> dict[str, dict[str, int | dict[str, float | None]]]:
        """Return a copy of collected statistics for inspection or reporting."""
        with self._lock:
            return {mode: stats.as_dict() for mode, stats in self._stats.items()}

    def record_indexing_operation(
        self,
        operation: str,
        duration_seconds: float,
        status: str = "success",
        items_processed: dict[str, int] | None = None,
    ) -> None:
        """
        Record metrics for an indexing operation.

        Args:
            operation: Operation name (e.g., 'reindex_all', 'export_csv', 'upload_csv')
            duration_seconds: Duration of the operation in seconds
            status: Operation status ('success' or 'error')
            items_processed: Optional dict mapping item types to counts (e.g., {'rules': 10, 'documents': 50})
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        _indexing_duration_metric.labels(operation=operation, status=status).observe(
            duration_seconds
        )
        _indexing_total_metric.labels(operation=operation, status=status).inc()

        if items_processed:
            for item_type, count in items_processed.items():
                if count > 0:
                    _indexing_items_processed_metric.labels(item_type=item_type).inc(count)

    def record_csv_upload(
        self,
        file_type: str,
        file_size_bytes: int,
    ) -> None:
        """
        Record metrics for CSV file upload.

        Args:
            file_type: Type of CSV file ('rules', 'documents', or 'links')
            file_size_bytes: Size of the uploaded file in bytes
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        _csv_upload_size_metric.labels(file_type=file_type).observe(file_size_bytes)

    def record_filter_quality(
        self,
        direction: str,
        true_positives: int,
        false_positives: int,
        false_negatives: int,
    ) -> None:
        """
        Record filter quality metrics (precision, recall, F1).

        Args:
            direction: Filter direction ('input' or 'output')
            true_positives: Number of true positives
            false_positives: Number of false positives
            false_negatives: Number of false negatives
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        # Calculate precision: TP / (TP + FP)
        precision = 0.0
        if true_positives + false_positives > 0:
            precision = true_positives / (true_positives + false_positives)

        # Calculate recall: TP / (TP + FN)
        recall = 0.0
        if true_positives + false_negatives > 0:
            recall = true_positives / (true_positives + false_negatives)

        # Calculate F1: 2 * precision * recall / (precision + recall)
        f1_score = 0.0
        if precision + recall > 0:
            f1_score = 2 * precision * recall / (precision + recall)

        _filter_precision_metric.labels(direction=direction).set(precision)
        _filter_recall_metric.labels(direction=direction).set(recall)
        _filter_f1_score_metric.labels(direction=direction).set(f1_score)

    def record_indexing_embedding_latency(
        self,
        operation: str,
        latency_seconds: float,
    ) -> None:
        """
        Record latency of embedding generation during indexing.

        Args:
            operation: Type of operation ('rules', 'documents')
            latency_seconds: Time taken to generate embeddings
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        _indexing_embedding_latency_metric.labels(operation=operation).observe(latency_seconds)

    def record_indexing_vector_insert_latency(
        self,
        operation: str,
        latency_seconds: float,
    ) -> None:
        """
        Record latency of vector insertion during indexing.

        Args:
            operation: Type of operation ('rules', 'documents', 'links')
            latency_seconds: Time taken to insert vectors
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        _indexing_vector_insert_latency_metric.labels(operation=operation).observe(latency_seconds)

    def record_indexing_rate(
        self,
        operation: str,
        items_count: int,
        duration_seconds: float,
    ) -> None:
        """
        Record indexing rate (items per second).

        Args:
            operation: Type of operation ('rules', 'documents', 'links')
            items_count: Number of items processed
            duration_seconds: Time taken to process items
        """
        if not settings.PROMETHEUS_ENABLED:
            return

        if duration_seconds > 0:
            rate = items_count / duration_seconds
            _indexing_items_per_second_metric.labels(operation=operation).set(rate)


content_filter_metrics = ContentFilterMetrics()

__all__ = ["ContentFilterMetrics", "LatencyStats", "ModeStats", "content_filter_metrics"]
