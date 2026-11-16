"""
OptGraph Memory System v2.0

Phase 2 Redesign: Zero-overhead structured memory

Key differences from v1:
1. Memory stored in state, NOT passed to LLM by default
2. Structured storage (not natural language summary)
3. On-demand retrieval only when needed
4. No cumulative bloat

Design principle:
> Memory lives in state, not in messages. Only inject when explicitly needed.
"""

from typing import TypedDict, Sequence, List, Dict, Any, Optional, Tuple
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    RemoveMessage
)
from langgraph.graph import MessagesState
import json


class MemoryStateV2(MessagesState):
    """Enhanced state with structured memory

    Fields:
        messages: Conversation history (baseline)
        structured_memory: Structured storage (NOT passed to LLM by default)
        memory_index: Keyword index for retrieval
    """
    structured_memory: Dict[str, Any]
    memory_index: Optional[Dict[str, List[int]]]  # keyword -> fact_ids


class StructuredMemory:
    """
    Structured memory storage and retrieval

    Memory format:
    {
        "user_profile": {"name": "Alice", "location": "Beijing", ...},
        "key_facts": [
            {
                "id": 1,
                "fact": "User is building OptGraph project",
                "round": 5,
                "importance": 0.9,
                "keywords": ["optgraph", "project", "building"]
            }
        ],
        "topic_threads": {
            "coding": [5, 12, 23],
            "design": [8, 19]
        }
    }
    """

    @staticmethod
    def create_empty() -> Dict[str, Any]:
        """Create empty memory structure"""
        return {
            "user_profile": {},
            "key_facts": [],
            "topic_threads": {}
        }

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract keywords from text (simple version)"""
        # Remove punctuation and lowercase
        text = text.lower()
        for char in ",.!?;:()[]{}\"'":
            text = text.replace(char, " ")

        # Split and filter
        words = text.split()

        # Remove common stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at",
            "to", "for", "of", "with", "by", "from", "is", "are",
            "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "could", "should",
            "i", "you", "he", "she", "it", "we", "they", "my", "your",
            "tell", "me", "about", "something", "what", "how", "why"
        }

        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        # Return unique keywords
        return list(set(keywords))[:10]  # Limit to 10 keywords

    @staticmethod
    def build_index(structured_memory: Dict[str, Any]) -> Dict[str, List[int]]:
        """Build keyword index for retrieval

        Returns:
            Dict mapping keyword -> list of fact IDs
        """
        index = {}

        for fact in structured_memory.get("key_facts", []):
            fact_id = fact["id"]
            keywords = fact.get("keywords", [])

            for kw in keywords:
                if kw not in index:
                    index[kw] = []
                index[kw].append(fact_id)

        return index


class MemoryCompressor:
    """
    Compress old messages into structured storage

    NOT generating natural language summary!
    Extract structured data instead.
    """

    def __init__(self, llm):
        self.llm = llm

    def compress_messages(
        self,
        messages: Sequence[BaseMessage],
        existing_memory: Dict[str, Any],
        round_number: int
    ) -> Dict[str, Any]:
        """
        Compress messages into structured format

        Args:
            messages: Messages to compress
            existing_memory: Current structured memory
            round_number: Current round number (for tracking)

        Returns:
            Updated structured memory
        """
        # Format messages for LLM
        conversation = ""
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = str(msg.content)[:300]  # Truncate long messages
            conversation += f"{role}: {content}\n"

        # Build extraction prompt
        prompt = f"""Extract key information from this conversation and return as JSON.

Conversation:
{conversation}

Extract:
1. user_profile_updates: Any new info about the user (name, location, preferences, expertise, etc.)
2. key_facts: Important facts worth remembering (with importance 0.0-1.0)
3. topics: Discussion topics

Return ONLY valid JSON in this exact format:
{{
    "user_profile_updates": {{}},
    "key_facts": [
        {{"fact": "...", "importance": 0.0-1.0}}
    ],
    "topics": []
}}

Rules:
- Ignore small talk and greetings
- Only extract facts with importance > 0.5
- Keep facts concise (< 100 chars each)
- Return empty lists/dicts if nothing important

