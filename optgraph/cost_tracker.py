# -*- coding: utf-8 -*-
"""
Cost Tracking and Budget Control

Tracks LLM API costs in real-time and enforces budget limits
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Any


# Pricing table (2024 rates, per 1K tokens)
PRICING = {
    # OpenAI
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},

    # Anthropic Claude
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},

    # Fallback for unknown models
    "default": {"input": 0.01, "output": 0.03},
}


class BudgetExceededError(Exception):
    """Raised when budget limit is exceeded"""
    pass


class CostTracker:
    """
    Track LLM API costs and enforce budget limits

    Features:
    - Real-time cost tracking for every LLM call
    - Budget enforcement (automatic stop when exceeded)
    - Statistics by thread, user, model, time period
    - Support for multiple LLM providers

    Example:
        >>> tracker = CostTracker(db_path="costs.db")
        >>> tracker.set_budget(limit=100.0, scope="global")
        >>>
        >>> tracker.log_call(
        ...     model="gpt-4",
        ...     input_tokens=1000,
        ...     output_tokens=500,
        ...     thread_id="conversation_123"
        ... )
        >>>
        >>> stats = tracker.get_stats()
        >>> print(f"Total cost: ${stats['total_cost']:.2f}")
    """

    def __init__(self, db_path: str = "costs.db", budget_limit: float = None):
        """
        Initialize cost tracker

        Args:
            db_path: Path to SQLite database file
            budget_limit: Global budget limit in USD (optional)
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self._setup_tables()

        # Set global budget if provided
        if budget_limit is not None:
            self.set_budget(limit=budget_limit, scope="global")

    def _setup_tables(self):
        """Create database schema"""

        # Table 1: LLM calls
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- Model info
                model TEXT NOT NULL,
                provider TEXT,

                -- Token usage
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,

                -- Costs
                input_cost_usd REAL NOT NULL,
                output_cost_usd REAL NOT NULL,
                total_cost_usd REAL NOT NULL,

                -- Context
                thread_id TEXT,
                user_id TEXT,
                node_name TEXT,
                purpose TEXT,

                -- Metadata
                metadata TEXT
            )
        """)

        # Indexes for fast queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON llm_calls(timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_thread_id
            ON llm_calls(thread_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id
            ON llm_calls(user_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model
            ON llm_calls(model)
        """)

        # Table 2: Budgets
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Scope
                scope TEXT NOT NULL,
                scope_id TEXT,

                -- Budget settings
                budget_usd REAL NOT NULL,
                period TEXT DEFAULT 'total',

                -- Alert
                warning_threshold REAL DEFAULT 0.8,

                -- Status
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
        """
        Calculate cost for a model and token usage

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-opus")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Dict with input_cost, output_cost, total_cost
        """
        # Get pricing (fallback to default if unknown)
        pricing = PRICING.get(model, PRICING["default"])

        # Calculate costs (pricing is per 1K tokens)
        input_cost = (input_tokens / 1000.0) * pricing["input"]
        output_cost = (output_tokens / 1000.0) * pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
        }

    def _detect_provider(self, model: str) -> str:
        """Detect provider from model name"""
        model_lower = model.lower()

        if "gpt" in model_lower or "openai" in model_lower:
            return "openai"
        elif "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        elif "gemini" in model_lower or "palm" in model_lower:
            return "google"
        else:
            return "unknown"

    def log_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        node_name: Optional[str] = None,
        purpose: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Log an LLM API call

        Args:
            model: Model name (e.g., "gpt-4")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            thread_id: Thread/conversation ID (optional)
            user_id: User ID (optional)
            node_name: LangGraph node name (optional)
            purpose: Purpose tag (optional)
            metadata: Additional metadata (optional)

        Returns:
            Dict with cost information and budget status

        Raises:
            BudgetExceededError: If budget limit is exceeded
        """

        # 1. Calculate cost
        cost = self._calculate_cost(model, input_tokens, output_tokens)

        # 2. Detect provider
        provider = self._detect_provider(model)

        # 3. Insert into database
        total_tokens = input_tokens + output_tokens
        metadata_json = json.dumps(metadata) if metadata else None

        cursor = self.conn.execute("""
            INSERT INTO llm_calls (
                model, provider,
                input_tokens, output_tokens, total_tokens,
                input_cost_usd, output_cost_usd, total_cost_usd,
                thread_id, user_id, node_name, purpose,
                metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model, provider,
            input_tokens, output_tokens, total_tokens,
            cost["input_cost"], cost["output_cost"], cost["total_cost"],
            thread_id, user_id, node_name, purpose,
            metadata_json
        ))

        self.conn.commit()
        call_id = cursor.lastrowid

        # 4. Check budget
        budget_status = self.check_budget(thread_id=thread_id, user_id=user_id)

        # 5. Raise exception if budget exceeded
        if not budget_status["within_budget"]:
            raise BudgetExceededError(
                f"Budget exceeded: ${budget_status['current_spend']:.4f} / "
                f"${budget_status['budget_limit']:.2f}"
            )

        # 6. Warn if approaching limit
        if budget_status["warning"]:
            print(f"[CostTracker] Warning: {budget_status['usage_percent']:.1f}% of budget used")

        return {
            "call_id": call_id,
            "cost": cost["total_cost"],
            "budget_status": budget_status,
        }

    def get_stats(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get cost statistics

        Args:
            thread_id: Filter by thread ID (optional)
            user_id: Filter by user ID (optional)
            start_date: Start date filter (optional)
            end_date: End date filter (optional)

        Returns:
            Dict with comprehensive statistics
        """

        # Build WHERE clause
        conditions = []
        params = []

        if thread_id:
            conditions.append("thread_id = ?")
            params.append(thread_id)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date.isoformat())

        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Overall stats
        cursor = self.conn.execute(f"""
            SELECT
                COUNT(*) as total_calls,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost_usd) as total_cost,
                AVG(total_cost_usd) as avg_cost_per_call,
                MIN(timestamp) as first_call,
                MAX(timestamp) as last_call
            FROM llm_calls
            WHERE {where_clause}
        """, params)

        overall = dict(cursor.fetchone())

        # By model
        cursor = self.conn.execute(f"""
            SELECT
                model,
                COUNT(*) as calls,
                SUM(total_tokens) as tokens,
                SUM(total_cost_usd) as cost
            FROM llm_calls
            WHERE {where_clause}
            GROUP BY model
            ORDER BY cost DESC
        """, params)

        by_model = {row["model"]: dict(row) for row in cursor.fetchall()}

        # By provider
        cursor = self.conn.execute(f"""
            SELECT
                provider,
                COUNT(*) as calls,
                SUM(total_cost_usd) as cost
            FROM llm_calls
            WHERE {where_clause}
            GROUP BY provider
            ORDER BY cost DESC
        """, params)

        by_provider = {row["provider"]: dict(row) for row in cursor.fetchall()}

        return {
            "total_calls": overall["total_calls"] or 0,
            "total_input_tokens": overall["total_input_tokens"] or 0,
            "total_output_tokens": overall["total_output_tokens"] or 0,
            "total_tokens": overall["total_tokens"] or 0,
            "total_cost": overall["total_cost"] or 0.0,
            "average_cost_per_call": overall["avg_cost_per_call"] or 0.0,
            "first_call": overall["first_call"],
            "last_call": overall["last_call"],
            "by_model": by_model,
            "by_provider": by_provider,
        }

    def set_budget(
        self,
        limit: float,
        scope: str = "global",
        scope_id: Optional[str] = None,
        warning_threshold: float = 0.8,
    ):
        """
        Set a budget limit

        Args:
            limit: Budget limit in USD
            scope: Budget scope ("global", "thread", "user")
            scope_id: ID for scoped budgets (thread_id or user_id)
            warning_threshold: Warning threshold (0.8 = 80%)
        """

        # Deactivate existing budgets for this scope
        if scope_id is None:
            self.conn.execute("""
                UPDATE budgets
                SET is_active = FALSE
                WHERE scope = ? AND scope_id IS NULL
            """, (scope,))
        else:
            self.conn.execute("""
                UPDATE budgets
                SET is_active = FALSE
                WHERE scope = ? AND scope_id = ?
            """, (scope, scope_id))

        # Insert new budget
        self.conn.execute("""
            INSERT INTO budgets (scope, scope_id, budget_usd, warning_threshold)
            VALUES (?, ?, ?, ?)
        """, (scope, scope_id, limit, warning_threshold))

        self.conn.commit()

    def check_budget(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check budget status

        Args:
            thread_id: Thread ID to check (optional)
            user_id: User ID to check (optional)

        Returns:
            Dict with budget status
        """

        # Determine which budget to check (priority: thread > user > global)
        if thread_id:
            scope, scope_id = "thread", thread_id
        elif user_id:
            scope, scope_id = "user", user_id
        else:
            scope, scope_id = "global", None

        # Get active budget
        if scope_id is None:
            cursor = self.conn.execute("""
                SELECT budget_usd, warning_threshold
                FROM budgets
                WHERE scope = ? AND scope_id IS NULL AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """, (scope,))
        else:
            cursor = self.conn.execute("""
                SELECT budget_usd, warning_threshold
                FROM budgets
                WHERE scope = ? AND scope_id = ? AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """, (scope, scope_id))

        budget_row = cursor.fetchone()

        if not budget_row:
            # No budget set, always within budget
            return {
                "within_budget": True,
                "current_spend": 0.0,
                "budget_limit": None,
                "usage_percent": 0.0,
                "warning": False,
            }

        budget_limit = budget_row["budget_usd"]
        warning_threshold = budget_row["warning_threshold"]

        # Calculate current spend
        params = []
        conditions = []

        if scope == "thread":
            conditions.append("thread_id = ?")
            params.append(scope_id)
        elif scope == "user":
            conditions.append("user_id = ?")
            params.append(scope_id)
        # global = no conditions

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor = self.conn.execute(f"""
            SELECT COALESCE(SUM(total_cost_usd), 0) as current_spend
            FROM llm_calls
            WHERE {where_clause}
        """, params)

        current_spend = cursor.fetchone()["current_spend"]

        # Calculate usage percentage
        usage_percent = (current_spend / budget_limit) * 100 if budget_limit > 0 else 0

        return {
            "within_budget": current_spend < budget_limit,
            "current_spend": current_spend,
            "budget_limit": budget_limit,
            "usage_percent": usage_percent,
            "warning": usage_percent >= (warning_threshold * 100),
        }

    def get_top_expensive(
        self,
        by: str = "thread",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get top expensive items

        Args:
            by: Group by ("thread", "user", "model", "node")
            limit: Number of results

        Returns:
            List of top expensive items
        """

        valid_by = ["thread", "user", "model", "node"]
        if by not in valid_by:
            raise ValueError(f"'by' must be one of {valid_by}")

        column_map = {
            "thread": "thread_id",
            "user": "user_id",
            "model": "model",
            "node": "node_name",
        }

        column = column_map[by]

        cursor = self.conn.execute(f"""
            SELECT
                {column} as id,
                COUNT(*) as calls,
                SUM(total_cost_usd) as cost,
                SUM(total_tokens) as tokens
            FROM llm_calls
            WHERE {column} IS NOT NULL
            GROUP BY {column}
            ORDER BY cost DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection"""
        self.conn.close()
