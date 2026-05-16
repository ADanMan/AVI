from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator

from config.settings import settings


class FilteringOptions(BaseModel):
    """
    Granular configuration for filtering components.

    Allows fine-grained control over which filtering steps are executed
    for input and output processing.
    """

    enable_vector_rules: bool = Field(
        default=True,
        description="Enable vector-based rule matching against filter rule database.",
        json_schema_extra={"example": True},
    )

    enable_safety_llm: bool = Field(
        default=True,
        description="Enable Safety LLM for content sanitization and rephrasing.",
        json_schema_extra={"example": True},
    )

    enable_prompt_modification: bool = Field(
        default=True,
        description="Enable automatic prompt modification when filter rules match (INPUT only).",
        json_schema_extra={"example": True},
    )

    enable_output_cleaning: bool = Field(
        default=True,
        description="Enable output content cleaning to remove system prompts and markers (OUTPUT only).",
        json_schema_extra={"example": True},
    )


class QueryRequest(BaseModel):
    """
    Model for text processing request.
    """

    model_config = {"protected_namespaces": ()}

    query: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="User query text that must be processed safely. Supports up to 100K characters with adaptive processing (chunking for long queries).",
        example="Explain how the AVI system helps moderate AI responses.",
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use caching to speed up repeated requests.",
        example=True,
    )
    model_name: str | None = Field(
        None,
        description="Optional LLM model name if the default value needs to be overridden.",
        example="gpt-4o-mini",
    )
    model_provider: str | None = Field(
        None,
        description="Optional provider identifier used to choose API credentials/endpoints.",
        example="openrouter",
    )
    llm_parameters: dict[str, Any] | None = Field(
        None,
        description="Extra generation parameters for the selected LLM (temperature, max_tokens, etc.).",
        example={"temperature": 0.3, "max_tokens": 512},
    )

    # New granular filtering controls
    input_filtering: FilteringOptions | None = Field(
        default=None,
        description="Detailed filtering configuration for INPUT (user query). If None, uses system defaults.",
        json_schema_extra={
            "example": {
                "enable_vector_rules": True,
                "enable_safety_llm": True,
                "enable_prompt_modification": True,
                "enable_output_cleaning": False,
            }
        },
    )

    output_filtering: FilteringOptions | None = Field(
        default=None,
        description="Detailed filtering configuration for OUTPUT (LLM response). If None, uses system defaults.",
        json_schema_extra={
            "example": {
                "enable_vector_rules": True,
                "enable_safety_llm": False,
                "enable_prompt_modification": False,
                "enable_output_cleaning": True,
            }
        },
    )

    # Legacy fields (for backward compatibility)
    use_llm_filter: bool = Field(
        default=True,
        description="DEPRECATED: Use input_filtering.enable_safety_llm and output_filtering.enable_safety_llm instead. "
        "Whether to enable request and response filtering with the Safety LLM.",
        example=True,
        deprecated=True,
    )
    use_linked_docs: bool = Field(
        default=True,
        description="Whether to retrieve related documents from the knowledge base for RAG context and filtering.",
        example=True,
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        """
        Checks that the query is not empty and contains meaningful text.
        """
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class QueryResponse(BaseModel):
    """
    Model for query response.
    """

    response: str = Field(
        ...,
        description="Generated safe response produced by the model.",
        example="The AVI system analyzes the query, pulls in relevant documents, and filters the answer before returning it.",
    )
    context_used: bool = Field(
        ...,
        description="Indicates whether external knowledge base context was used.",
        example=True,
    )
    relevance_scores: list[float] | None = Field(
        None,
        description="Relevance scores of the retrieved documents.",
        example=[0.92, 0.87],
    )
    rerank_scores: list[float] | None = Field(
        None,
        description="Scores after re-ranking with a cross-encoder.",
        example=[1.32, 0.87],
    )
    processing_time: float | None = Field(
        None,
        description="Total processing time for the query (in seconds).",
        example=0.42,
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the response was generated in ISO 8601 format.",
        example="2024-05-20T10:15:32.451236",
    )
    input_filter_result: "FilterResult | None" = Field(
        None,
        description="Filtering results for the incoming query.",
        example=None,
    )
    output_filter_result: "FilterResult | None" = Field(
        None,
        description="Filtering results for the final response.",
        example=None,
    )


class UpdateThresholdRequest(BaseModel):
    """
    Model for updating relevance threshold request.
    """

    threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="New relevance threshold value for filtering.",
        example=0.75,
    )


class VectorDBStats(BaseModel):
    """Statistics about the vector store of documents and rules."""

    total_documents: int = Field(
        ...,
        description="Number of documents stored in the database.",
        example=150,
    )
    total_rules: int = Field(
        ...,
        description="Number of active filtering rules.",
        example=25,
    )


