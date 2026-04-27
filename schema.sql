-- =============================================================
-- Pixvault — Supabase / PostgreSQL Schema
-- Run this in your Supabase SQL editor (Database > SQL Editor)
-- =============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── Users ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_admin      BOOLEAN     DEFAULT FALSE,
    storage_used  BIGINT      DEFAULT 0,   -- bytes
    bio           TEXT,
    avatar_url    TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Albums ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS albums (
    id          UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id     UUID        REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    cover_url   TEXT,
    is_public   BOOLEAN     DEFAULT FALSE,
    share_token VARCHAR(64) UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Media ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS media (
    id                   UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id              UUID        REFERENCES users(id) ON DELETE CASCADE,
    album_id             UUID        REFERENCES albums(id) ON DELETE SET NULL,
    filename             VARCHAR(255) NOT NULL,
    original_filename    VARCHAR(255),
    cloudinary_public_id VARCHAR(255) NOT NULL UNIQUE,
    cloudinary_url       TEXT        NOT NULL,
    media_type           VARCHAR(10) NOT NULL CHECK (media_type IN ('image', 'video')),
    file_size            BIGINT      DEFAULT 0,
    width                INTEGER,
    height               INTEGER,
    duration             FLOAT,
    tags                 TEXT[]      DEFAULT '{}',
    share_token          VARCHAR(64) UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_albums_user_id        ON albums(user_id);
CREATE INDEX IF NOT EXISTS idx_albums_share_token    ON albums(share_token);
CREATE INDEX IF NOT EXISTS idx_media_user_id         ON media(user_id);
CREATE INDEX IF NOT EXISTS idx_media_album_id        ON media(album_id);
CREATE INDEX IF NOT EXISTS idx_media_created_at      ON media(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_tags            ON media USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_media_share_token     ON media(share_token);
CREATE INDEX IF NOT EXISTS idx_users_username        ON users(username);
