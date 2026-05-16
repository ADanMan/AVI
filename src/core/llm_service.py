import json
from collections.abc import AsyncGenerator
from typing import Any

from openai import OpenAI
from tenacity import AsyncRetrying, retry, stop_after_attempt, wait_exponential

from config.settings import settings
from src.models.schemas import APICredentials, LLMConfiguration, LLMConfigurationUpdate
from src.utils.logger import logger


class LLMService:
    """
    Service for working with Language Model (LLM).
    Supports working with various API endpoints, including local models.
    """

    def __init__(
        self,
        model: str = settings.MAIN_LLM_MODEL,
        temperature: float = settings.MAIN_LLM_TEMPERATURE,
        max_tokens: int = settings.MAIN_LLM_MAX_TOKENS,
    ):
        """
        Initialize LLM service.

        Args:
            model: Model name
            temperature: Generation temperature
            max_tokens: Maximum number of tokens

        Raises:
            ValueError: If required API settings are missing
            ConnectionError: On API connection error
        """
        try:
            self.model = model
            self.temperature = temperature
            self.max_tokens = max_tokens

            # Validate API key
            if not settings.MAIN_LLM_API_KEY:
                raise ValueError(
                    "API key is not set. Make sure MAIN_LLM_API_KEY "
                    "is set in environment variables or .env file"
                )

            # Build API configuration
            api_config = {
                "api_key": settings.MAIN_LLM_API_KEY,
            }

            # Add base URL if specified
            if settings.MAIN_LLM_API_BASE:
                api_config["base_url"] = settings.MAIN_LLM_API_BASE
                logger.info(f"Custom API base in use: {settings.MAIN_LLM_API_BASE}")

            # Initialize OpenAI client with settings
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(**api_config)
            logger.info(f"LLM service initialized with model {model}")

            # Test connection
            self._test_connection()

        except ValueError as ve:
            logger.error(f"Configuration error: {ve!s}")
            raise
        except Exception as e:
            logger.error(f"Error initializing LLM service: {e!s}")
            if "Bearer" in str(e):
                raise ValueError(
                    "Incorrect API key. Make sure MAIN_LLM_API_KEY "
                    "is set correctly and is not empty"
                ) from e
            raise

    def _test_connection(self):
        """
        Test API connection.
        Sends a test request to check service availability.
        """
        try:
            # Send a simple test request
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            logger.info("API connection successfully tested")

        except Exception as e:
            logger.error(f"Error testing API connection: {e!s}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(
        self,
        query: str,
        context: str | None = None,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a response using the LLM.

        Args:
            query: User query
            context: Context for generation (optional)
            system_prompt: System prompt (optional)
            **kwargs: Additional parameters for API

        Returns:
            str: Generated response
        """
        try:
            # Using AsyncRetrying instead of the regular retry decorator
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=4, max=10),
            ):
                with attempt:
                    # Prepare the system prompt
                    system_content = system_prompt or self._prepare_system_prompt(context)

                    # Formulate messages for the chat
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": query},
                    ]

                    # Merge default parameters with the ones provided
                    params = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        **kwargs,
                    }

                    # Log request parameters for debugging
                    if settings.DEBUG:
                        logger.debug(f"API request parameters: {json.dumps(params, indent=2)}")

                    # Make the API request
                    response = await self.client.chat.completions.create(**params)

                    # Extract the response text
                    answer = response.choices[0].message.content.strip()

                    # Log successful generation
                    logger.info(f"Successfully generated response of {len(answer)} characters")

                    return answer

        except Exception as e:
            logger.error(f"Error generating response: {e!s}")
            raise

    def _prepare_system_prompt(self, context: str | None = None) -> str:
        """
        Prepare the system prompt considering the context.

        Args:
            context: Context for generation (optional)

        Returns:
            str: Prepared system prompt
        """
        base_prompt = (
            "You are a helpful assistant that answers user questions. "
            "Your answers should be accurate, informative, and based on the provided context."
        )

        if context:
            return (
                f"{base_prompt}\n\n"
                f"When answering, use the following context:\n{context}\n\n"
                "If the information in the context is insufficient, indicate this. "
                "Do not invent information that is not in the context."
            )

        return base_prompt

    async def generate_streaming_response(
        self, query: str, context: str | None = None
    ) -> AsyncGenerator[str, None]:
        """
        Streaming response generation.

        Args:
            query: User query
            context: Context for generation (optional)

        Yields:
            str: Parts of the generated response
        """
        try:
            # Prepare the system prompt
            system_prompt = self._prepare_system_prompt(context)

            # Formulate messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ]

            # Make a streaming request
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

            logger.info("Streaming response generation completed")

        except Exception as e:
            logger.error(f"Error during streaming generation: {e!s}")
            raise

    def update_api_base(self, new_base_url: str | None):
        """
        Update the API base URL.

        Args:
            new_base_url: New base URL or None to use the default
        """
        try:
            # Get the current configuration
            api_config = settings.get_api_configuration()

            # Update base_url
            if new_base_url:
                api_config["base_url"] = new_base_url
            elif "base_url" in api_config:
                del api_config["base_url"]

            # Create a new client with the updated settings
            self.client = OpenAI(**api_config)

            # Check connection
            self._test_connection()

            logger.info(f"API base successfully updated: {new_base_url or 'default'}")

        except Exception as e:
            logger.error(f"Error updating API base: {e!s}")
            raise

    def get_configuration(self) -> LLMConfiguration:
        """
        Get the current LLM service configuration.

        Returns:
            LLMConfiguration: Current configuration
        """
        return LLMConfiguration(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            base_url=settings.MAIN_LLM_API_BASE,
            timeout=getattr(self.client, "timeout", 30.0),
        )

    def update_configuration(self, config: LLMConfigurationUpdate) -> LLMConfiguration:
        """
        Update the LLM service configuration.

        Args:
            config: New configuration parameters

        Returns:
            LLMConfiguration: Updated configuration
        """
        try:
            # Save the current configuration for rollback in case of error
            current_config = self.get_configuration()

            # Update only the provided parameters
            if config.model is not None:
                self.model = config.model
            if config.temperature is not None:
                self.temperature = config.temperature
            if config.max_tokens is not None:
                self.max_tokens = config.max_tokens

            # Update API settings if they have changed
            api_config = {}
            if config.base_url:
                api_config["base_url"] = str(config.base_url)
            if config.api_type:
                api_config["api_type"] = config.api_type
            if config.api_version:
                api_config["api_version"] = config.api_version
            if config.timeout:
                api_config["timeout"] = config.timeout

            if api_config:
                # Create a new client with the updated settings
                new_client = OpenAI(api_key=settings.MAIN_LLM_API_KEY, **api_config)

                # Check the functionality of the new client
                self._test_connection_with_client(new_client)

                # If the check is successful, update the client
                self.client = new_client

            # Update statistics
            self._update_stats("config_updates")

            logger.info("LLM configuration successfully updated")
            return self.get_configuration()

        except Exception as e:
            # In case of error, return the previous configuration
            logger.error(f"Error updating configuration: {e!s}")
            self._restore_configuration(current_config)
            raise

    def _test_connection_with_client(self, client: OpenAI) -> bool:
        """
        Test connection with the given client.

        Args:
            client: OpenAI client for testing

        Returns:
            bool: Test result
        """
        try:
            client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.error(f"Error testing connection: {e!s}")
            return False

    def _restore_configuration(self, config: LLMConfiguration):
        """
        Restore the previous configuration in case of error.

        Args:
            config: Configuration for restoration
        """
        try:
            self.model = config.model
            self.temperature = config.temperature
            self.max_tokens = config.max_tokens

            # Restore API settings
            api_config = {"api_key": settings.MAIN_LLM_API_KEY, "timeout": config.timeout}
            if config.base_url:
                api_config["base_url"] = str(config.base_url)
            if config.api_type:
                api_config["api_type"] = config.api_type
            if config.api_version:
                api_config["api_version"] = config.api_version

            self.client = OpenAI(**api_config)
            logger.info("Configuration successfully restored")

        except Exception as e:
            logger.error(f"Error restoring configuration: {e!s}")
            raise

    def _update_stats(self, stat_name: str):
        """
        Update usage statistics.

        Args:
            stat_name: Name of the statistic to update
        """
        if not hasattr(self, "_stats"):
            self._stats = {}

        if stat_name not in self._stats:
            self._stats[stat_name] = 0

        self._stats[stat_name] += 1

    def get_stats(self) -> dict[str, Any]:
        """
        Get the usage statistics of the LLM service.

        Returns:
            Dict[str, Any]: Usage statistics
        """
        if not hasattr(self, "_stats"):
            self._stats = {}
        return self._stats.copy()

    def update_credentials(self, credentials: APICredentials) -> bool:
        """
        Update API credentials.
        This method safely updates the API key and checks its functionality
        before applying the changes.

        Args:
            credentials: New API credentials

        Returns:
            bool: Result of the credentials update
        """
        try:
            # Save the current credentials for rollback in case of error
            current_api_key = self.client.api_key

            # Create a temporary client with the new credentials
            test_client = OpenAI(
                api_key=credentials.api_key.get_secret_value(),
                base_url=(self.client.base_url if hasattr(self.client, "base_url") else None),
                organization=credentials.organization_id,
            )

            # Check functionality
            if self._test_connection_with_client(test_client):
                # If the check is successful, update the main client
                self.client = test_client
                logger.info("API credentials successfully updated")
                return True
            else:
                logger.error("Failed to verify the functionality of the new credentials")
                return False

        except Exception as e:
            logger.error(f"Error updating credentials: {e!s}")
            # Restore the previous credentials
            self.client.api_key = current_api_key
            raise

    def update_configuration_with_credentials(
        self, config: LLMConfigurationUpdate
    ) -> LLMConfiguration:
        """
        Update the LLM service configuration along with the credentials.

        Args:
            config: New configuration parameters and credentials

        Returns:
            LLMConfiguration: Updated configuration
        """
        try:
            # First, update the main configuration parameters
            updated_config = self.update_configuration(config)

            # If new credentials are provided, update them
            if config.credentials:
                if not self.update_credentials(config.credentials):
                    raise ValueError("Failed to update API credentials")

            return updated_config

        except Exception as e:
            logger.error(f"Error updating configuration: {e!s}")
            raise

    def _mask_api_key(self, api_key: str) -> str:
        """
        Mask the API key for logs and API responses.
        Shows only the first and last 4 characters.

        Args:
            api_key: API key to mask

        Returns:
            str: Masked API key
        """
        if not api_key:
            return ""
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}...{api_key[-4:]}"