class CacheStats(BaseModel):
    """Performance indicators for the query and response cache."""

    size: int = Field(
        ...,
        description="Number of entries stored in the cache.",
        example=512,
    )
    hits: int = Field(
        ...,
        description="How many times the system served an answer from the cache.",
        example=340,
    )
    misses: int = Field(
        ...,
        description="How many times the system had to query external services.",
        example=120,
    )
    hit_rate: float = Field(
        ...,
        description="Cache hit ratio expressed as a percentage.",
        example=73.9,
    )


class FilterStats(BaseModel):
    """Current state of the content filtering subsystem."""

    threshold: float = Field(
        ...,
        description="Similarity threshold at which a rule is considered triggered.",
        example=0.8,
    )
    status: str = Field(
        ...,
        description="Filtering status (for example, active or disabled).",
        example="active",
    )


class SystemStats(BaseModel):
    """Summary statistics for the system's key components."""

    vector_db: VectorDBStats = Field(
        ...,
        description="Status of the vector knowledge base.",
        example={"total_documents": 150, "total_rules": 25},
    )
    cache: CacheStats = Field(
        ...,
        description="Cache metrics for responses.",
        example={"size": 512, "hits": 340, "misses": 120, "hit_rate": 73.9},
    )
    filter: FilterStats = Field(
        ...,
        description="Filtering parameters and status.",
        example={"threshold": 0.8, "status": "active"},
    )
    system_status: str = Field(
        ...,
        description="Overall system status (healthy, degraded, etc.).",
        example="healthy",
    )


class DocumentMetadata(BaseModel):
    """Metadata for a document stored for RAG."""

    document_id: str = Field(
        ...,
        description="Unique identifier of the document.",
        example="doc_42",
    )
    source: str = Field(
        ...,
        description="Document source (for example, file, knowledge base, link).",
        example="internal_wiki",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Date and time when the document was added.",
        example="2024-05-20T09:05:00",
    )
    additional_info: dict[str, Any] | None = Field(
        None,
        description="Additional information that helps with debugging or filtering.",
        example={"language": "ru", "owner": "ml-team"},
    )


class Document(BaseModel):
    """Model of a document that is indexed for RAG."""

    text: str = Field(
        ...,
        min_length=1,
        description="Full text of the document.",
        example="AVI helps safely connect an LLM with enterprise data.",
    )
    metadata: DocumentMetadata = Field(
        ...,
        description="Structured metadata for the document.",
        example={
            "document_id": "doc_42",
            "source": "internal_wiki",
            "timestamp": "2024-05-20T09:05:00",
        },
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        """
        Checks that the document text is not empty.
        """
        if not v.strip():
            raise ValueError("Document text cannot be empty")
        return v.strip()


class CSVUploadResponse(BaseModel):
    """Response to uploading a CSV file with documents or rules."""

    status: str = Field(
        ...,
        description="Processing status of the file.",
        example="success",
    )
    processed_documents: int = Field(
        ...,
        description="Number of rows successfully processed from the file.",
        example=125,
    )
    file_name: str = Field(
        ...,
        description="Name of the uploaded file.",
        example="documents_batch.csv",
    )
    errors: list[str] | None = Field(
        None,
        description="List of errors detected during processing.",
        example=["Row 5: missing text column"],
    )
    warnings: list[str] | None = Field(
        None,
        description="List of warnings (for example, missing metadata).",
        example=["Row 8: rule_ids are not provided"],
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when file processing finished.",
        example="2024-05-20T11:02:44",
    )


class HealthCheckResponse(BaseModel):
    """Result of the service health check."""

    status: str = Field(
        ...,
        pattern="^(healthy|unhealthy)$",
        description="Overall system status.",
        example="healthy",
    )
    components: dict[str, str] = Field(
        ...,
        description="Statuses of individual components (LLM, database, cache, etc.).",
        example={"external_llm": "healthy", "vector_db": "healthy"},
    )
    requested_safety_mode: str = Field(
        default="disabled",
        description="Configured operating mode of the safety system.",
        example="hybrid",
    )
    active_safety_mode: str = Field(
        default="disabled",
        description="Mode actually used after fallback logic is applied.",
        example="external",
    )
    stats: dict[str, Any] | None = Field(
        None,
        description="Additional diagnostic data for components.",
        example={"latency_ms": 120},
    )
    error: str | None = Field(
        None,
        description="Error description if the health check failed.",
        example="Vector DB connection timeout",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the check was performed.",
        example="2024-05-20T11:10:00",
    )


class BackupMetadata(BaseModel):
    """Information about a generated backup archive."""

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Date and time when the archive was created.",
        example="2024-05-10T18:30:00",
    )
    total_documents: int = Field(
        ...,
        description="Number of documents included in the archive.",
        example=380,
    )
    file_size: int = Field(
        ...,
        description="Archive size in bytes.",
        example=5242880,
    )
    checksum: str = Field(
        ...,
        description="Checksum of the archive file.",
        example="c0ffee1234abcd",
    )
    version: str = Field(
        default="1.0",
        pattern=r"^\d+\.\d+$",
        description="Version of the backup format.",
        example="1.1",
    )


