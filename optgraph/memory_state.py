"""
OptGraph Memory Management

Based on research from:
- LangGraph official (44.9K stars)
- Mem0 architecture (23K stars)
- AgeMem paper (arXiv:2601.01885)

Design principles:
1. Memory management at State layer (not Checkpointer)
2. Use RemoveMessage API for deletion
3. LLM-powered summarization
4. Separate short-term and long-term memory
"""

from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    RemoveMessage
)
from langgraph.graph import MessagesState, add_messages


class MemoryState(MessagesState):
    """Enhanced state with memory management

    Fields:
        messages: Conversation history (managed)
        summary: Compressed summary of old messages
        user_profile: Structured user information (never deleted)
    """
    summary: str = ""
    user_profile: dict = {}


def should_compress(state: MemoryState, max_messages: int = 20) -> bool:
    """Check if compression is needed

    Args:
        state: Current state
        max_messages: Maximum messages before compression

    Returns:
        True if should compress
    """
    messages = state.get("messages", [])
    return len(messages) > max_messages


def extract_user_profile(messages: Sequence[BaseMessage]) -> dict:
    """Extract structured user information from messages

    This provides deterministic storage of key facts that should never be lost.

    Args:
        messages: Message history

    Returns:
        Dict with user profile info
    """
    profile = {}

    # Look at first few messages for self-introduction
    for msg in messages[:3]:
        if not isinstance(msg, HumanMessage):
            continue

        content = str(msg.content).lower()

        # Extract name
        if "my name is" in content or "i'm" in content or "i am" in content:
            # Simple extraction (can be improved with NLP)
            words = content.split()
            for i, word in enumerate(words):
                if word in ["is", "am", "i'm"] and i + 1 < len(words):
                    potential_name = words[i + 1].strip(",.!?").capitalize()
                    if len(potential_name) > 1 and potential_name[0].isupper():
                        profile["name"] = potential_name
                        break

        # Extract location
        if "i live in" in content or "i'm from" in content or "i am from" in content:
            words = content.split()
            for i, word in enumerate(words):
                if word == "in" or word == "from":
                    if i + 1 < len(words):
                        location = words[i + 1].strip(",.!?").capitalize()
                        profile["location"] = location
                        break

        # Extract preferences (simple keyword matching)
        if "i love" in content or "i like" in content or "i prefer" in content:
            for keyword in ["python", "java", "javascript", "typescript", "go", "rust"]:
                if keyword in content:
                    if "preferences" not in profile:
                        profile["preferences"] = []
                    profile["preferences"].append(keyword.capitalize())

    return profile


def create_summary_with_llm(
    messages: Sequence[BaseMessage],
    existing_summary: str,
    summarizer_llm
) -> str:
    """Generate summary using LLM

    Strategy (from Mem0 architecture):
    - Extract key facts from conversation
    - Preserve user profile information
    - Keep summary concise (< 150 tokens)

    Args:
        messages: Messages to summarize
        existing_summary: Previous summary (if any)
        summarizer_llm: LLM for summarization

    Returns:
        New summary text
    """
    # Format conversation
    conversation_text = ""
    for msg in messages:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        content = str(msg.content)[:200]  # Truncate long messages
        conversation_text += f"{role}: {content}\n"

    # Build prompt
    if existing_summary:
        prompt = f"""You have a previous summary and new messages. Create ONE consolidated summary under 80 words.

CRITICAL: Always preserve user's name, location, and preferences from the previous summary.

Previous summary:
{existing_summary}

New messages:
{conversation_text}

Consolidated summary (under 80 words, always preserve name/location/preferences):"""
    else:
        prompt = f"""Summarize this conversation in under 80 words. Extract:
- User's name, location, preferences
- Key discussion topics
- Important decisions or tasks

Conversation:
{conversation_text}

Summary (under 80 words):"""

    # Call LLM with length limit
    try:
        limited_llm = summarizer_llm.bind(max_tokens=120)
        response = limited_llm.invoke(prompt)

        if hasattr(response, 'content'):
            summary = str(response.content).strip()
        else:
            summary = str(response).strip()

        # Safety: if summary is too short or empty, keep old one
        if len(summary) < 10:
            return existing_summary if existing_summary else "No summary available."

        return summary

    except Exception as e:
        print(f"[Memory] Summary generation failed: {e}")
        return existing_summary if existing_summary else "No summary available."


def estimate_tokens(messages: Sequence[BaseMessage]) -> int:
    """Estimate token count for messages

    Simple estimation: ~4 characters = 1 token

    Args:
        messages: Messages to estimate

    Returns:
        Estimated token count
    """
    total_chars = sum(len(str(m.content)) for m in messages)
    return total_chars // 4


