from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ChatBridgeResult:
    kind: str
    text: str
    metadata: dict[str, Any]


def bridge_chat_memory_json(data: Any, source_name: str) -> ChatBridgeResult | None:
    chats = _extract_chats(data, source_name)
    memories = _extract_memories(data)

    if chats:
        return _render_chats(chats, source_name)
    if memories:
        return _render_memories(memories, source_name)
    return None


def _extract_chats(data: Any, source_name: str) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        if _is_chatgpt_conversation(data):
            return [_chat_from_chatgpt_conversation(data, source_name)]

        for key in ["conversations", "chats", "threads"]:
            value = data.get(key)
            if isinstance(value, list):
                chats = _extract_chats(value, source_name)
                if chats:
                    return chats

        messages = _messages_from_container(data)
        if messages:
            return [{
                "title": str(data.get("title") or data.get("name") or Path(source_name).stem),
                "thread_id": str(data.get("id") or data.get("thread_id") or data.get("conversation_id") or ""),
                "messages": messages,
            }]

    if isinstance(data, list):
        if data and all(isinstance(item, dict) and _is_message_like(item) for item in data):
            return [{
                "title": Path(source_name).stem,
                "thread_id": "",
                "messages": [_message_from_dict(item, index + 1) for index, item in enumerate(data)],
            }]

        chats: list[dict[str, Any]] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            if _is_chatgpt_conversation(item):
                chats.append(_chat_from_chatgpt_conversation(item, source_name, fallback_index=index))
                continue
            messages = _messages_from_container(item)
            if messages:
                chats.append({
                    "title": str(item.get("title") or item.get("name") or f"{Path(source_name).stem}_{index}"),
                    "thread_id": str(item.get("id") or item.get("thread_id") or item.get("conversation_id") or ""),
                    "messages": messages,
                })
        return chats

    return []


def _is_chatgpt_conversation(item: dict[str, Any]) -> bool:
    return isinstance(item.get("mapping"), dict)


def _chat_from_chatgpt_conversation(
    conversation: dict[str, Any],
    source_name: str,
    fallback_index: int = 1,
) -> dict[str, Any]:
    mapping = conversation.get("mapping") or {}
    messages: list[dict[str, Any]] = []
    order = 0

    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        extracted = _message_from_chatgpt_message(message, order + 1)
        if extracted["content"]:
            order += 1
            messages.append(extracted)

    messages.sort(key=lambda item: (item.get("sort_time") is None, item.get("sort_time") or 0, item.get("order") or 0))
    for index, message in enumerate(messages, start=1):
        message["turn"] = index

    return {
        "title": str(conversation.get("title") or f"{Path(source_name).stem}_{fallback_index}"),
        "thread_id": str(conversation.get("id") or conversation.get("conversation_id") or ""),
        "created_at": _time_value(conversation.get("create_time")),
        "updated_at": _time_value(conversation.get("update_time")),
        "messages": messages,
    }


def _message_from_chatgpt_message(message: dict[str, Any], order: int) -> dict[str, Any]:
    author = message.get("author") if isinstance(message.get("author"), dict) else {}
    role = str(author.get("role") or message.get("role") or "unknown")
    content = message.get("content") if isinstance(message.get("content"), dict) else {}
    text = _content_to_text(content.get("parts") if "parts" in content else content.get("text"))
    return {
        "turn": order,
        "order": order,
        "role": role,
        "time": _time_value(message.get("create_time")),
        "content": text,
        "sort_time": message.get("create_time") if isinstance(message.get("create_time"), (int, float)) else None,
    }