JSON:"""

        try:
            # Call LLM
            response = self.llm.invoke(prompt)

            if hasattr(response, 'content'):
                response_text = str(response.content).strip()
            else:
                response_text = str(response).strip()

            # Parse JSON
            # Extract JSON block if wrapped in markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            extracted = json.loads(response_text)

            # Merge into existing memory
            memory = existing_memory.copy()

            # Update user profile
            profile_updates = extracted.get("user_profile_updates", {})
            if profile_updates:
                memory["user_profile"].update(profile_updates)

            # Add key facts
            new_facts = extracted.get("key_facts", [])
            next_id = len(memory["key_facts"]) + 1

            for fact_data in new_facts:
                fact = {
                    "id": next_id,
                    "fact": fact_data["fact"],
                    "round": round_number,
                    "importance": fact_data.get("importance", 0.7),
                    "keywords": StructuredMemory.extract_keywords(fact_data["fact"])
                }
                memory["key_facts"].append(fact)
                next_id += 1

            # Update topic threads
            topics = extracted.get("topics", [])
            for topic in topics:
                topic_key = topic.lower().replace(" ", "_")
                if topic_key not in memory["topic_threads"]:
                    memory["topic_threads"][topic_key] = []
                memory["topic_threads"][topic_key].append(round_number)

            return memory

        except Exception as e:
            print(f"[MemoryCompressor] Failed to extract: {e}")
            # Return existing memory unchanged
            return existing_memory


class MemoryRetriever:
    """
    On-demand memory retrieval

    Only called when memory is explicitly needed!
    """

    @staticmethod
    def retrieve(
        query: str,
        structured_memory: Dict[str, Any],
        memory_index: Optional[Dict[str, List[int]]],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant facts from memory

        Args:
            query: User's query
            structured_memory: The structured memory storage
            memory_index: Keyword index
            top_k: Number of facts to retrieve

        Returns:
            List of relevant facts
        """
        query_keywords = StructuredMemory.extract_keywords(query)

        if not query_keywords:
            return []

        # Rebuild index if not provided
        if memory_index is None:
            memory_index = StructuredMemory.build_index(structured_memory)

        # Score each fact by keyword overlap
        fact_scores = {}  # fact_id -> score

        for kw in query_keywords:
            if kw in memory_index:
                for fact_id in memory_index[kw]:
                    fact_scores[fact_id] = fact_scores.get(fact_id, 0) + 1

        # Get top-k facts
        sorted_facts = sorted(
            fact_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        # Retrieve full fact objects
        facts = structured_memory.get("key_facts", [])
        fact_map = {f["id"]: f for f in facts}

        relevant_facts = [
            fact_map[fact_id]
            for fact_id, score in sorted_facts
            if fact_id in fact_map
        ]

        return relevant_facts

    @staticmethod
    def format_for_llm(
        facts: List[Dict[str, Any]],
        user_profile: Dict[str, Any]
    ) -> str:
        """
        Format retrieved memory as concise text for LLM injection

        Returns:
            Concise memory context string (or empty if no memory)
        """
        if not facts and not user_profile:
            return ""

        lines = ["Relevant context from earlier:"]

        # Add user profile if exists
        if user_profile:
            profile_parts = []
            if "name" in user_profile:
                profile_parts.append(f"Name: {user_profile['name']}")
            if "location" in user_profile:
                profile_parts.append(f"Location: {user_profile['location']}")
            if profile_parts:
                lines.append("- " + ", ".join(profile_parts))

        # Add facts
        for fact in facts:
            lines.append(f"- Round {fact['round']}: {fact['fact']}")

        return "\n".join(lines)


def should_compress_v2(
    state: MemoryStateV2,
    max_messages: int = 20,
    min_total_messages: int = 25
) -> bool:
    """
    Check if compression is needed

    Args:
        state: Current state
        max_messages: Trigger compression when messages exceed this
        min_total_messages: Minimum total messages before allowing compression
                           (avoid compression overhead in short conversations)

    Returns:
        True if should compress
    """
    messages = state.get("messages", [])
    current_count = len(messages)

    # Don't compress if conversation is too short
    # (compression overhead > savings in short conversations)
    if current_count < min_total_messages:
        return False

    # Compress if exceeds max_messages
    return current_count >= max_messages


def compress_memory_v2(
    state: MemoryStateV2,
    compressor: MemoryCompressor,
    keep_recent: int = 10
) -> Dict[str, Any]:
    """
    Compress old messages into structured storage

    Args:
        state: Current state
        compressor: MemoryCompressor instance (has LLM)
        keep_recent: Number of recent messages to keep

    Returns:
        State updates
    """
    messages = state.get("messages", [])

    if len(messages) <= keep_recent:
        return {}

    # Get existing memory or create empty
    structured_memory = state.get("structured_memory")
    if not structured_memory:
        structured_memory = StructuredMemory.create_empty()

    # Identify old messages to compress
    old_messages = messages[:-keep_recent]

    # Calculate round number (approximate)
    round_number = len(messages) // 2  # Rough estimate

    print(f"[Memory v2] Compressing {len(old_messages)} messages...")

    # Extract structured data from old messages
    updated_memory = compressor.compress_messages(
        old_messages,
        structured_memory,
        round_number
    )

    # Build keyword index
    memory_index = StructuredMemory.build_index(updated_memory)

    print(f"[Memory v2] Extracted {len(updated_memory['key_facts']) - len(structured_memory['key_facts'])} new facts")
    print(f"[Memory v2] User profile: {updated_memory['user_profile']}")

    # Delete old messages
    delete_messages = [RemoveMessage(id=m.id) for m in old_messages]

    return {
        "structured_memory": updated_memory,
        "memory_index": memory_index,
        "messages": delete_messages
    }


def get_context_baseline(state: MemoryStateV2) -> List[BaseMessage]:
    """
    Get context WITHOUT memory (baseline)

    This is the default path - zero overhead!
    """
    return list(state.get("messages", []))


def get_context_with_recall(
    state: MemoryStateV2,
    query: str,
    top_k: int = 3
) -> List[BaseMessage]:
    """
    Get context WITH memory retrieval

    Only called when explicitly needed!
    """
    messages = list(state.get("messages", []))

    structured_memory = state.get("structured_memory")
    if not structured_memory:
        # No memory yet, return baseline
        return messages

    memory_index = state.get("memory_index")

    # Retrieve relevant facts
    relevant_facts = MemoryRetriever.retrieve(
        query,
        structured_memory,
        memory_index,
        top_k
    )

    # Format as text
    memory_context = MemoryRetriever.format_for_llm(
        relevant_facts,
        structured_memory.get("user_profile", {})
    )

    if not memory_context:
        return messages

    # Inject as SystemMessage at the start
    # (Only for this specific request, not permanently added)
    context_message = SystemMessage(content=memory_context)

    print(f"[Memory v2] Injecting {len(relevant_facts)} facts into context")
    print(f"[Memory v2] Memory context ({len(memory_context)} chars):")
    print(f"  {memory_context[:200]}...")

    return [context_message] + messages


def needs_recall(user_message: str) -> bool:
    """
    Detect if user is asking for recall

    Phase 1: Simple keyword detection
    Phase 3: Can use small classifier for better detection
    """
    message_lower = user_message.lower()

    # Recall keywords (English + Chinese)
    recall_keywords = [
        # Explicit recall - asking about PAST
        "remember", "recall", "earlier", "before", "previous",
        "remind me", "what did i", "what was",
        # Chinese
        "记得", "之前", "刚才", "上次", "提醒我",
    ]

    # Check for recall keywords
    has_recall_keyword = any(kw in message_lower for kw in recall_keywords)

    # Exclude self-introduction (contains "my name" but is NOT recall)
    # Self-intro patterns: "my name is", "i'm", "i am", "i live"
    is_self_intro = any(pattern in message_lower for pattern in [
        "my name is", "i'm", "i am", "i live in", "i love"
    ])

    # Only trigger recall if has keyword AND not self-introduction
    return has_recall_keyword and not is_self_intro
