"""
Context Manager for Entity Tracking and Working Memory
Maintains conversation state, entities, and contextual relationships
"""

import json
import time
import re
from typing import Dict, List, Optional, Any, Set
import structlog
import redis.asyncio as redis

from app.config import settings
from app.redis_client import get_redis

logger = structlog.get_logger(__name__)

class ContextualEntity:
    """Represents an entity mentioned in conversation with context"""
    
    def __init__(self, entity_type: str, name: str, first_mentioned_at: int):
        self.entity_type = entity_type  # 'job', 'build', 'user', 'action'
        self.name = name
        self.first_mentioned_at = first_mentioned_at
        self.last_mentioned_at = first_mentioned_at
        self.mention_count = 1
        self.associated_data = {}  # Store related information
        self.relationships = {}  # Store relationships to other entities

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "entity_type": self.entity_type,
            "name": self.name,
            "first_mentioned_at": self.first_mentioned_at,
            "last_mentioned_at": self.last_mentioned_at,
            "mention_count": self.mention_count,
            "associated_data": self.associated_data,
            "relationships": self.relationships
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextualEntity':
        """Create entity from dictionary"""
        entity = cls(
            entity_type=data["entity_type"],
            name=data["name"],
            first_mentioned_at=data["first_mentioned_at"]
        )
        entity.last_mentioned_at = data.get("last_mentioned_at", entity.first_mentioned_at)
        entity.mention_count = data.get("mention_count", 1)
        entity.associated_data = data.get("associated_data", {})
        entity.relationships = data.get("relationships", {})
        return entity