def should_skip_compression(
    messages_to_delete: Sequence[BaseMessage],
    summary_overhead: int = 250
) -> tuple[bool, str]:
    """Determine if compression should be skipped

    Adaptive strategy: Skip compression if the cost outweighs the benefit.

    Args:
        messages_to_delete: Messages that would be deleted
        summary_overhead: Estimated token cost of generating summary

    Returns:
        (should_skip, reason)
    """
    if not messages_to_delete:
        return True, "No messages to delete"

    # Calculate average message length
    avg_tokens = estimate_tokens(messages_to_delete) / len(messages_to_delete)

    # Strategy 1: Skip if messages are too short
    if avg_tokens < 80:
        return True, f"Avg message too short ({avg_tokens:.1f} tokens < 80 threshold)"

    # Strategy 2: Skip if deletion benefit < summary cost * 1.2 (20% safety margin)
    deletion_benefit = estimate_tokens(messages_to_delete)
    if deletion_benefit < summary_overhead * 1.2:
        return True, f"Benefit ({deletion_benefit}) < Cost ({summary_overhead}*1.2)"

    return False, f"Worth compressing: {deletion_benefit} tokens saved"


def compress_memory(
    state: MemoryState,
    summarizer_llm,
    keep_recent: int = 10
) -> dict:
    """Compress conversation memory with adaptive strategy

    Based on LangGraph official pattern + adaptive optimization:
    1. Extract user profile (deterministic, never lost)
    2. Check if compression is worth it (NEW: adaptive strategy)
    3. Generate summary of old messages (LLM) or skip if not worth it
    4. Delete old messages except recent N (RemoveMessage)
    5. Keep summary + recent messages

    Args:
        state: Current state
        summarizer_llm: LLM for summarization
        keep_recent: Number of recent messages to keep

    Returns:
        State updates (summary, user_profile, messages with RemoveMessage)
    """
    messages = state.get("messages", [])
    existing_summary = state.get("summary", "")
    existing_profile = state.get("user_profile", {})

    if len(messages) <= keep_recent:
        return {}

    # 1. Extract user profile (if not already done)
    if not existing_profile:
        profile = extract_user_profile(messages)
        print(f"[Memory] Extracted profile: {profile}")
    else:
        profile = existing_profile

    # 2. Identify old vs recent messages
    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # 3. Adaptive strategy: Check if compression is worth it
    skip, reason = should_skip_compression(old_messages)

    if skip:
        print(f"[Memory] Skipping compression: {reason}")
        # Still delete old messages to save tokens, but don't generate summary
        delete_messages = [RemoveMessage(id=m.id) for m in old_messages]
        return {
            "user_profile": profile,
            "messages": delete_messages
            # Note: summary is NOT updated, preserving existing one
        }

    # 4. Generate summary of old messages (worth the cost)
    new_summary = create_summary_with_llm(
        old_messages,
        existing_summary,
        summarizer_llm
    )

    print(f"[Memory] Compression: {len(messages)} → {keep_recent} messages")
    print(f"[Memory] Reason: {reason}")
    print(f"[Memory] Summary: {new_summary[:100]}...")

    # 5. Create RemoveMessage for old messages
    delete_messages = [RemoveMessage(id=m.id) for m in old_messages]

    return {
        "summary": new_summary,
        "user_profile": profile,
        "messages": delete_messages
    }


def get_context_with_memory(state: MemoryState) -> list[BaseMessage]:
    """Get full context including memory

    Returns messages with memory context prepended.

    IMPORTANT: Some models ignore SystemMessage, so we inject memory
    as fake conversation history (HumanMessage + AIMessage pairs).

    Args:
        state: Current state

    Returns:
        Full message list for LLM
    """
    messages = []

    # Build memory context as conversation history
    profile = state.get("user_profile", {})
    summary = state.get("summary", "")

    if profile or summary:
        # Create a fake "user introduction" message
        intro_parts = []

        if profile:
            if "name" in profile:
                intro_parts.append(f"my name is {profile['name']}")
            if "location" in profile:
                intro_parts.append(f"I live in {profile['location']}")
            if "preferences" in profile and profile["preferences"]:
                prefs = ", ".join(profile["preferences"])
                intro_parts.append(f"I love {prefs}")

        if intro_parts:
            # Inject as fake conversation at the start
            fake_user_intro = "Hi! " + ", and ".join(intro_parts) + "."
            fake_assistant_ack = "Got it! I'll remember that."

            messages.append(HumanMessage(content=fake_user_intro))
            messages.append(AIMessage(content=fake_assistant_ack))

        # Add summary as context if exists
        if summary:
            # Add as a fake exchange
            messages.append(HumanMessage(content="[Earlier conversation summary]"))
            messages.append(AIMessage(content=summary))

    # Add recent messages
    messages.extend(state.get("messages", []))

    return messages
