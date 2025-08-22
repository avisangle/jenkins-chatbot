"""
Conversation Service for managing chat sessions and history
Handles Redis-based session storage and conversation context
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any
import structlog
import redis.asyncio as redis

from app.config import settings
from app.models import ChatMessage, UserContext
from app.redis_client import get_redis

logger = structlog.get_logger(__name__)

class ConversationService:
    """Service for managing chat conversations and sessions"""
    
    def __init__(self):
        self.redis = None
        
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if not self.redis:
            self.redis = await get_redis()
        return self.redis
    
    async def create_session(
        self, 
        user_id: str, 
        user_token: str, 
        permissions: List[str], 
        timeout: int = 900
    ) -> Dict[str, Any]:
        """Create a new chat session"""
        
        session_id = str(uuid.uuid4())
        created_at = int(time.time() * 1000)
        expires_at = created_at + (timeout * 1000)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "user_token": user_token,
            "permissions": permissions,
            "created_at": created_at,
            "last_activity": created_at,
            "expires_at": expires_at,
            "conversation_history": [],
            "pending_actions": [],
            "context": {
                "current_jobs": [],
                "last_build_status": {},
                "workspace_info": "",
                "user_preferences": {}
            }
        }
        
        try:
            redis_client = await self._get_redis()
            
            # Store session data
            session_key = f"session:{user_id}:{session_id}"
            await redis_client.setex(
                session_key,
                timeout,
                json.dumps(session_data, default=str)
            )
            
            # Store conversation history separately with longer TTL
            conversation_key = f"conversation:{session_id}"
            await redis_client.setex(
                conversation_key,
                settings.REDIS_CONVERSATION_TTL,
                json.dumps({"messages": []}, default=str)
            )
            
            logger.info("Session created",
                       session_id=session_id,
                       user_id=user_id,
                       expires_at=expires_at)
            
            return session_data
            
        except Exception as e:
            logger.error("Failed to create session",
                        error=str(e),
                        user_id=user_id)
            raise
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        
        try:
            redis_client = await self._get_redis()
            
            # Try to find session by scanning all user session keys
            # In production, you might want to store user_id -> session_id mapping
            pattern = f"session:*:{session_id}"
            
            async for key in redis_client.scan_iter(match=pattern):
                session_data = await redis_client.get(key)
                if session_data:
                    data = json.loads(session_data)
                    
                    # Check if session is expired
                    if data.get("expires_at", 0) < int(time.time() * 1000):
                        await redis_client.delete(key)
                        return None
                    
                    # Update last activity
                    data["last_activity"] = int(time.time() * 1000)
                    await redis_client.setex(
                        key,
                        settings.CHAT_SESSION_TIMEOUT,
                        json.dumps(data, default=str)
                    )
                    
                    return data
            
            return None
            
        except Exception as e:
            logger.error("Failed to get session",
                        error=str(e),
                        session_id=session_id)
            return None
    
    async def update_session_context(
        self, 
        session_id: str, 
        context_update: Dict[str, Any]
    ) -> bool:
        """Update session context"""
        
        try:
            session = await self.get_session(session_id)
            if not session:
                return False
            
            # Merge context updates
            if "context" not in session:
                session["context"] = {}
            
            session["context"].update(context_update)
            session["last_activity"] = int(time.time() * 1000)
            
            # Save updated session
            redis_client = await self._get_redis()
            pattern = f"session:*:{session_id}"
            
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.setex(
                    key,
                    settings.CHAT_SESSION_TIMEOUT,
                    json.dumps(session, default=str)
                )
                break
            
            return True
            
        except Exception as e:
            logger.error("Failed to update session context",
                        error=str(e),
                        session_id=session_id)
            return False
    
    async def add_interaction(
        self,
        session_id: str,
        user_message: str,
        ai_response: str,
        actions: Optional[List[Any]] = None,
        tool_results: Optional[List[Any]] = None
    ) -> bool:
        """Add a conversation interaction"""
        
        try:
            redis_client = await self._get_redis()
            conversation_key = f"conversation:{session_id}"
            
            # Get existing conversation
            conversation_data = await redis_client.get(conversation_key)
            if conversation_data:
                conversation = json.loads(conversation_data)
            else:
                conversation = {"messages": []}
            
            timestamp = int(time.time() * 1000)
            
            # Add user message
            conversation["messages"].append({
                "timestamp": timestamp,
                "role": "user",
                "content": user_message,
                "metadata": {}
            })
            
            # Add AI response
            conversation["messages"].append({
                "timestamp": timestamp + 1,  # Slight offset to maintain order
                "role": "assistant",
                "content": ai_response,
                "actions_taken": [str(action) for action in actions] if actions else [],
                "tool_results": tool_results if tool_results else [],
                "metadata": {}
            })
            
            # Limit conversation length
            if len(conversation["messages"]) > settings.MAX_CONVERSATION_LENGTH * 2:
                # Remove oldest messages (keep pairs)
                conversation["messages"] = conversation["messages"][-settings.MAX_CONVERSATION_LENGTH * 2:]
            
            # Save updated conversation
            await redis_client.setex(
                conversation_key,
                settings.REDIS_CONVERSATION_TTL,
                json.dumps(conversation, default=str)
            )
            
            logger.info("Interaction added to conversation",
                       session_id=session_id,
                       message_count=len(conversation["messages"]))
            
            return True
            
        except Exception as e:
            logger.error("Failed to add interaction",
                        error=str(e),
                        session_id=session_id)
            return False
    
    async def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session"""
        
        try:
            redis_client = await self._get_redis()
            conversation_key = f"conversation:{session_id}"
            
            conversation_data = await redis_client.get(conversation_key)
            if not conversation_data:
                return []
            
            conversation = json.loads(conversation_data)
            messages = conversation.get("messages", [])
            
            # Return most recent messages
            return messages[-limit:] if len(messages) > limit else messages
            
        except Exception as e:
            logger.error("Failed to get conversation history",
                        error=str(e),
                        session_id=session_id)
            return []
    
    async def clear_conversation(self, session_id: str) -> bool:
        """Clear conversation history for a session"""
        
        try:
            redis_client = await self._get_redis()
            conversation_key = f"conversation:{session_id}"
            
            # Reset conversation to empty
            await redis_client.setex(
                conversation_key,
                settings.REDIS_CONVERSATION_TTL,
                json.dumps({"messages": []}, default=str)
            )
            
            logger.info("Conversation cleared", session_id=session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to clear conversation",
                        error=str(e),
                        session_id=session_id)
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its conversation"""
        
        try:
            redis_client = await self._get_redis()
            
            # Delete session
            pattern = f"session:*:{session_id}"
            deleted_count = 0
            
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.delete(key)
                deleted_count += 1
            
            # Delete conversation
            conversation_key = f"conversation:{session_id}"
            await redis_client.delete(conversation_key)
            
            logger.info("Session deleted",
                       session_id=session_id,
                       deleted_keys=deleted_count + 1)
            
            return True
            
        except Exception as e:
            logger.error("Failed to delete session",
                        error=str(e),
                        session_id=session_id)
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        
        try:
            redis_client = await self._get_redis()
            current_time = int(time.time() * 1000)
            deleted_count = 0
            
            # Scan all session keys
            pattern = "session:*"
            async for key in redis_client.scan_iter(match=pattern):
                session_data = await redis_client.get(key)
                if session_data:
                    data = json.loads(session_data)
                    if data.get("expires_at", 0) < current_time:
                        # Session expired, delete it and its conversation
                        session_id = data.get("session_id")
                        await redis_client.delete(key)
                        if session_id:
                            conversation_key = f"conversation:{session_id}"
                            await redis_client.delete(conversation_key)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info("Expired sessions cleaned up", count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            logger.error("Failed to cleanup expired sessions", error=str(e))
            return 0
    
    async def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        
        try:
            redis_client = await self._get_redis()
            pattern = "session:*"
            count = 0
            
            async for key in redis_client.scan_iter(match=pattern):
                count += 1
            
            return count
            
        except Exception as e:
            logger.error("Failed to get active session count", error=str(e))
            return 0
    
    async def health_check(self) -> bool:
        """Health check for conversation service"""
        try:
            redis_client = await self._get_redis()
            await redis_client.ping()
            return True
        except Exception as e:
            logger.error("Conversation service health check failed", error=str(e))
            return False
    
    async def redis_health_check(self) -> bool:
        """Specific Redis health check"""
        return await self.health_check()