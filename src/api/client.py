import httpx

from config.settings import settings
from src.utils.logger import logger


class APIClient:
    """
    Client for making authenticated requests to AVI API.

    Uses X-API-Key header for authentication.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """
        Initialize API client.

        Args:
            api_key: API key for authentication. If None, uses settings.AVI_API_KEY
            base_url: Base URL for API. If None, uses settings.AVI_API_BASE
        """
        self.api_key = api_key or settings.AVI_API_KEY
        self.base_url = base_url or settings.AVI_API_BASE

        # Build headers
        self.headers = {}
        if self.api_key:
            self.headers[settings.API_KEY_HEADER] = self.api_key

    async def query(self, text: str, rag_mode: bool = True, use_cache: bool = True) -> dict:
        """
        Execute a query to LLM via API.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/query",
                    json={"query": text, "use_cache": use_cache},
                    params={"rag_mode": rag_mode},
                    headers=self.headers,
                    timeout=30,
                )

                # Check HTTP errors
                if response.status_code >= 400:
                    error_info = {}
                    try:
                        error_info = response.json()
                    except (ValueError, httpx.JSONDecodeError):
                        error_info = {"detail": response.text}

                    logger.error(f"API Query Error: HTTP {response.status_code}, {error_info}")

                    return {
                        "error": error_info.get("detail", "Query processing error"),
                        "response": "Sorry, a technical error occurred while processing the query.",
                    }

                return response.json()

        except httpx.RequestError as req_error:
            logger.error(f"API Query Network Error: {req_error!s}")
            return {
                "error": f"Network error: {req_error!s}",
                "response": "Could not connect to the server.",
            }
        except httpx.TimeoutException:
            logger.error("API Query Timeout")
            return {
                "error": "Response timeout exceeded",
                "response": "The server did not respond in time. Please try again later.",
            }
        except Exception as e:
            logger.error(f"API Query Error: {e!s}")
            return {
                "error": f"Error: {e!s}",
                "response": "An error occurred while processing the query.",
            }

    async def get_stats(self) -> dict:
        """
        Get system statistics.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/stats", headers=self.headers, timeout=10
                )

                # Check HTTP errors
                if response.status_code >= 400:
                    logger.error(f"API Stats Error: HTTP {response.status_code}")
                    return {
                        "error": f"HTTP error {response.status_code}",
                        "vector_db": {"total_documents": 0, "total_rules": 0},
                        "cache": {"size": 0, "hits": 0, "misses": 0, "hit_rate": 0},
                    }

                return response.json()
        except Exception as e:
            logger.error(f"API Stats Error: {e!s}")
            return {
                "error": f"Statistics retrieval error: {e!s}",
                "vector_db": {"total_documents": 0, "total_rules": 0},
                "cache": {"size": 0, "hits": 0, "misses": 0, "hit_rate": 0},
            }

    async def clear_cache(self) -> dict:
        """
        Clear system cache.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cache/clear", headers=self.headers, timeout=10
                )

                # Check HTTP errors
                if response.status_code >= 400:
                    logger.error(f"API Clear Cache Error: HTTP {response.status_code}")
                    return {"error": f"HTTP error {response.status_code}"}

                return response.json()
        except Exception as e:
            logger.error(f"API Clear Cache Error: {e!s}")
            return {"error": f"Cache clearing error: {e!s}"}

    async def reindex_data(self) -> dict:
        """
        Start data reindexing.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/reindex",
                    headers=self.headers,
                    timeout=60,  # Increased timeout for long-running operation
                )

                # Check HTTP errors
                if response.status_code >= 400:
                    logger.error(f"API Reindex Error: HTTP {response.status_code}")
                    return {"error": f"HTTP error {response.status_code}"}

                return response.json()
        except Exception as e:
            logger.error(f"API Reindex Error: {e!s}")
            return {"error": f"Data reindexing error: {e!s}"}

    async def get_all_rules(self) -> list[dict]:
        """
        Get all filtering rules.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rules",
                    headers=self.headers,
                    timeout=15,  # Increased timeout for potentially heavy operation
                )

                # Check HTTP errors
                if response.status_code >= 400:
                    error_message = f"API Get Rules Error: HTTP {response.status_code}"
                    try:
                        # Try to get error details from JSON
                        error_info = response.json()
                        logger.error(f"{error_message}, details: {error_info}")
                    except (ValueError, httpx.JSONDecodeError) as json_err:
                        # If JSON parsing fails, use response text
                        logger.error(f"{error_message}, text: {response.text}, error: {json_err}")

                    # In any case, return an empty list
                    return []

                # Try to parse response as JSON
                try:
                    data = response.json()
                except (ValueError, httpx.JSONDecodeError) as json_err:
                    logger.error(f"API Get Rules Error: Failed to parse JSON response: {json_err}")
                    return []

                # Check that the response is a list
                if not isinstance(data, list):
                    logger.error(f"API Get Rules Error: Expected list, got {type(data)}")
                    return []

                return data
        except Exception as e:
            logger.error(f"API Get Rules Error: {e!s}")
            return []

    async def add_rule(self, rule: dict) -> dict:
        """
        Add a new filtering rule.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rules",
                    json=rule,
                    headers=self.headers,
                    timeout=10,
                )
                return response.json()
        except Exception as e:
            logger.error(f"API Add Rule Error: {e!s}")
            return {"error": "Error adding rule"}

    async def delete_rule(self, rule_id: str) -> dict:
        """
        Delete a filtering rule.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/rules/{rule_id}", headers=self.headers, timeout=10
                )
                return response.json()
        except Exception as e:
            logger.error(f"API Delete Rule Error: {e!s}")
            return {"error": "Error deleting rule"}

    async def check_health(self) -> dict:
        """
        Check system health.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health", headers=self.headers, timeout=10
                )
                return response.json()
        except Exception as e:
            logger.error(f"API Health Check Error: {e!s}")
            return {"status": "error", "error": str(e)}

    async def link_rule_to_document(
        self, rule_id: str, document_id: str, is_approved: bool = True
    ) -> dict:
        """
        Create a link between a rule and a document.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rules/{rule_id}/documents/{document_id}",
                    params={"is_approved": is_approved},
                    headers=self.headers,
                    timeout=10,
                )
                return response.json()
        except Exception as e:
            logger.error(f"API Link Rule Error: {e!s}")
            return {"error": "Error creating link"}

    async def get_logs(self, limit: int = 15) -> list[str]:
        """
        Get the latest system logs.
        """
        # Note: the endpoint for logs is missing in routes.py
        # This method will return a placeholder until the corresponding API is implemented
        return [
            "Endpoint for getting logs is not implemented in the API.",
            "It is recommended to add it in routes.py.",
        ]

    async def get_feedback_stats(self) -> dict:
        """
        Get feedback statistics.
        """
        # Note: the endpoint for feedback statistics is missing in routes.py
        # This method will return a placeholder until the corresponding API is implemented
        return {"total": 0, "good": 0, "bad": 0, "with_comments": 0}

    # Additional methods for full API compliance

    async def get_documents_for_rule(self, rule_id: str, only_approved: bool = True) -> list[dict]:
        """
        Get documents linked to a rule.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rules/{rule_id}/documents",
                    params={"only_approved": only_approved},
                    headers=self.headers,
                    timeout=10,
                )
                return response.json()
        except Exception as e:
            logger.error(f"API Get Documents Error: {e!s}")
            return []

    async def get_rules_for_document(
        self, document_id: str, only_approved: bool = True
    ) -> list[dict]:
        """
        Get rules linked to a document.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/documents/{document_id}/rules",
                    params={"only_approved": only_approved},
                    headers=self.headers,
                    timeout=10,
                )
                return response.json()
        except Exception as e:
            logger.error(f"API Get Rules Error: {e!s}")
            return []
