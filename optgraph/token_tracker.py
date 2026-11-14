"""
Token usage tracking from real API responses

Extracts token usage from OpenAI-compatible API response metadata
instead of estimating from character counts.
"""

from typing import Dict, Any, Optional
from threading import Lock


class TokenTracker:
    """Track real token usage from API responses

    Thread-safe token usage accumulator that extracts usage
    from API response metadata (usage.prompt_tokens, usage.completion_tokens).
    """

    def __init__(self):
        """Initialize the token tracker"""
        self._lock = Lock()
        self.stats = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "api_calls": 0,
        }

    def record_usage(self, response: Any) -> None:
        """Record token usage from an API response

        Extracts usage information from response.usage_metadata or response.usage,
        depending on the LangChain version and model provider.

        Args:
            response: API response object (AIMessage or ChatCompletion)
        """
        with self._lock:
            usage = self._extract_usage(response)
            if usage:
                self.stats["total_prompt_tokens"] += usage.get("prompt_tokens", 0)
                self.stats["total_completion_tokens"] += usage.get("completion_tokens", 0)
                self.stats["total_tokens"] += usage.get("total_tokens", 0)
                self.stats["api_calls"] += 1

    def record_request(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage from manual counts (for estimation)

        Args:
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
        """
        with self._lock:
            self.stats["total_prompt_tokens"] += input_tokens
            self.stats["total_completion_tokens"] += output_tokens
            self.stats["total_tokens"] += input_tokens + output_tokens
            self.stats["api_calls"] += 1

    def _extract_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """Extract usage dict from various response formats

        Supports:
        - LangChain AIMessage with usage_metadata
        - OpenAI ChatCompletion with usage
        - Dict with usage key

        Args:
            response: API response in various formats

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens or None
        """
        # LangChain AIMessage format
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            metadata = response.usage_metadata
            return {
                "prompt_tokens": metadata.get("input_tokens", 0),
                "completion_tokens": metadata.get("output_tokens", 0),
                "total_tokens": metadata.get("total_tokens", 0),
            }

        # OpenAI ChatCompletion format
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            return {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }

        # Dict format
        if isinstance(response, dict) and "usage" in response:
            usage = response["usage"]
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get current token usage statistics

        Returns:
            Dict with total_prompt_tokens, total_completion_tokens,
            total_tokens, total_requests (alias for api_calls),
            and avg_tokens_per_request
        """
        with self._lock:
            stats = self.stats.copy()
            # Add aliases and calculated fields
            stats['total_requests'] = stats['api_calls']
            if stats['api_calls'] > 0:
                stats['avg_tokens_per_request'] = stats['total_tokens'] / stats['api_calls']
            else:
                stats['avg_tokens_per_request'] = 0.0
            return stats

    def reset(self) -> None:
        """Reset all statistics to zero"""
        with self._lock:
            self.stats = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "api_calls": 0,
            }

    def get_tokens_before_after(self, before_stats: Dict[str, int]) -> Dict[str, Any]:
        """Calculate token difference between two snapshots

        Args:
            before_stats: Previous stats snapshot from get_stats()

        Returns:
            Dict with tokens_before, tokens_after, reduction, and reduction_percent
        """
        current = self.get_stats()

        tokens_before = before_stats["total_tokens"]
        tokens_after = current["total_tokens"]
        reduction = tokens_before - tokens_after

        if tokens_before > 0:
            reduction_percent = (reduction / tokens_before) * 100
        else:
            reduction_percent = 0.0

        return {
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "reduction": reduction,
            "reduction_percent": round(reduction_percent, 2),
        }