class ImportRequest(BaseModel):
    """Parameters for importing data into the system."""

    file_path: str = Field(
        ...,
        description="Path to the file that needs to be imported.",
        example="/data/uploads/rules.csv",
    )
    validate_data: bool = Field(
        default=True,
        description="Whether to validate the input data before loading.",
        example=True,
    )
    skip_errors: bool = Field(
        default=False,
        description="Whether to skip problematic rows instead of stopping the process.",
        example=False,
    )
    batch_size: int = Field(
        default=1000,
        gt=0,
        description="Batch size for stepwise data loading.",
        example=500,
    )


class ExportRequest(BaseModel):
    """Parameters for exporting data from the system."""

    export_path: str = Field(
        ...,
        description="Where to store the exported data.",
        example="/data/export/rules.json",
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include document and rule metadata.",
        example=True,
    )
    format: str = Field(
        default="json",
        pattern="^(json|csv)$",
        description="Format of the exported file.",
        example="json",
    )
    compress: bool = Field(
        default=False,
        description="Whether to create a compressed archive during export.",
        example=False,
    )


class SearchFilters(BaseModel):
    """Filters for searching within the vector database."""

    min_relevance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score required for a document to appear in the results.",
        example=0.6,
    )
    max_results: int = Field(
        default=5,
        gt=0,
        description="Maximum number of results to return.",
        example=10,
    )
    metadata_filters: dict[str, Any] | None = Field(
        None,
        description="Additional metadata constraints (category, source, etc.).",
        example={"category": "safety"},
    )
    date_range: dict[str, datetime] | None = Field(
        None,
        description="Date range that the document must fall within.",
        example={
            "start": "2024-01-01T00:00:00",
            "end": "2024-05-20T23:59:59",
        },
    )

    @field_validator("date_range")
    @classmethod
    def validate_date_range(cls, v):
        """Checks the validity of the date range."""
        if v is not None:
            if "start" not in v or "end" not in v:
                raise ValueError("Date range must contain start and end")
            if v["start"] > v["end"]:
                raise ValueError("Start date cannot be later than end date")
        return v


class LLMConfiguration(BaseModel):
    """Configuration options for the primary language model."""

    model: str = Field(
        default=settings.MAIN_LLM_MODEL,
        description="Name of the model to use by default.",
        example="gpt-4o-mini",
    )
    temperature: float = Field(
        default=settings.MAIN_LLM_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="Generation temperature: higher values produce more creative answers.",
        example=0.2,
    )
    max_tokens: int = Field(
        default=settings.MAIN_LLM_MAX_TOKENS,
        gt=0,
        description="Maximum number of tokens in the response.",
        example=800,
    )
    base_url: HttpUrl | None = Field(
        default=None,
        description="Base API URL if it differs from the provider's default.",
        example="https://api.example.com/v1",
    )
    api_type: str = Field(
        default="openai",
        pattern="^(openai|azure|custom)$",
        description="API provider type (openai, azure, custom).",
        example="openai",
    )
    api_version: str | None = Field(
        default=None,
        description="API version (required for Azure).",
        example="2024-02-01",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Request timeout for the external API in seconds.",
        example=45.0,
    )


class LLMConfigurationResponse(BaseModel):
    """Service response with the current LLM settings."""

    configuration: LLMConfiguration = Field(
        ...,
        description="Current connection settings for the model.",
        example={
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "max_tokens": 800,
            "api_type": "openai",
        },
    )
    status: str = Field(
        ...,
        description="Connection status with the LLM API.",
        example="connected",
    )
    last_test_timestamp: datetime | None = Field(
        None,
        description="Time of the last successful connectivity check.",
        example="2024-05-20T11:00:00",
    )
    stats: dict[str, Any] = Field(
        default_factory=dict,
        description="API usage statistics (limits, request counters, etc.).",
        example={"requests_today": 45, "rate_limit_remaining": 95},
    )


class LLMConfigurationUpdate(BaseModel):
    """Partial update payload for LLM settings."""

    model: str | None = Field(
        None,
        description="New model name if a switch is required.",
        example="gpt-4o-mini",
    )
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Updated generation temperature.",
        example=0.1,
    )
    max_tokens: int | None = Field(
        None,
        gt=0,
        description="Updated limit on response length in tokens.",
        example=600,
    )
    base_url: HttpUrl | None = Field(
        None,
        description="Overridden base URL for the service.",
        example="https://azure.openai.azure.com",
    )
    api_type: str | None = Field(
        None,
        pattern="^(openai|azure|custom)$",
        description="New API type when performing a migration.",
        example="azure",
    )
    api_version: str | None = Field(
        None,
        description="API version when using Azure or a custom provider.",
        example="2024-03-15",
    )
    timeout: float | None = Field(
        None,
        gt=0,
        description="Timeout for requests in seconds.",
        example=60.0,
    )