def _messages_from_container(container: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ["messages", "chat_messages", "turns", "items"]:
        value = container.get(key)
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            messages = [_message_from_dict(item, index + 1) for index, item in enumerate(value)]
            messages = [message for message in messages if message["content"]]
            if messages and any(message["role"] != "memory" for message in messages):
                return messages
    return []


def _is_message_like(item: dict[str, Any]) -> bool:
    return any(key in item for key in ["role", "author", "sender", "from"]) and any(
        key in item for key in ["content", "text", "message", "body"]
    )


def _message_from_dict(item: dict[str, Any], order: int) -> dict[str, Any]:
    role_value = item.get("role") or item.get("author") or item.get("sender") or item.get("from") or "unknown"
    if isinstance(role_value, dict):
        role_value = role_value.get("role") or role_value.get("name") or "unknown"
    content_value = item.get("content") if "content" in item else item.get("text", item.get("message", item.get("body", "")))
    return {
        "turn": int(item.get("turn") or item.get("index") or order),
        "order": order,
        "role": str(role_value),
        "time": _time_value(item.get("time") or item.get("timestamp") or item.get("created_at") or item.get("created")),
        "content": _content_to_text(content_value),
        "sort_time": None,
    }


def _extract_memories(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ["memories", "memory", "memory_items", "saved_memories"]:
            value = data.get(key)
            if isinstance(value, list):
                return _memory_list(value)
        if _is_memory_like(data):
            return [_memory_from_value(data, 1)]

    if isinstance(data, list) and data and all(isinstance(item, (dict, str)) for item in data):
        memories = _memory_list(data)
        if memories:
            return memories

    return []


def _memory_list(values: list[Any]) -> list[dict[str, Any]]:
    memories = [_memory_from_value(value, index + 1) for index, value in enumerate(values)]
    return [memory for memory in memories if memory["content"]]


def _is_memory_like(item: dict[str, Any]) -> bool:
    return any(key in item for key in ["memory", "memory_text", "summary", "value"]) and not _is_message_like(item)


def _memory_from_value(value: Any, order: int) -> dict[str, Any]:
    if isinstance(value, str):
        return {"index": order, "source": "", "time": "", "content": value}
    if not isinstance(value, dict):
        return {"index": order, "source": "", "time": "", "content": ""}
    content = value.get("memory") or value.get("memory_text") or value.get("summary") or value.get("value") or value.get("text") or value.get("content") or ""
    return {
        "index": int(value.get("index") or value.get("id") or order) if str(value.get("index") or value.get("id") or order).isdigit() else order,
        "source": str(value.get("source") or value.get("origin") or ""),
        "time": _time_value(value.get("time") or value.get("timestamp") or value.get("created_at") or value.get("created")),
        "content": _content_to_text(content),
    }


def _render_chats(chats: list[dict[str, Any]], source_name: str) -> ChatBridgeResult:
    lines = [f"[SOURCE: {source_name}]", "[TYPE: chat_bridge]"]
    total_messages = 0

    for chat_index, chat in enumerate(chats, start=1):
        messages = chat.get("messages") or []
        total_messages += len(messages)
        lines.extend([
            "",
            f"[CHAT: {_clean(chat.get('title') or f'chat_{chat_index}')}]",
        ])
        if chat.get("thread_id"):
            lines.append(f"[THREAD_ID: {_clean(chat['thread_id'])}]")
        if chat.get("created_at"):
            lines.append(f"[CREATED_AT: {_clean(chat['created_at'])}]")
        if chat.get("updated_at"):
            lines.append(f"[UPDATED_AT: {_clean(chat['updated_at'])}]")

        for turn_index, message in enumerate(messages, start=1):
            lines.extend([
                "",
                f"[TURN: {message.get('turn') or turn_index}]",
                f"[ROLE: {_clean(message.get('role') or 'unknown')}]",
            ])
            if message.get("time"):
                lines.append(f"[TIME: {_clean(message['time'])}]")
            lines.append(_clean_multiline(message.get("content") or ""))

        lines.extend(["", "[CHAT_END]"])

    return ChatBridgeResult(
        kind="chat",
        text="\n".join(lines),
        metadata={"bridge": "chat_memory", "kind": "chat", "chat_count": len(chats), "message_count": total_messages},
    )


def _render_memories(memories: list[dict[str, Any]], source_name: str) -> ChatBridgeResult:
    lines = [f"[SOURCE: {source_name}]", "[TYPE: memory_bridge]", "", f"[MEMORY_COLLECTION: {Path(source_name).stem}]"]
    for index, memory in enumerate(memories, start=1):
        lines.extend([
            "",
            f"[MEMORY_ITEM: {memory.get('index') or index}]",
        ])
        if memory.get("source"):
            lines.append(f"[SOURCE_REF: {_clean(memory['source'])}]")
        if memory.get("time"):
            lines.append(f"[TIME: {_clean(memory['time'])}]")
        lines.append(_clean_multiline(memory.get("content") or ""))
    lines.extend(["", "[MEMORY_COLLECTION_END]"])
    return ChatBridgeResult(
        kind="memory",
        text="\n".join(lines),
        metadata={"bridge": "chat_memory", "kind": "memory", "memory_count": len(memories)},
    )


def _content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_content_to_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        if isinstance(value.get("parts"), list):
            return _content_to_text(value["parts"])
    return str(value)


def _time_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            return str(value)
    return str(value)


def _clean(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _clean_multiline(value: str) -> str:
    return "\n".join(line.rstrip() for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()
