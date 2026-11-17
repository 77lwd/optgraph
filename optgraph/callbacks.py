# -*- coding: utf-8 -*-
"""
Cost Tracking Callback for LangChain/LangGraph

Automatically tracks LLM API costs via callbacks
"""

from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from optgraph.cost_tracker import CostTracker, BudgetExceededError


class CostTrackingCallback(BaseCallbackHandler):
    """
    Callback handler that tracks LLM costs automatically

    Usage:
        >>> from optgraph.callbacks import CostTrackingCallback
        >>> from optgraph.cost_tracker import CostTracker
        >>>
        >>> tracker = CostTracker(db_path="costs.db")
        >>> tracker.set_budget(limit=100.0)
        >>>
        >>> callback = CostTrackingCallback(tracker)
        >>>
        >>> # Use with LLM
        >>> from langchain_openai import ChatOpenAI
        >>> llm = ChatOpenAI(model="gpt-4", callbacks=[callback])
        >>> result = llm.invoke("Hello")  # Cost automatically tracked!
        >>>
        >>> # Check stats
        >>> stats = tracker.get_stats()
        >>> print(f"Total cost: ${stats['total_cost']:.2f}")
    """

    def __init__(
        self,
        cost_tracker: CostTracker,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize callback

        Args:
            cost_tracker: CostTracker instance
            thread_id: Thread/conversation ID (optional)
            user_id: User ID (optional)
            verbose: Print cost info after each call
        """
        super().__init__()
        self.cost_tracker = cost_tracker
        self.thread_id = thread_id
        self.user_id = user_id
        self.verbose = verbose

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts"""
        pass

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """
        Called when LLM ends - record the cost

        Extracts token usage and model info from the response
        """

        # Extract token usage
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            model_name = response.llm_output.get("model_name", "unknown")

            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Handle different token naming conventions
            if input_tokens == 0:
                input_tokens = usage.get("input_tokens", 0)
            if output_tokens == 0:
                output_tokens = usage.get("output_tokens", 0)

            # Only log if we have token info
            if input_tokens > 0 or output_tokens > 0:
                try:
                    result = self.cost_tracker.log_call(
                        model=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        thread_id=self.thread_id or kwargs.get("thread_id"),
                        user_id=self.user_id or kwargs.get("user_id"),
                        metadata={
                            "run_id": str(kwargs.get("run_id", "")),
                            "tags": kwargs.get("tags", []),
                        },
                    )

                    if self.verbose:
                        print(f"[CostTracker] {model_name}: "
                              f"{input_tokens} in + {output_tokens} out = "
                              f"${result['cost']:.4f}")

                except BudgetExceededError:
                    # Re-raise budget errors - these should stop execution
                    raise
                except Exception as e:
                    # Don't fail the LLM call for other tracking errors
                    print(f"[CostTracker] Warning: Failed to log cost: {e}")

    def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors"""
        pass


class CostTrackedLLM:
    """
    Wrapper that adds cost tracking to any LLM

    Usage:
        >>> from optgraph.callbacks import CostTrackedLLM
        >>> from optgraph.cost_tracker import CostTracker
        >>> from langchain_openai import ChatOpenAI
        >>>
        >>> tracker = CostTracker()
        >>> base_llm = ChatOpenAI(model="gpt-4")
        >>> llm = CostTrackedLLM(base_llm, tracker)
        >>>
        >>> result = llm.invoke("Hello")  # Cost tracked!
    """

    def __init__(
        self,
        llm,
        cost_tracker: CostTracker,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """
        Wrap an LLM with cost tracking

        Args:
            llm: Base LLM instance
            cost_tracker: CostTracker instance
            thread_id: Thread/conversation ID (optional)
            user_id: User ID (optional)
        """
        self.llm = llm
        self.cost_tracker = cost_tracker
        self.thread_id = thread_id
        self.user_id = user_id

        # Add callback to the LLM
        callback = CostTrackingCallback(
            cost_tracker=cost_tracker,
            thread_id=thread_id,
            user_id=user_id,
        )

        if hasattr(llm, "callbacks"):
            if llm.callbacks is None:
                llm.callbacks = [callback]
            else:
                llm.callbacks.append(callback)
        else:
            # Fallback: set callbacks attribute
            llm.callbacks = [callback]

    def invoke(self, *args, **kwargs):
        """Pass through to underlying LLM"""
        return self.llm.invoke(*args, **kwargs)

    async def ainvoke(self, *args, **kwargs):
        """Pass through to underlying LLM (async)"""
        return await self.llm.ainvoke(*args, **kwargs)

    def __getattr__(self, name):
        """Proxy all other attributes to underlying LLM"""
        return getattr(self.llm, name)


# Convenience functions for quick setup

def enable_cost_tracking(
    llm,
    cost_tracker: Optional[CostTracker] = None,
    db_path: str = "costs.db",
    budget_limit: Optional[float] = None,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Quick setup: Enable cost tracking for an LLM

    This is the recommended way to add cost tracking to your LLMs when using
    OptGraph.compile() with enable_cost_tracking=True.

    Args:
        llm: LLM instance to wrap
        cost_tracker: Existing CostTracker instance (use app.cost_tracker from OptGraph.compile)
                     If None, creates a new tracker
        db_path: Database path (only used if cost_tracker=None)
        budget_limit: Budget limit in USD (only used if cost_tracker=None)
        thread_id: Thread/conversation ID (optional)
        user_id: User ID (optional)

    Returns:
        CostTrackedLLM instance with tracker attached

    Examples:
        >>> # Example 1: Standalone usage (creates new tracker)
        >>> from langchain_openai import ChatOpenAI
        >>> from optgraph.callbacks import enable_cost_tracking
        >>>
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> tracked_llm = enable_cost_tracking(llm, budget_limit=100.0)
        >>> result = tracked_llm.invoke("Hello")
        >>> print(f"Cost: ${tracked_llm.cost_tracker.get_stats()['total_cost']:.2f}")
        >>>
        >>> # Example 2: With OptGraph.compile() (use existing tracker)
        >>> from optgraph import OptGraph
        >>> app = OptGraph.compile(graph, enable_cost_tracking=True)
        >>>
        >>> def agent_node(state):
        >>>     llm = ChatOpenAI(model="gpt-4")
        >>>     # Use the tracker from app
        >>>     llm = enable_cost_tracking(llm, cost_tracker=app.cost_tracker)
        >>>     response = llm.invoke(state["messages"])
        >>>     return {"messages": [response]}
    """

    # Use existing tracker or create new one
    if cost_tracker is None:
        tracker = CostTracker(db_path=db_path, budget_limit=budget_limit)
    else:
        tracker = cost_tracker

    return CostTrackedLLM(llm, tracker, thread_id=thread_id, user_id=user_id)


def add_cost_tracking_callback(
    llm,
    cost_tracker: CostTracker,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Add cost tracking callback to an existing LLM (in-place modification)

    This is a lightweight alternative to enable_cost_tracking() that modifies
    the LLM's callbacks list directly without wrapping.

    Args:
        llm: LLM instance to modify
        cost_tracker: CostTracker instance
        thread_id: Thread/conversation ID (optional)
        user_id: User ID (optional)

    Returns:
        The same LLM instance (modified in-place)

    Example:
        >>> from optgraph import OptGraph
        >>> app = OptGraph.compile(graph, enable_cost_tracking=True)
        >>>
        >>> def agent_node(state):
        >>>     llm = ChatOpenAI(model="gpt-4")
        >>>     # Add callback directly
        >>>     add_cost_tracking_callback(llm, app.cost_tracker)
        >>>     response = llm.invoke(state["messages"])
        >>>     return {"messages": [response]}
    """

    callback = CostTrackingCallback(
        cost_tracker=cost_tracker,
        thread_id=thread_id,
        user_id=user_id,
    )

    if hasattr(llm, "callbacks"):
        if llm.callbacks is None:
            llm.callbacks = [callback]
        else:
            llm.callbacks.append(callback)
    else:
        llm.callbacks = [callback]

    return llm