class APICredentials(BaseModel):
    """Credentials for accessing the LLM provider."""

    api_key: SecretStr = Field(
        ...,
        description="Secret API key used to call the LLM service.",
        example=SecretStr("sk-...masked-key..."),
    )
    organization_id: str | None = Field(
        None,
        description="Organization identifier within the provider.",
        example="org-12345",
    )

    class Config:
        """Model settings."""

        json_encoders = {SecretStr: lambda v: "***"}  # Hide value when serializing


class FilteredContent(BaseModel):
    """Base model for a content filtering rule."""

    text: str = Field(
        ...,
        min_length=1,
        description="Rule text describing undesirable content.",
        example="Discriminatory statements based on nationality are not allowed",
    )
    category: str = Field(
        ...,
        description="Risk category associated with the rule.",
        example="discrimination",
    )
    risk_level: int = Field(
        ...,
        ge=1,
        le=5,
        description="Risk level on a scale from 1 (low) to 5 (critical).",
        example=4,
    )
    threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Similarity threshold that triggers the rule.",
        example=0.78,
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        """Text validation for the rule"""
        if not v.strip():
            raise ValueError("Rule text cannot be empty")
        return v.strip()


class FilterMatch(BaseModel):
    """Details about a triggered filtering rule."""

    rule_id: str = Field(
        ...,
        description="Identifier of the rule that matched.",
        example="rule-toxic-001",
    )
    rule_text: str = Field(
        ...,
        description="Text of the rule that matched the query or response.",
        example="Offensive statements targeting social groups are prohibited",
    )
    category: str = Field(
        ...,
        description="Risk category of the triggered rule.",
        example="toxicity",
    )
    risk_level: int = Field(
        ...,
        ge=1,
        le=5,
        description="Risk level for the triggered rule.",
        example=5,
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score between the text and the rule.",
        example=0.86,
    )


class FilterResult(BaseModel):
    """Result produced by the filter for a specific text."""

    original_text: str = Field(
        ...,
        description="Original text before filtering.",
        example="Why are some nations considered better than others?",
    )
    modified_text: str | None = Field(
        None,
        description="Modified text when the system rewrites the query.",
        example="Explain the principles of cross-cultural respect in modern society.",
    )
    was_modified: bool = Field(
        ...,
        description="Indicates whether the text was modified by the system.",
        example=True,
    )
    matches: list[FilterMatch] = Field(
        default_factory=list,
        description="List of rules that were triggered during validation.",
        example=[
            {
                "rule_id": "rule-toxic-001",
                "rule_text": "Offensive statements are prohibited",
                "category": "toxicity",
                "risk_level": 5,
                "relevance_score": 0.86,
            }
        ],
    )
    processed_at: datetime = Field(
        default_factory=datetime.now,
        description="Time when the text was processed.",
        example="2024-05-20T11:05:12",
    )
    safety_mode: str | None = Field(
        None,
        description="Active safety mode used during the check.",
        example="local",
    )
    detection_latency_ms: float | None = Field(
        None,
        description="Latency of the rule detection stage in milliseconds.",
        example=12.4,
    )
    sanitization_latency_ms: float | None = Field(
        None,
        description="Latency of the optional sanitization stage in milliseconds.",
        example=38.2,
    )
    latency_ms: float | None = Field(
        None,
        description=(
            "Deprecated alias for detection_latency_ms retained for backwards compatibility."
        ),
        example=12.4,
    )

    # Component tracking for metrics and debugging
    components_applied: dict[str, bool] = Field(
        default_factory=dict,
        description="Tracks which filtering components were applied during processing.",
        json_schema_extra={
            "example": {
                "vector_rules": True,
                "safety_llm": False,
                "prompt_modification": True,
                "output_cleaning": False,
            }
        },
    )

    component_latencies_ms: dict[str, float] | None = Field(
        None,
        description="Detailed latency breakdown by filtering component in milliseconds.",
        json_schema_extra={
            "example": {
                "vector_rules": 12.4,
                "prompt_modification": 2.1,
                "safety_llm": 38.2,
                "output_cleaning": 5.3,
            }
        },
    )


class EnhancedQueryResponse(QueryResponse):
    """Extended query response that includes filtering details."""

    input_filter_result: FilterResult | None = Field(
        None,
        description="Result of validating the user's original query.",
        example=None,
    )
    output_filter_result: FilterResult | None = Field(
        None,
        description="Result of post-filtering the model's response.",
        example=None,
    )


class RuleDocument(BaseModel):
    """Link between a rule and a document in the store."""

    rule_id: str = Field(
        ...,
        description="Identifier of the filtering rule.",
        example="rule-toxic-001",
    )
    document_id: str = Field(
        ...,
        description="Identifier of the document associated with the rule.",
        example="doc_42",
    )
    is_approved: bool = Field(
        default=False,
        description="Indicates whether the link has been approved by a moderator.",
        example=True,
    )
    relevance_score: float | None = Field(
        None,
        description="Relevance score for the link during automatic matching.",
        example=0.91,
    )


