#!/usr/bin/env python3
"""
RAG Context Store — SSD-based context extension for local LLMs.

Uses SQLite FTS5 with BM25 ranking. Zero external dependencies.
Stores two types of context:
  1. Conversation history (user/assistant message pairs)
  2. Codebase file chunks (512-char segments with overlap)

All data lives on SSD in ~/.agents/rag_context.db
"""
import sqlite3
import os
import re
import time

DB_PATH = os.path.expanduser("~/.agents/rag_context.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conv_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS conv_fts USING fts5(
    content,
    content=conv_chunks,
    content_rowid=id,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS conv_ai AFTER INSERT ON conv_chunks BEGIN
    INSERT INTO conv_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS conv_ad AFTER DELETE ON conv_chunks BEGIN
    INSERT INTO conv_fts(conv_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TABLE IF NOT EXISTS code_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    mtime REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5(
    file_path,
    content,
    content=code_chunks,
    content_rowid=id,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS code_ai AFTER INSERT ON code_chunks BEGIN
    INSERT INTO code_fts(rowid, file_path, content) VALUES (new.id, new.file_path, new.content);
END;
CREATE TRIGGER IF NOT EXISTS code_ad AFTER DELETE ON code_chunks BEGIN
    INSERT INTO code_fts(code_fts, rowid, file_path, content) VALUES('delete', old.id, old.file_path, old.content);
END;

CREATE TABLE IF NOT EXISTS indexed_files (
    file_path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    chunk_count INTEGER NOT NULL
);
"""


def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.executescript(_SCHEMA)
    return conn


# ── Conversation History ─────────────────────────────────────────────

def store_conversation(session_id, role, content):
    if not content or not content.strip():
        return
    content = content[:4000]
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO conv_chunks (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time())
        )
        conn.commit()
    finally:
        conn.close()


def search_conversations(query, limit=5, exclude_session=None):
    if not query or not query.strip():
        return []
    conn = _get_conn()
    try:
        tokens = re.findall(r'\w{2,}', query.lower())
        if not tokens:
            return []
        fts_query = " OR ".join(tokens[:15])
        if exclude_session:
            rows = conn.execute("""
                SELECT c.role, c.content, c.session_id, rank
                FROM conv_fts f
                JOIN conv_chunks c ON c.id = f.rowid
                WHERE conv_fts MATCH ?
                  AND c.session_id != ?
                ORDER BY rank LIMIT ?
            """, (fts_query, exclude_session, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.role, c.content, c.session_id, rank
                FROM conv_fts f
                JOIN conv_chunks c ON c.id = f.rowid
                WHERE conv_fts MATCH ? ORDER BY rank LIMIT ?
            """, (fts_query, limit)).fetchall()
        return [{"role": r[0], "content": r[1][:1500], "session": r[2]} for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ── Codebase Indexing ────────────────────────────────────────────────

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.swift', '.rs', '.go',
    '.c', '.h', '.cpp', '.hpp', '.java', '.kt', '.rb',
    '.md', '.txt', '.toml', '.yaml', '.yml', '.json', '.jsonc',
    '.sh', '.zsh', '.bash', '.fish',
    '.css', '.scss', '.html', '.xml', '.plist',
    '.sql', '.graphql', '.proto',
    '.env', '.ini', '.cfg', '.conf',
}

SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    '.tox', '.mypy_cache', '.pytest_cache', 'dist', 'build',
    '.next', '.nuxt', '.svelte-kit', 'target', '.gradle',
    '.idea', '.vscode', '.DS_Store', 'Pods', '.build',
    'DerivedData', '.swiftpm', 'vendor',
}

MAX_FILE_SIZE = 100_000


def _chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


def index_file(file_path):
    try:
        stat = os.stat(file_path)
        if stat.st_size > MAX_FILE_SIZE or stat.st_size == 0:
            return 0
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT mtime FROM indexed_files WHERE file_path = ?",
                (file_path,)
            ).fetchone()
            if row and abs(row[0] - stat.st_mtime) < 0.01:
                return 0
            with open(file_path, 'r', errors='replace') as f:
                text = f.read()
            conn.execute("DELETE FROM code_chunks WHERE file_path = ?", (file_path,))
            chunks = _chunk_text(text)
            for i, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT INTO code_chunks (file_path, chunk_index, content, mtime) VALUES (?, ?, ?, ?)",
                    (file_path, i, chunk, stat.st_mtime)
                )
            conn.execute(
                "INSERT OR REPLACE INTO indexed_files (file_path, mtime, chunk_count) VALUES (?, ?, ?)",
                (file_path, stat.st_mtime, len(chunks))
            )
            conn.commit()
            return len(chunks)
        finally:
            conn.close()
    except (OSError, UnicodeDecodeError, sqlite3.Error):
        return 0


