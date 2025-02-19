import sqlite3
import json
import asyncio
from functools import partial
import threading

class ConversationDB:
    def __init__(self):
        self._local = threading.local()
        self.db_path = 'conversations.db'
        # Create tables on init
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def _get_conn(self):
        """Get a thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    async def add_message(self, user_id: int, role: str, content: str):
        """Add a message to the database"""
        def _add_message():
            with self._get_conn() as conn:
                conn.execute(
                    'INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)',
                    (user_id, role, content)
                )
        
        await asyncio.get_event_loop().run_in_executor(None, _add_message)
    
    async def get_conversation_history(self, user_id: int, limit: int = 10):
        """Get conversation history for a user"""
        def _get_history():
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'SELECT role, content FROM conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
                    (user_id, limit)
                )
                messages = cursor.fetchall()
                return [{"role": role, "content": content} for role, content in reversed(messages)]
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_history)
    
    async def clear_user_history(self, user_id: int):
        """Clear all conversation history for a user"""
        def _clear_history():
            with self._get_conn() as conn:
                conn.execute(
                    'DELETE FROM conversations WHERE user_id = ?',
                    (user_id,)
                )
        
        await asyncio.get_event_loop().run_in_executor(None, _clear_history)
    
    def close(self):
        """Close all database connections"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn 

    async def set_user_prompt(self, user_id: int, prompt: str):
        """Set or update a user's system prompt"""
        def _set_prompt():
            with self._get_conn() as conn:
                # First delete any existing system prompts for this user
                conn.execute(
                    'DELETE FROM conversations WHERE user_id = ? AND role = "system"',
                    (user_id,)
                )
                # Insert new system prompt
                conn.execute(
                    'INSERT INTO conversations (user_id, role, content) VALUES (?, "system", ?)',
                    (user_id, prompt)
                )
        
        await asyncio.get_event_loop().run_in_executor(None, _set_prompt)

    async def get_user_prompt(self, user_id: int) -> str:
        """Get a user's current system prompt"""
        def _get_prompt():
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'SELECT content FROM conversations WHERE user_id = ? AND role = "system" ORDER BY timestamp DESC LIMIT 1',
                    (user_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_prompt) 