class EnhancedFilteredContent(BaseModel):
    """Extended filtering rule that lists linked documents."""

    text: str = Field(
        ...,
        min_length=1,
        description="Filtering rule text.",
        example="Do not allow calls for violence",
    )
    category: str = Field(
        ...,
        description="Risk category for the rule.",
        example="violence",
    )
    risk_level: int = Field(
        ...,
        ge=1,
        le=5,
        description="Risk level of the rule.",
        example=5,
    )
    threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Similarity threshold that activates the rule.",
        example=0.8,
    )
    linked_documents: list[str] = Field(
        default_factory=list,
        description="Identifiers of documents supporting the rule.",
        example=["doc_violence_guidelines", "doc_community_rules"],
    )


class EnhancedDocument(BaseModel):
    """Knowledge base document enriched with rule information."""

    text: str = Field(
        ...,
        description="Full text of the document.",
        example="The document outlines a zero-tolerance policy toward discrimination.",
    )
    metadata: DocumentMetadata = Field(
        ...,
        description="Document metadata.",
        example={
            "document_id": "doc_policy_01",
            "source": "compliance_portal",
            "timestamp": "2024-04-10T08:00:00",
        },
    )
    linked_rules: list[str] = Field(
        default_factory=list,
        description="List of rule identifiers linked to the document.",
        example=["rule-toxic-001", "rule-bias-007"],
    )


class RuleLinkRequest(BaseModel):
    """Request to link a rule with documents."""

    rule_id: str = Field(
        ...,
        description="Rule that should be linked to documents.",
        example="rule-bias-002",
    )
    document_ids: list[str] = Field(
        ...,
        description="Identifiers of the documents to associate.",
        example=["doc_11", "doc_12"],
    )
    is_approved: bool = Field(
        default=True,
        description="Whether the link should be marked as approved immediately.",
        example=True,
    )


class RuleLinkResponse(BaseModel):
    """Service response after creating links between rules and documents."""

    success: bool = Field(
        ...,
        description="Indicates whether the operation was successful.",
        example=True,
    )
    message: str = Field(
        ...,
        description="Human-readable description of the outcome.",
        example="Links created successfully",
    )
    created_links: list[RuleDocument] = Field(
        ...,
        description="List of created links with details.",
        example=[
            {
                "rule_id": "rule-bias-002",
                "document_id": "doc_11",
                "is_approved": True,
                "relevance_score": 0.88,
            }
        ],
    )


# ========== Configuration Management Schemas ==========


class LLMConfigUpdate(BaseModel):
    """Request schema for updating LLM configuration."""

    model: str | None = Field(
        None,
        min_length=1,
        description="LLM model name or identifier.",
        example="openai/gpt-4o-mini",
    )
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0).",
        example=0.7,
    )
    max_tokens: int | None = Field(
        None,
        gt=0,
        description="Maximum tokens in response.",
        example=2000,
    )
    top_p: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter (0.0-1.0).",
        example=1.0,
    )
    timeout: float | None = Field(
        None,
        gt=0,
        description="Request timeout in seconds.",
        example=30.0,
    )
    system_prompt: str | None = Field(
        None,
        description="Custom system prompt.",
        example="You are a helpful assistant.",
    )


class LLMConfigResponse(BaseModel):
    """Response schema for LLM configuration."""

    main: dict[str, Any] = Field(
        ...,
        description="Main LLM configuration.",
        example={
            "model": "openai/gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2000,
            "api_key": "***",
        },
    )
    safety: dict[str, Any] | None = Field(
        None,
        description="Safety LLM configuration (if configured).",
        example=None,
    )
    scoring: dict[str, Any] | None = Field(
        None,
        description="Scoring LLM configuration (if configured).",
        example=None,
    )


class RAGConfigUpdate(BaseModel):
    """Request schema for updating RAG configuration."""

    threshold: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Relevance threshold for document retrieval (0.0-1.0).",
        example=0.75,
    )
    rerank_enabled: bool | None = Field(
        None,
        description="Enable reranking of retrieved documents.",
        example=True,
    )
    rerank_candidate_count: int | None = Field(
        None,
        gt=0,
        description="Number of candidates to rerank.",
        example=15,
    )
    rerank_model_name: str | None = Field(
        None,
        min_length=1,
        description="Reranking model name.",
        example="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    rerank_score_threshold: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum reranking score threshold.",
        example=0.0,
    )
    rerank_max_length: int | None = Field(
        None,
        gt=0,
        description="Maximum text length for reranking.",
        example=512,
    )


class RAGConfigResponse(BaseModel):
    """Response schema for RAG configuration."""

    threshold: float = Field(..., description="Current relevance threshold.")
    rerank_enabled: bool = Field(..., description="Whether reranking is enabled.")
    rerank_candidate_count: int = Field(..., description="Number of rerank candidates.")
    rerank_model_name: str = Field(..., description="Reranking model name.")
    rerank_score_threshold: float = Field(..., description="Reranking score threshold.")
    rerank_max_length: int = Field(..., description="Maximum text length for reranking.")


