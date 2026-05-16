import json
import time
from collections.abc import Callable
from typing import Any

from config.settings import settings
from src.core.cache_system import CacheSystem, create_cache_system
from src.core.content_filter import ContentFilterService, create_content_filter_service
from src.models.schemas import EnhancedQueryResponse, FilteringOptions, FilterMatch
from src.services.filter_service import FilterService
from src.services.indexing_service import IndexingService
from src.services.links_manager import LinksManager
from src.services.llm_adapter import LLMAdapter
from src.services.query_processor import QueryProcessor
from src.services.rag_service import RAGService
from src.services.vector_db import VectorDBClient, VectorDBService
from src.utils.logger import logger


class RAGSystem:
    """Coordinate vector search, LLM calls, filtering, and indexing services for RAG."""

    def __init__(
        self,
        vector_db: VectorDBClient | None = None,
        llm_adapter: LLMAdapter | None = None,
        content_filter: ContentFilterService | None = None,
        cache: CacheSystem | None = None,
        threshold: float = settings.RAG_THRESHOLD,
        indexing_service: IndexingService | None = None,
        links_manager: LinksManager | None = None,
        filter_service: FilterService | None = None,
        query_processor: QueryProcessor | None = None,
    ):
        """Initialize the system with explicit or default service implementations."""
        self.vector_db = vector_db or VectorDBService()
        self.llm_adapter = llm_adapter or LLMAdapter(role="external")
        self.external_llm = self.llm_adapter
        self.content_filter = content_filter or create_content_filter_service(
            vector_db=self.vector_db
        )
        self.cache = cache or create_cache_system()
        self.threshold = threshold
        self.indexing_service = indexing_service or IndexingService(self.vector_db)
        self.links_manager = links_manager or LinksManager(self.vector_db)
        self.filter_service = filter_service or FilterService(self.vector_db)
        self.query_processor = query_processor or QueryProcessor(llm_adapter=self.llm_adapter)

        self._default_llm_adapter = self.llm_adapter
        self._default_rag_service = RAGService(llm_adapter=self._default_llm_adapter)
        self.rag_service = self._default_rag_service

        # Track whether the system is currently in dedicated indexing mode
        self._indexing_enabled: bool = False

        logger.info("RAG system initialized with query processor for long queries")

    async def process_query(
        self,
        query: str,
        use_cache: bool = True,
        use_llm_filter: bool = False,  # DEPRECATED: use input_filtering.enable_safety_llm
        use_linked_docs: bool = True,
        rag_mode: bool = True,
        is_input: bool = True,
        model_name: str | None = None,
        model_provider: str | None = None,
        llm_parameters: dict[str, Any] | None = None,
        # New granular filtering controls
        input_filtering: "FilteringOptions | None" = None,
        output_filtering: "FilteringOptions | None" = None,
    ) -> EnhancedQueryResponse:
        """Process a query end-to-end and return an enriched response payload."""
        start_time = time.time()
        params_key = json.dumps(llm_parameters, sort_keys=True) if llm_parameters else ""
        cache_key = (
            f"{query}_{rag_mode}_{use_llm_filter}_{use_linked_docs}_"
            f"{model_name}_{model_provider or ''}_{params_key}"
        )

        # Apply default filtering options if not provided
        input_opts = input_filtering or FilteringOptions()
        output_opts = output_filtering or FilteringOptions()

        # Backward compatibility: if use_llm_filter is explicitly set, override input_opts
        if use_llm_filter and input_filtering is None:
            logger.warning(
                "use_llm_filter is deprecated. Use input_filtering.enable_safety_llm instead."
            )
            input_opts.enable_safety_llm = use_llm_filter

        current_llm_adapter: LLMAdapter
        current_rag_service: RAGService

        if model_name and model_name.strip():
            provider_value = (model_provider or "openrouter").strip().lower()
            adapter_role = provider_value or "external"
            # Create new instances for a specific provider/model combination
            current_llm_adapter = LLMAdapter(
                role=adapter_role,
                provider=provider_value,
                model_name_override=model_name.strip(),
                llm_parameters=llm_parameters,
            )
            current_rag_service = RAGService(llm_adapter=current_llm_adapter)
            logger.info(
                "Using dynamic LLM: %s (provider=%s) with custom params: %s",
                model_name.strip(),
                provider_value,
                llm_parameters,
            )
        else:
            # Using default instances
            current_llm_adapter = self._default_llm_adapter
            current_rag_service = self._default_rag_service
            logger.info("Using default LLM")

        try:
            if use_cache:
                cached_response = self.cache.get(cache_key)
                if cached_response:
                    logger.info("Response obtained from cache")
                    return EnhancedQueryResponse(**cached_response)

            # STEP 1: Process query adaptively (handles long queries)
            processed_query = await self.query_processor.process_query(query)
            logger.info(
                f"Query processed with strategy: {processed_query.strategy}, "
                f"generated {len(processed_query.search_queries)} search queries"
            )

            # STEP 2: INPUT filtering - use first search query for filtering
            input_filter_result = await self.filter_service.filter_input(
                processed_query.search_queries[0],
                use_llm=input_opts.enable_safety_llm,
                use_linked_docs=use_linked_docs,
                enable_vector_rules=input_opts.enable_vector_rules,
                enable_prompt_modification=input_opts.enable_prompt_modification,
            )
            effective_query = input_filter_result.modified_text or processed_query.search_queries[0]

            context_docs = None
            response = ""
            used_context = False
            relevance_scores_list = None
            rerank_scores_list = None

            if rag_mode:
                if use_linked_docs and input_filter_result.matches:
                    logger.info(
                        "Input filter matched rules; retrieving linked documents for context."
                    )
                    context_docs = await self._get_context_from_matches(input_filter_result.matches)
                    if context_docs:
                        logger.info(f"Retrieved {len(context_docs)} linked documents for context.")
                        used_context = True
                        relevance_scores_list = [doc.get("relevance_score") for doc in context_docs]

                        # Re-run filter_input with context_docs to update modified_text
                        input_filter_result = await self.filter_service.filter_input(
                            query,
                            use_llm=input_opts.enable_safety_llm,
                            use_linked_docs=use_linked_docs,
                            context_docs=context_docs,
                            enable_vector_rules=input_opts.enable_vector_rules,
                            enable_prompt_modification=input_opts.enable_prompt_modification,
                        )
                        effective_query = input_filter_result.modified_text or query
                    else:
                        logger.info(
                            "No linked documents found for matched rules; falling back to vector search."
                        )

                if not context_docs:
                    from config.settings import settings

                    # STEP 3: Multi-query RAG search for long queries
                    all_docs = []
                    for idx, search_query in enumerate(processed_query.search_queries):
                        logger.info(
                            f"Performing vector search {idx+1}/{len(processed_query.search_queries)}: "
                            f"{search_query[:100]}..."
                        )
                        docs = await current_rag_service.retrieve_context(
                            search_query, top_k=settings.RAG_CANDIDATE_COUNT
                        )
                        if docs:
                            all_docs.extend(docs)

                    # STEP 4: Deduplicate and rank documents
                    if all_docs:
                        context_docs = self._deduplicate_documents(all_docs)
                        used_context = True
                        relevance_scores_list = [doc.get("relevance_score") for doc in context_docs]
                        if any("rerank_score" in doc for doc in context_docs):
                            rerank_scores_list = [doc.get("rerank_score") for doc in context_docs]
                        logger.info(
                            f"Retrieved {len(all_docs)} total docs, "
                            f"deduplicated to {len(context_docs)} unique documents"
                        )
                    else:
                        logger.info("No relevant documents found via vector search.")

                context_string = (
                    "\n\n".join(
                        [
                            f"Source: {doc.get('metadata', {}).get('source', 'N/A')}\n{doc.get('text', '')}"
                            for doc in context_docs
                        ]
                    )
                    if context_docs
                    else None
                )

                # STEP 5: Generate response.
                # If governance rules matched, inject a strict system prompt that blocks
                # parametric bypass (LLM reasoning about restricted topics from training
                # knowledge), and use the effective_query (which carries the governed
                # user-message preamble) instead of the raw full_context.
                if input_filter_result.matches:
                    from config.settings import settings as _settings

                    # Extract the highest-scoring matched rule text as the active policy
                    top_match = max(
                        input_filter_result.matches,
                        key=lambda m: getattr(m, "score", 0.0),
                    )
                    policy_text = getattr(top_match, "rule_text", "Disclose no restricted information.")

                    governed_system_prompt = _settings.GOVERNED_SYSTEM_PROMPT.format(
                        policy_text=policy_text,
                        compliant_example=_settings.GOVERNED_COMPLIANT_EXAMPLE,
                    )

                    # Temporarily override system_prompt on the adapter
                    _original_system_prompt = current_llm_adapter.system_prompt
                    current_llm_adapter.system_prompt = governed_system_prompt
                    try:
                        response = await current_llm_adapter.generate_response(
                            effective_query, context=context_string
                        )
                    finally:
                        # Always restore original system_prompt to avoid side-effects
                        current_llm_adapter.system_prompt = _original_system_prompt
                else:
                    response = await current_llm_adapter.generate_response(
                        processed_query.full_context, context=context_string
                    )

            else:
                response = await current_rag_service.generate_direct(effective_query)
                used_context = False
                relevance_scores_list = None

            # OUTPUT filtering with granular control
            output_filter_check = await self.filter_service.filter_output(
                response,
                use_linked_docs=use_linked_docs,
                context_docs=context_docs,
                use_llm=output_opts.enable_safety_llm,
                enable_vector_rules=output_opts.enable_vector_rules,
                enable_output_cleaning=output_opts.enable_output_cleaning,
            )
            final_response_text = output_filter_check.modified_text or response
            final_output_filter_result = output_filter_check

            result = EnhancedQueryResponse(
                response=final_response_text,
                context_used=used_context,
                relevance_scores=relevance_scores_list,
                rerank_scores=rerank_scores_list,
                processing_time=time.time() - start_time,
                input_filter_result=input_filter_result,
                output_filter_result=final_output_filter_result,
            )
            if use_cache:
                self.cache.set(cache_key, result.model_dump())
            return result
        except Exception as e:
            logger.error(f"Critical error processing query: {e!s}")
            logger.exception(e)
            error_response = EnhancedQueryResponse(
                response="Sorry, an internal error occurred while processing your request.",
                context_used=False,
                relevance_scores=None,
                processing_time=time.time() - start_time,
                input_filter_result=None,
                output_filter_result=None,
            )
            return error_response

    async def _get_context_from_matches(self, matches: list[FilterMatch]) -> list[dict] | None:
        """Collect linked documents for each matched rule and annotate their relevance."""
        try:
            context_docs = []
            processed_doc_ids = set()  # Prevent duplicates in the aggregated context

            # Sort matches by relevance to prioritize the strongest signals
            sorted_matches = sorted(matches, key=lambda x: x.relevance_score, reverse=True)

            for match in sorted_matches:
                # Retrieve approved documents linked to each rule
                linked_docs = await self.vector_db.get_documents_for_rule(
                    rule_id=match.rule_id, only_approved=True
                )

                if linked_docs:
                    for doc in linked_docs:
                        doc_id = doc.get("document_id")
                        if doc_id and doc_id not in processed_doc_ids:
                            # Propagate the originating rule's relevance score to the document
                            doc["relevance_score"] = match.relevance_score
                            context_docs.append(doc)
                            processed_doc_ids.add(doc_id)

            # Sort the final document list by relevance as a guardrail
            if context_docs:
                context_docs.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                # Optionally trim to a maximum number of documents if future needs require it
                return context_docs

            return None

        except Exception as e:
            logger.error(f"Error getting context from rules: {e!s}")
            return None

    def _deduplicate_documents(self, documents: list[dict]) -> list[dict]:
        """
        Deduplicate documents by ID and aggregate scores.

        For duplicate documents, keeps the highest relevance/rerank scores.

        Args:
            documents: List of document dicts with potential duplicates

        Returns:
            Deduplicated list sorted by score (descending)
        """
        seen_ids = {}

        for doc in documents:
            doc_id = doc.get("metadata", {}).get("document_id") or doc.get("document_id")

            if not doc_id:
                # No ID, treat as unique
                doc_id = f"_no_id_{id(doc)}"

            if doc_id not in seen_ids:
                seen_ids[doc_id] = doc
            else:
                # Merge scores - keep highest
                existing = seen_ids[doc_id]

                # Update relevance score if higher
                if doc.get("relevance_score", 0) > existing.get("relevance_score", 0):
                    existing["relevance_score"] = doc["relevance_score"]

                # Update rerank score if higher
                if doc.get("rerank_score", 0) > existing.get("rerank_score", 0):
                    existing["rerank_score"] = doc["rerank_score"]

        # Convert back to list and sort by best score
        unique_docs = list(seen_ids.values())

        # Sort by rerank_score if available, else relevance_score
        def get_sort_score(doc):
            return doc.get("rerank_score") or doc.get("relevance_score", 0)

        unique_docs.sort(key=get_sort_score, reverse=True)

        # Limit to reasonable number of documents
        max_docs = settings.RAG_CANDIDATE_COUNT
        return unique_docs[:max_docs]

    def _prepare_context(self, documents: list[dict]) -> list[dict]:
        """Prepare document records for presentation as conversational context."""
        try:
            # Sort documents by relevance
            sorted_docs = sorted(documents, key=lambda x: x.get("relevance_score", 0), reverse=True)

            # Enrich each document with a human-readable source string
            for doc in sorted_docs:
                source_info = doc.get("metadata", {}).get("source", "unknown")
                doc["source_info"] = f"Source: {source_info}"

            return sorted_docs

        except Exception as e:
            logger.error(f"Error preparing context: {e!s}")
            return []

    async def update_threshold(self, new_threshold: float) -> None:
        """Update the relevance threshold used for subsequent searches."""
        if not 0 <= new_threshold <= 1:
            raise ValueError("Threshold value must be in the range [0, 1]")

        self.threshold = new_threshold
        logger.info(f"Threshold value updated: {new_threshold}")

    async def get_system_stats(self) -> dict:
        """Return aggregated statistics for the vector DB, cache, and filter state."""
        try:
            # Get statistics from vector database
            vector_db_stats = await self.vector_db.get_collection_stats()

            # Get cache statistics
            cache_stats = self.cache.get_stats()

            # Calculate cache hit rate
            hits = cache_stats.get("hits", 0)
            misses = cache_stats.get("misses", 0)
            hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0.0

            # Prepare the aggregate statistics payload
            stats = {
                "vector_db": vector_db_stats,
                "cache": {
                    "size": cache_stats.get("size", 0),
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": hit_rate,
                },
                "filter": {
                    "threshold": self.threshold,
                    "status": "active",  # Example filter status
                },
                "system_status": "active",  # Example overall system status
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e!s}")
            return {
                "error": "Failed to retrieve statistics",
                "details": str(e),
                "vector_db": {
                    "main_collection": {"total_documents": 0},
                    "filter_collection": {"total_rules": 0},
                },
                "cache": {"size": 0, "hits": 0, "misses": 0, "hit_rate": 0.0},
                "filter": {"threshold": self.threshold, "status": "unknown"},
                "system_status": "degraded",
            }

    async def check_llm_connection(self):
        """Verify connectivity to the configured conversational LLM."""
        try:
            return await self.external_llm.check_connection()
        except Exception as e:
            logger.error(f"Connection error to LLM: {e!s}")
            return False

    def clear_cache(self) -> None:
        """Remove all cached entries from the configured cache backend."""
        try:
            self.cache.clear()
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {e!s}")
            raise

    async def reindex_data(self, progress_callback: Callable | None = None) -> dict[str, Any]:
        """Kick off a full reindex of all data sources via the indexing service."""
        try:
            if progress_callback:
                await progress_callback("Starting reindexing...")

            result = await self.indexing_service.reindex_all()

            if progress_callback:
                await progress_callback("✓ Reindexing completed successfully")

            self.cache.clear()
            return result
        except Exception as e:
            logger.error(f"Error during reindexing: {e!s}")
            if progress_callback:
                await progress_callback(f"❌ Error during reindexing: {e!s}")
            raise

    def get_indexing_mode(self) -> bool:
        """Return whether dedicated indexing mode is currently enabled."""
        return self._indexing_enabled

    def set_indexing_mode(self, enabled: bool) -> None:
        """Enable or disable dedicated indexing mode."""
        self._indexing_enabled = enabled
        logger.info(f"Indexing mode set to: {'ENABLED' if enabled else 'DISABLED'}")

    # Expose service instances for tests and orchestration layers
    @property
    def services(self):
        """Return all injected services for testability and orchestration."""
        return {
            "vector_db": self.vector_db,
            "external_llm": self.external_llm,
            "content_filter": self.content_filter,
            "cache": self.cache,
            "indexing_service": self.indexing_service,
            "links_manager": self.links_manager,
            "filter_service": self.filter_service,
            "rag_service": self.rag_service,
            "llm_adapter": self.llm_adapter,
            "query_processor": self.query_processor,
        }
