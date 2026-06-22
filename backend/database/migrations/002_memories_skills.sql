-- JARVIS Backend - Memories & Skills Schema
-- Extends the database with memory and skill management tables.

-- ── Memories (Semantic Memory Store) ──
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) CHECK (type IN ('fact', 'preference', 'context', 'history')),
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- For semantic search (OpenAI embeddings)
    importance FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_type ON memories(type);
CREATE INDEX idx_memories_importance ON memories(importance DESC);

-- ── Skills Registry ──
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50),  -- android|browser|file|media|messaging
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed default skills
INSERT INTO skills (name, category, description) VALUES
    ('android_intent', 'android', 'Execute Android intents for app launching and system actions'),
    ('chrome_control', 'browser', 'Control Chrome browser: navigate, search, extract content'),
    ('file_manager', 'file', 'File system operations: read, write, list, delete'),
    ('youtube_play', 'media', 'YouTube playback control: search, play, pause, queue'),
    ('whatsapp_send', 'messaging', 'Send WhatsApp messages and media')
ON CONFLICT (name) DO NOTHING;

-- ── Analytics Events ──
CREATE TABLE analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(100),  -- chat|command|task|error
    event_name VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analytics_user_id ON analytics(user_id);
CREATE INDEX idx_analytics_event_type ON analytics(event_type);
CREATE INDEX idx_analytics_created_at ON analytics(created_at);