class CacheConfigUpdate(BaseModel):
    """Request schema for updating cache configuration."""

    ttl: int | None = Field(
        None,
        gt=0,
        description="Cache TTL in seconds.",
        example=3600,
    )
    backend: str | None = Field(
        None,
        pattern="^(memory|redis)$",
        description="Cache backend: 'memory' or 'redis'.",
        example="memory",
    )
    redis_url: str | None = Field(
        None,
        description="Redis connection URL (required if backend is redis).",
        example="redis://localhost:6379/0",
    )
    redis_host: str | None = Field(
        None,
        description="Redis host.",
        example="localhost",
    )
    redis_port: int | None = Field(
        None,
        gt=0,
        le=65535,
        description="Redis port.",
        example=6379,
    )
    redis_db: int | None = Field(
        None,
        ge=0,
        description="Redis database number.",
        example=0,
    )


class CacheConfigResponse(BaseModel):
    """Response schema for cache configuration."""

    ttl: int = Field(..., description="Cache TTL in seconds.")
    backend: str = Field(..., description="Cache backend (memory or redis).")
    redis_url: str | None = Field(None, description="Redis connection URL.")
    redis_host: str = Field(..., description="Redis host.")
    redis_port: int = Field(..., description="Redis port.")
    redis_db: int = Field(..., description="Redis database number.")


class SafetyConfigUpdate(BaseModel):
    """Request schema for updating safety configuration."""

    mode: str | None = Field(
        None,
        pattern="^(disabled|external|local|hybrid|plugin)$",
        description="Safety mode: disabled, external, local, hybrid, or plugin.",
        example="disabled",
    )
    stream_guard_mode: str | None = Field(
        None,
        pattern="^(rule-only|llm-only|hybrid|bypass)$",
        description="Stream guard mode: rule-only, llm-only, hybrid, or bypass.",
        example="hybrid",
    )


class SafetyConfigResponse(BaseModel):
    """Response schema for safety configuration."""

    mode: str = Field(..., description="Configured safety mode.")
    active_mode: str = Field(..., description="Actually active safety mode.")
    stream_guard_mode: str = Field(..., description="Stream guard mode.")


class RateLimitConfigUpdate(BaseModel):
    """Request schema for updating rate limiting configuration."""

    enabled: bool | None = Field(
        None,
        description="Enable or disable rate limiting.",
        example=True,
    )
    default_limit: str | None = Field(
        None,
        pattern=r"^\d+/(second|minute|hour|day)$",
        description="Default rate limit (format: 'N/unit').",
        example="100/minute",
    )
    query_limit: str | None = Field(
        None,
        pattern=r"^\d+/(second|minute|hour|day)$",
        description="Rate limit for query endpoints.",
        example="30/minute",
    )
    upload_limit: str | None = Field(
        None,
        pattern=r"^\d+/(second|minute|hour|day)$",
        description="Rate limit for upload endpoints.",
        example="10/minute",
    )
    admin_limit: str | None = Field(
        None,
        pattern=r"^\d+/(second|minute|hour|day)$",
        description="Rate limit for admin endpoints.",
        example="50/minute",
    )


class RateLimitConfigResponse(BaseModel):
    """Response schema for rate limiting configuration."""

    enabled: bool = Field(..., description="Whether rate limiting is enabled.")
    default_limit: str = Field(..., description="Default rate limit.")
    query_limit: str = Field(..., description="Query endpoint rate limit.")
    upload_limit: str = Field(..., description="Upload endpoint rate limit.")
    admin_limit: str = Field(..., description="Admin endpoint rate limit.")
    redis_url: str | None = Field(None, description="Redis URL for distributed rate limiting.")


class MonitoringConfigUpdate(BaseModel):
    """Request schema for updating monitoring configuration."""

    prometheus_enabled: bool | None = Field(
        None,
        description="Enable Prometheus metrics.",
        example=True,
    )
    prometheus_route: str | None = Field(
        None,
        pattern=r"^/.*",
        description="Prometheus metrics endpoint route.",
        example="/metrics",
    )
    otel_enabled: bool | None = Field(
        None,
        description="Enable OpenTelemetry tracing.",
        example=False,
    )
    otel_service_name: str | None = Field(
        None,
        min_length=1,
        description="OpenTelemetry service name.",
        example="avi-api",
    )
    otel_endpoint: str | None = Field(
        None,
        description="OpenTelemetry collector endpoint.",
        example="http://tempo:4318/v1/traces",
    )
    mlflow_enabled: bool | None = Field(
        None,
        description="Enable MLflow logging.",
        example=False,
    )
    mlflow_tracking_uri: str | None = Field(
        None,
        description="MLflow tracking server URI.",
        example="http://mlflow:5000",
    )
    wandb_enabled: bool | None = Field(
        None,
        description="Enable Weights & Biases logging.",
        example=False,
    )
    wandb_project: str | None = Field(
        None,
        description="W&B project name.",
        example="avi-metrics",
    )


