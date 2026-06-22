"""
Prepared Database Queries

Commonly-used parameterized queries for database operations.
Keeps inline SQL out of service/API layers.
"""



# ── User Queries ──

UPSERT_USER = """
INSERT INTO users (device_id, phone_number, metadata)
VALUES ($1, $2, $3)
ON CONFLICT (device_id)
DO UPDATE SET
    updated_at = NOW(),
    phone_number = COALESCE($2, users.phone_number),
    metadata = users.metadata || $3
RETURNING id, device_id, created_at;
"""

GET_USER_BY_DEVICE_ID = """
SELECT id, device_id, phone_number, created_at, metadata
FROM users
WHERE device_id = $1;
"""

GET_USER_BY_ID = """
SELECT id, device_id, phone_number, created_at, metadata
FROM users
WHERE id = $1;
"""


# ── Session Queries ──

CREATE_SESSION = """
INSERT INTO sessions (user_id, access_token, refresh_token, expires_at, ip_address, user_agent)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id, created_at;
"""

GET_VALID_SESSION = """
SELECT id, user_id, access_token, expires_at
FROM sessions
WHERE access_token = $1 AND expires_at > NOW();
"""

INVALIDATE_SESSION = """
UPDATE sessions
SET expires_at = NOW()
WHERE access_token = $1;
"""

INVALIDATE_ALL_USER_SESSIONS = """
UPDATE sessions
SET expires_at = NOW()
WHERE user_id = $1 AND expires_at > NOW();
"""


# ── Conversation Queries ──

GET_CONVERSATIONS_WITH_MESSAGE_COUNT = """
SELECT
    c.id,
    c.title,
    c.created_at,
    COUNT(m.id) AS message_count,
    MAX(m.created_at) AS last_message_at
FROM conversations c
LEFT JOIN messages m ON m.conversation_id = c.id
WHERE c.user_id = $1
GROUP BY c.id
ORDER BY last_message_at DESC NULLS LAST
LIMIT $2 OFFSET $3;
"""

GET_RECENT_MESSAGES = """
SELECT id, role, content, tokens_used, created_at, metadata
FROM messages
WHERE conversation_id = $1
ORDER BY created_at ASC
LIMIT $2;
"""


# ── Task Queries ──

UPDATE_TASK_STATUS = """
UPDATE tasks
SET
    status = $2,
    started_at = CASE WHEN $2 = 'RUNNING' THEN NOW() ELSE started_at END,
    completed_at = CASE WHEN $2 IN ('COMPLETED', 'FAILED', 'CANCELLED') THEN NOW() ELSE completed_at END,
    error_message = $3,
    progress_percent = $4
WHERE id = $1
RETURNING *;
"""

GET_PENDING_TASKS = """
SELECT id, user_id, skill_name, input, timeout_seconds, created_at
FROM tasks
WHERE status = 'PENDING'
ORDER BY created_at ASC
LIMIT $1;
"""


# ── Memory Queries ──

FULL_TEXT_SEARCH_MEMORIES = """
SELECT id, type, content, importance, created_at, expires_at, metadata,
       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $2)) AS rank
FROM memories
WHERE user_id = $1
  AND to_tsvector('english', content) @@ plainto_tsquery('english', $2)
  AND importance >= $3
ORDER BY rank DESC, importance DESC
LIMIT $4;
"""
