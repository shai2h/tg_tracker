class RetryableLLMError(Exception):
    """Transient LLM failure that ClassificationQueue may retry."""