class MonitoringConfigResponse(BaseModel):
    """Response schema for monitoring configuration."""

    prometheus_enabled: bool = Field(..., description="Prometheus metrics enabled.")
    prometheus_route: str = Field(..., description="Prometheus endpoint route.")
    otel_enabled: bool = Field(..., description="OpenTelemetry enabled.")
    otel_service_name: str = Field(..., description="OpenTelemetry service name.")
    otel_endpoint: str | None = Field(None, description="OpenTelemetry endpoint.")
    mlflow_enabled: bool = Field(..., description="MLflow enabled.")
    mlflow_tracking_uri: str | None = Field(None, description="MLflow tracking URI.")
    mlflow_experiment_name: str = Field(..., description="MLflow experiment name.")
    wandb_enabled: bool = Field(..., description="Weights & Biases enabled.")
    wandb_project: str | None = Field(None, description="W&B project name.")


class IndexingConfigUpdate(BaseModel):
    """Request schema for updating indexing configuration."""

    enabled: bool | None = Field(
        None,
        description="Enable or disable document indexing.",
        example=True,
    )
    batch_size: int | None = Field(
        None,
        gt=0,
        description="Batch size for indexing operations.",
        example=100,
    )
    auto_reindex_on_startup: bool | None = Field(
        None,
        description="Automatically reindex on system startup.",
        example=False,
    )
    index_documents: bool | None = Field(
        None,
        description="Enable document indexing.",
        example=True,
    )
    index_rules: bool | None = Field(
        None,
        description="Enable rule indexing.",
        example=True,
    )


class IndexingConfigResponse(BaseModel):
    """Response schema for indexing configuration."""

    enabled: bool = Field(..., description="Whether indexing is enabled.")
    batch_size: int = Field(..., description="Batch size for indexing operations.")
    auto_reindex_on_startup: bool = Field(..., description="Auto-reindex on startup.")
    index_documents: bool = Field(..., description="Document indexing enabled.")
    index_rules: bool = Field(..., description="Rule indexing enabled.")


class FilteringConfigUpdate(BaseModel):
    """Update schema for default filtering configuration."""

    default_input_filtering: FilteringOptions | None = Field(
        None, description="Default filtering options for INPUT (user queries)."
    )
    default_output_filtering: FilteringOptions | None = Field(
        None, description="Default filtering options for OUTPUT (LLM responses)."
    )


class FilteringConfigResponse(BaseModel):
    """Response schema for default filtering configuration."""

    default_input_filtering: FilteringOptions = Field(
        ..., description="Default filtering options for INPUT (user queries)."
    )
    default_output_filtering: FilteringOptions = Field(
        ..., description="Default filtering options for OUTPUT (LLM responses)."
    )


class SystemSettingsResponse(BaseModel):
    """Response schema for complete system settings."""

    llm: LLMConfigResponse = Field(..., description="LLM configurations.")
    rag: RAGConfigResponse = Field(..., description="RAG configuration.")
    cache: CacheConfigResponse = Field(..., description="Cache configuration.")
    safety: SafetyConfigResponse = Field(..., description="Safety configuration.")
    rate_limit: RateLimitConfigResponse = Field(..., description="Rate limiting configuration.")
    monitoring: MonitoringConfigResponse = Field(..., description="Monitoring configuration.")
    indexing: IndexingConfigResponse = Field(..., description="Indexing configuration.")
    filtering: FilteringConfigResponse = Field(..., description="Filtering configuration.")
    timestamp: datetime = Field(..., description="Timestamp of settings snapshot.")


class ConfigUpdateResponse(BaseModel):
    """Generic response for configuration updates."""

    status: str = Field(..., description="Update status.", json_schema_extra={"example": "updated"})
    category: str = Field(
        ..., description="Configuration category.", json_schema_extra={"example": "llm"}
    )
    config: dict[str, Any] = Field(..., description="Updated configuration.")
    timestamp: datetime = Field(..., description="Update timestamp.")


# ========== Indexing Status Schemas ==========