def index_directory(directory, max_files=2000):
    indexed = 0
    file_count = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for fname in files:
            if file_count >= max_files:
                return indexed
            ext = os.path.splitext(fname)[1].lower()
            if ext not in CODE_EXTENSIONS and fname.lower() not in ('makefile', 'dockerfile', 'gemfile', 'rakefile'):
                continue
            fpath = os.path.join(root, fname)
            n = index_file(fpath)
            if n > 0:
                indexed += n
                file_count += 1
    return indexed


def search_code(query, limit=5):
    if not query or not query.strip():
        return []
    conn = _get_conn()
    try:
        tokens = re.findall(r'\w{2,}', query.lower())
        if not tokens:
            return []
        fts_query = " OR ".join(tokens[:15])
        rows = conn.execute("""
            SELECT c.file_path, c.content, c.chunk_index, rank
            FROM code_fts f
            JOIN code_chunks c ON c.id = f.rowid
            WHERE code_fts MATCH ? ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
        return [{"file": r[0], "content": r[1][:1500], "chunk": r[2]} for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


# ── Unified RAG Retrieval ────────────────────────────────────────────

def retrieve_context(query: str, session_id=None, max_tokens: int = 500) -> str:
    if not query or not query.strip():
        return ""
    parts = []
    char_budget = max_tokens * 3

    code_results = search_code(query, limit=4)
    if code_results:
        parts.append("### Relevant Code (from your codebase):")
        for r in code_results:
            snippet = f"**{r['file']}** (chunk {r['chunk']}):\n```\n{r['content'][:800]}\n```"
            parts.append(snippet)

    conv_results = search_conversations(query, limit=3, exclude_session=session_id)
    if conv_results:
        parts.append("\n### Relevant Past Conversations:")
        for r in conv_results:
            parts.append(f"[{r['role']}]: {r['content'][:600]}")

    skills_snippet = _search_skills_index(query, limit=2)
    if skills_snippet:
        parts.append(f"\n{skills_snippet}")

    if not parts:
        return ""

    result = "\n\n".join(parts)
    if len(result) > char_budget:
        result = result[:char_budget] + "\n\n... [RAG context truncated to fit token budget]"
    return result


def _search_skills_index(query, limit=2):
    skills_db = os.path.expanduser("~/.agents/skills_index.db")
    if not os.path.exists(skills_db):
        return ""
    try:
        conn = sqlite3.connect(skills_db)
        tokens = re.findall(r'\w+', query)
        fts_query = " OR ".join(tokens) if tokens else query
        rows = conn.execute("""
            SELECT name, description, content
            FROM skills_fts WHERE skills_fts MATCH ? ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
        conn.close()
        if not rows:
            return ""
        res = ["### On-Demand Skills (SSD RAG):"]
        for r in rows:
            res.append(f"Skill: {r[0]} ({r[1]})\n{r[2][:1000]}")
        return "\n".join(res)
    except Exception:
        return ""


def get_stats():
    conn = _get_conn()
    try:
        conv_count = conn.execute("SELECT COUNT(*) FROM conv_chunks").fetchone()[0]
        code_count = conn.execute("SELECT COUNT(*) FROM code_chunks").fetchone()[0]
        file_count = conn.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0]
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        return {
            "conversation_chunks": conv_count,
            "code_chunks": code_count,
            "indexed_files": file_count,
            "db_size_mb": round(db_size / 1_048_576, 2),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  rag-context-store.py index <directory>")
        print("  rag-context-store.py search <query>")
        print("  rag-context-store.py stats")
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "index" and len(sys.argv) >= 3:
        directory = sys.argv[2]
        print(f"Indexing {directory}...")
        n = index_directory(directory)
        print(f"Indexed {n} chunks")
        stats = get_stats()
        print(f"DB: {stats['indexed_files']} files, {stats['code_chunks']} code chunks, {stats['db_size_mb']} MB")
    elif cmd == "search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        print(f"Searching: {query}\n")
        ctx = retrieve_context(query)
        print(ctx if ctx else "(no results)")
    elif cmd == "stats":
        stats = get_stats()
        print(f"Conversation chunks: {stats['conversation_chunks']}")
        print(f"Code chunks:         {stats['code_chunks']}")
        print(f"Indexed files:       {stats['indexed_files']}")
        print(f"Database size:       {stats['db_size_mb']} MB")
    else:
        print(f"Unknown command: {cmd}")