class ConversationContext:
    """Maintains working memory for a conversation session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.entities: Dict[str, ContextualEntity] = {}
        self.current_focus = None  # Currently focused entity
        self.last_action = None
        self.conversation_state = "browsing"  # browsing, focused, executing
        self.pending_references = []  # Unresolved pronouns/references
        
    def add_entity(self, entity_type: str, name: str, timestamp: int = None) -> ContextualEntity:
        """Add or update an entity in context"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        
        entity_key = f"{entity_type}:{name}"
        
        if entity_key in self.entities:
            # Update existing entity
            entity = self.entities[entity_key]
            entity.last_mentioned_at = timestamp
            entity.mention_count += 1
        else:
            # Create new entity
            entity = ContextualEntity(entity_type, name, timestamp)
            self.entities[entity_key] = entity
        
        # Update current focus for certain entity types
        if entity_type in ['job', 'build']:
            self.current_focus = entity_key
            
        return entity
    
    def get_entity(self, entity_type: str, name: str) -> Optional[ContextualEntity]:
        """Get entity by type and name"""
        entity_key = f"{entity_type}:{name}"
        return self.entities.get(entity_key)
    
    def get_recent_entities(self, entity_type: str = None, limit: int = 5) -> List[ContextualEntity]:
        """Get recently mentioned entities"""
        entities = list(self.entities.values())
        
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]
        
        # Sort by last mentioned time
        entities.sort(key=lambda e: e.last_mentioned_at, reverse=True)
        
        return entities[:limit]
    
    def resolve_reference(self, reference: str) -> Optional[ContextualEntity]:
        """Resolve pronouns and references to entities"""
        reference_lower = reference.lower()
        
        # Direct reference resolution
        if reference_lower in ['it', 'that', 'this']:
            if self.current_focus:
                return self.entities.get(self.current_focus)
        
        # Job-specific references
        if reference_lower in ['the job', 'that job', 'this job']:
            recent_jobs = self.get_recent_entities('job', limit=1)
            return recent_jobs[0] if recent_jobs else None
        
        # Build-specific references
        if reference_lower in ['the build', 'that build', 'this build']:
            recent_builds = self.get_recent_entities('build', limit=1)
            return recent_builds[0] if recent_builds else None
        
        # Last action references
        if reference_lower in ['it', 'that', 'the last one']:
            if self.last_action:
                return self.entities.get(self.current_focus)
        
        return None
    
    def update_state(self, new_state: str):
        """Update conversation state"""
        self.conversation_state = new_state
    
    def set_action(self, action: str, target_entity: str = None):
        """Set the last action performed"""
        self.last_action = action
        if target_entity:
            self.current_focus = target_entity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "current_focus": self.current_focus,
            "last_action": self.last_action,
            "conversation_state": self.conversation_state,
            "pending_references": self.pending_references
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Create context from dictionary"""
        context = cls(data["session_id"])
        context.entities = {k: ContextualEntity.from_dict(v) for k, v in data.get("entities", {}).items()}
        context.current_focus = data.get("current_focus")
        context.last_action = data.get("last_action")
        context.conversation_state = data.get("conversation_state", "browsing")
        context.pending_references = data.get("pending_references", [])
        return context

class ContextManager:
    """Manages contextual entities and working memory across conversations"""
    
    def __init__(self):
        self.redis = None
        
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if not self.redis:
            self.redis = await get_redis()
        return self.redis
    
    async def extract_entities_from_message(self, message: str, session_id: str) -> Dict[str, List[str]]:
        """Extract entities from a message using pattern matching"""
        entities = {
            'jobs': [],
            'builds': [],
            'actions': [],
            'references': []
        }
        
        # Job name patterns (common Jenkins job naming conventions)
        job_patterns = [
            r'(?:job|Job)\s+([A-Za-z0-9_\-\.]+)',
            r'([A-Za-z0-9_\-\.]+(?:-CICD|-Pipeline|-Build|-Deploy))',
            r'(?:trigger|start|run|execute)\s+([A-Za-z0-9_\-\.]+)',
            r'(?:build|check|monitor)\s+([A-Za-z0-9_\-\.]+)'
        ]
        
        for pattern in job_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            entities['jobs'].extend(matches)
        
        # Build number patterns
        build_patterns = [
            r'(?:build|Build)\s+(?:number\s+)?(\d+)',
            r'(?:#)(\d+)',
            r'(?:run|execution)\s+(\d+)'
        ]
        
        for pattern in build_patterns:
            matches = re.findall(pattern, message)
            entities['builds'].extend(matches)
        
        # Action patterns
        action_patterns = [
            r'(trigger|start|run|execute|stop|restart|pause|resume)',
            r'(get|fetch|retrieve|show|display)\s+(?:me\s+)?(?:the\s+)?(log|logs|output|status|info|information)',
            r'(check|monitor|watch|view|see)\s+(?:the\s+)?(status|progress|build|job)',
            r'(cancel|abort|terminate|kill)'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, message.lower())
            entities['actions'].extend([match[0] if isinstance(match, tuple) else match for match in matches])
        
        # Reference patterns (pronouns and implicit references)
        reference_patterns = [
            r'\b(it|that|this|the\s+(?:job|build|one|last\s+one))\b'
        ]
        
        for pattern in reference_patterns:
            matches = re.findall(pattern, message.lower())
            entities['references'].extend(matches)
        
        # Remove duplicates
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities
    
    async def update_context_from_message(self, message: str, session_id: str, role: str = "user") -> ConversationContext:
        """Update conversation context based on message content"""
        try:
            # Get existing context or create new one
            context = await self.get_conversation_context(session_id)
            if not context:
                context = ConversationContext(session_id)
            
            # Extract entities from message
            entities = await self.extract_entities_from_message(message, session_id)
            timestamp = int(time.time() * 1000)
            
            # Add jobs to context
            for job_name in entities['jobs']:
                entity = context.add_entity('job', job_name, timestamp)
                logger.info("Added job entity to context", job=job_name, session_id=session_id)
            
            # Add builds to context with job relationships
            for build_number in entities['builds']:
                entity = context.add_entity('build', build_number, timestamp)
                # Link build to current job focus if available
                if context.current_focus and context.current_focus.startswith('job:'):
                    job_entity = context.entities[context.current_focus]
                    entity.relationships['job'] = job_entity.name
                    job_entity.relationships.setdefault('builds', []).append(build_number)
                logger.info("Added build entity to context", build=build_number, session_id=session_id)
            
            # Track actions
            for action in entities['actions']:
                context.set_action(action)
                context.add_entity('action', action, timestamp)
                logger.info("Tracked action in context", action=action, session_id=session_id)
            
            # Save updated context
            await self.save_conversation_context(context)
            
            return context
            
        except Exception as e:
            logger.error("Failed to update context from message", error=str(e), session_id=session_id)
            return ConversationContext(session_id)  # Return empty context on error
    
    async def get_conversation_context(self, session_id: str) -> Optional[ConversationContext]:
        """Retrieve conversation context from Redis"""
        try:
            redis_client = await self._get_redis()
            context_key = f"context:{session_id}"
            
            context_data = await redis_client.get(context_key)
            if not context_data:
                return None
            
            data = json.loads(context_data)
            return ConversationContext.from_dict(data)
            
        except Exception as e:
            logger.error("Failed to get conversation context", error=str(e), session_id=session_id)
            return None
    
    async def save_conversation_context(self, context: ConversationContext) -> bool:
        """Save conversation context to Redis"""
        try:
            redis_client = await self._get_redis()
            context_key = f"context:{context.session_id}"
            
            context_data = json.dumps(context.to_dict(), default=str)
            await redis_client.setex(
                context_key,
                settings.REDIS_CONVERSATION_TTL,
                context_data
            )
            
            logger.debug("Conversation context saved", session_id=context.session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to save conversation context", error=str(e), session_id=context.session_id)
            return False
    
    async def resolve_references_in_message(self, message: str, session_id: str) -> str:
        """Resolve pronouns and references in message to explicit entities"""
        try:
            context = await self.get_conversation_context(session_id)
            if not context:
                return message
            
            # Simple reference resolution
            resolved_message = message
            
            # Replace "it" with current focus
            if re.search(r'\bit\b', message.lower()) and context.current_focus:
                entity = context.entities.get(context.current_focus)
                if entity:
                    resolved_message = re.sub(
                        r'\bit\b', 
                        f'{entity.entity_type} {entity.name}', 
                        resolved_message, 
                        flags=re.IGNORECASE
                    )
            
            # Replace "the job" with last mentioned job
            if re.search(r'\bthe job\b', message.lower()):
                recent_jobs = context.get_recent_entities('job', limit=1)
                if recent_jobs:
                    resolved_message = re.sub(
                        r'\bthe job\b', 
                        f'job {recent_jobs[0].name}', 
                        resolved_message, 
                        flags=re.IGNORECASE
                    )
            
            # Replace "the build" with last mentioned build
            if re.search(r'\bthe build\b', message.lower()):
                recent_builds = context.get_recent_entities('build', limit=1)
                if recent_builds:
                    resolved_message = re.sub(
                        r'\bthe build\b', 
                        f'build {recent_builds[0].name}', 
                        resolved_message, 
                        flags=re.IGNORECASE
                    )
            
            if resolved_message != message:
                logger.info("Resolved references in message", 
                          original=message[:50], 
                          resolved=resolved_message[:50], 
                          session_id=session_id)
            
            return resolved_message
            
        except Exception as e:
            logger.error("Failed to resolve references", error=str(e), session_id=session_id)
            return message
    
    async def get_context_summary(self, session_id: str) -> str:
        """Generate a context summary for the AI"""
        try:
            context = await self.get_conversation_context(session_id)
            if not context:
                return "No contextual information available."
            
            summary_parts = []
            
            # Current focus
            if context.current_focus:
                entity = context.entities.get(context.current_focus)
                if entity:
                    summary_parts.append(f"Current focus: {entity.entity_type} '{entity.name}'")
            
            # Recent entities
            recent_jobs = context.get_recent_entities('job', limit=3)
            if recent_jobs:
                job_names = [job.name for job in recent_jobs]
                summary_parts.append(f"Recent jobs discussed: {', '.join(job_names)}")
            
            recent_builds = context.get_recent_entities('build', limit=3)
            if recent_builds:
                build_numbers = [build.name for build in recent_builds]
                summary_parts.append(f"Recent builds discussed: {', '.join(build_numbers)}")
            
            # Last action
            if context.last_action:
                summary_parts.append(f"Last action: {context.last_action}")
            
            # Conversation state
            summary_parts.append(f"Conversation state: {context.conversation_state}")
            
            return " | ".join(summary_parts) if summary_parts else "No specific context available."
            
        except Exception as e:
            logger.error("Failed to generate context summary", error=str(e), session_id=session_id)
            return "Error generating context summary."
    
    async def clear_context(self, session_id: str) -> bool:
        """Clear conversation context"""
        try:
            redis_client = await self._get_redis()
            context_key = f"context:{session_id}"
            await redis_client.delete(context_key)
            
            logger.info("Conversation context cleared", session_id=session_id)
            return True
            
        except Exception as e:
            logger.error("Failed to clear context", error=str(e), session_id=session_id)
            return False

# Global context manager instance
context_manager = ContextManager()