class IndexingStatus(BaseModel):
    """Current status of the indexing operation."""

    status: str = Field(
        ...,
        pattern="^(idle|in_progress|completed|failed)$",
        description="Current indexing status: idle, in_progress, completed, or failed.",
        example="in_progress",
    )
    progress_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Progress percentage (0-100).",
        example=45.5,
    )
    indexed_rules: int = Field(
        default=0,
        ge=0,
        description="Number of rules that have been indexed.",
        example=25,
    )
    indexed_documents: int = Field(
        default=0,
        ge=0,
        description="Number of documents that have been indexed.",
        example=150,
    )
    indexed_links: int = Field(
        default=0,
        ge=0,
        description="Number of links that have been indexed.",
        example=75,
    )
    total_rules: int = Field(
        default=0,
        ge=0,
        description="Total number of rules to index.",
        example=50,
    )
    total_documents: int = Field(
        default=0,
        ge=0,
        description="Total number of documents to index.",
        example=300,
    )
    total_links: int = Field(
        default=0,
        ge=0,
        description="Total number of links to index.",
        example=150,
    )
    start_time: datetime | None = Field(
        None,
        description="Time when indexing started.",
        example="2024-05-20T10:00:00",
    )
    end_time: datetime | None = Field(
        None,
        description="Time when indexing completed or failed.",
        example="2024-05-20T10:05:30",
    )
    duration_seconds: float | None = Field(
        None,
        ge=0,
        description="Duration of indexing operation in seconds.",
        example=330.5,
    )
    error_message: str | None = Field(
        None,
        description="Error message if indexing failed.",
        example="Failed to connect to vector database",
    )
    current_operation: str | None = Field(
        None,
        description="Description of the current indexing operation.",
        example="Indexing documents",
    )


class IndexingStatusResponse(BaseModel):
    """Response schema for indexing status endpoint."""

    status: IndexingStatus = Field(..., description="Current indexing status.")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when status was retrieved.",
        example="2024-05-20T10:02:30",
    )


# ========== Safety Checking Schemas ==========


class SafetyScores(BaseModel):
    """
    Safety scores for a message.

    Dynamic model that accepts any filter scores from backend configuration.
    Common fields: overall, toxicity, pii, prompt_injection, hate_speech.
    """

    model_config = {"extra": "allow"}  # Allow dynamic filter fields

    overall: float = Field(..., ge=0.0, le=1.0, description="Overall safety score (minimum of all scores)")


class SafetyCheckRequest(BaseModel):
    """Safety check request."""

    text: str = Field(..., description="Text to check")
    checks: list[str] | None = Field(None, description="Specific checks to run")


# ========== Prompt Template Management Schemas ==========


class PromptTemplateResponse(BaseModel):
    """Response schema for getting current prompt template."""

    template: str = Field(
        ...,
        description="Current prompt modification template with {text} and {context} placeholders.",
        example=(
            "Remember to adhere to safety guidelines and answer ethically. "
            "User question: USER QUESTION: {text}\n"
            "CONTEXT: {context}\n"
        ),
    )
    required_variables: list[str] = Field(
        default=["text", "context"],
        description="List of required variables that must be present in the template.",
        example=["text", "context"],
    )


class PromptTemplateUpdateRequest(BaseModel):
    """Request schema for updating prompt template."""

    template: str = Field(
        ...,
        min_length=1,
        description="New prompt template. Must contain {text} and {context} variables.",
        example="Instruction: {text}\nContext: {context}",
    )

    @field_validator("template")
    @classmethod
    def validate_required_variables(cls, v: str) -> str:
        """Validate that template contains required variables."""
        if "{text}" not in v:
            raise ValueError("Template must contain {text} variable")
        if "{context}" not in v:
            raise ValueError("Template must contain {context} variable")
        return v


class PromptPreviewRequest(BaseModel):
    """Request schema for previewing prompt with actual query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="User query to preview with the template. Supports up to 100K characters.",
        example="How do I implement authentication?",
    )
    use_rag: bool = Field(
        default=True,
        description="Whether to include RAG context in the preview.",
        example=True,
    )
    use_linked_docs: bool = Field(
        default=True,
        description="Whether to use linked documents for RAG context.",
        example=True,
    )


class PromptPreviewResponse(BaseModel):
    """Response schema for prompt preview."""

    original_query: str = Field(
        ...,
        description="Original user query before any modifications.",
        example="How do I implement authentication?",
    )
    final_prompt: str = Field(
        ...,
        description="Final prompt text with template applied and context injected.",
        example=(
            "Remember to adhere to safety guidelines and answer ethically. "
            "User question: USER QUESTION: How do I implement authentication?\n"
            "CONTEXT: Source: auth_docs\nUse OAuth 2.0...\n"
        ),
    )
    context_used: str | None = Field(
        None,
        description="RAG context that was retrieved and injected into the template.",
        example="Source: auth_docs\nUse OAuth 2.0 for authentication...",
    )
    context_documents: list[dict[str, Any]] | None = Field(
        None,
        description="List of documents retrieved for RAG context with metadata.",
        example=[
            {
                "text": "OAuth 2.0 is recommended...",
                "metadata": {"source": "auth_docs"},
                "relevance_score": 0.92,
            }
        ],
    )
    template_used: str = Field(
        ...,
        description="Template that was used to generate the final prompt.",
        example=(
            "Remember to adhere to safety guidelines and answer ethically. "
            "User question: USER QUESTION: {text}\n"
            "CONTEXT: {context}\n"
        ),
    )
    processing_time: float = Field(
        ...,
        description="Time taken to build the preview (in seconds).",
        example=0.12,
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when preview was generated.",
        example="2024-05-20T10:15:32.451236",
    )
