"""
Conversation State Manager - Multi-step goal tracking and context preservation
Solves the conversation memory issues where AI repeats actions instead of progressing
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)

class GoalStatus(str, Enum):
    """Status of a conversation goal"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(str, Enum):
    """Status of individual steps"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class ConversationMemory:
    """Memory item for conversation context"""
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    importance: float = 1.0  # 0.0 to 1.0, higher is more important

@dataclass
class Step:
    """Individual step in a multi-step goal"""
    id: str
    description: str
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)  # Step IDs this depends on
    
    @property
    def is_ready(self) -> bool:
        """Check if step is ready to execute (dependencies completed)"""
        return self.status == StepStatus.PENDING

@dataclass
class Goal:
    """Represents a high-level user goal that may require multiple steps"""
    id: str
    description: str
    user_query: str
    status: GoalStatus = GoalStatus.PENDING
    steps: List[Step] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    priority: float = 1.0
    expected_completion_time: Optional[float] = None
    
    def get_next_step(self) -> Optional[Step]:
        """Get the next step that's ready to execute"""
        for step in self.steps:
            if step.status == StepStatus.PENDING and step.is_ready:
                return step
        return None
    
    def get_completed_steps(self) -> List[Step]:
        """Get all completed steps"""
        return [step for step in self.steps if step.status == StepStatus.COMPLETED]
    
    def get_failed_steps(self) -> List[Step]:
        """Get all failed steps"""
        return [step for step in self.steps if step.status == StepStatus.FAILED]
    
    @property
    def is_complete(self) -> bool:
        """Check if all steps are completed"""
        return all(step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for step in self.steps)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage"""
        if not self.steps:
            return 0.0
        completed = len([s for s in self.steps if s.status == StepStatus.COMPLETED])
        return (completed / len(self.steps)) * 100.0

@dataclass
class Approach:
    """Alternative approach for achieving a goal"""
    id: str
    description: str
    steps: List[Step] = field(default_factory=list)
    estimated_time: Optional[float] = None
    success_probability: float = 0.5
    tried: bool = False

class ConversationState:
    """Manages conversation state and multi-step goals"""
    
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.current_goal: Optional[Goal] = None
        self.completed_goals: List[Goal] = []
        self.failed_goals: List[Goal] = []
        self.memory: Dict[str, ConversationMemory] = {}
        self.context_history: List[Dict[str, Any]] = []
        self.alternative_approaches: Dict[str, List[Approach]] = {}
        self.created_at = time.time()
        self.last_activity = time.time()
        self.retry_count = 0
        self.max_context_history = 50
        
    def create_goal(self, description: str, user_query: str, 
                   context: Dict[str, Any] = None) -> Goal:
        """Create a new conversation goal"""
        
        goal_id = f"goal_{int(time.time())}_{len(self.completed_goals) + len(self.failed_goals)}"
        
        goal = Goal(
            id=goal_id,
            description=description,
            user_query=user_query,
            context=context or {},
            created_at=time.time()
        )
        
        # If we have a current goal, complete it first
        if self.current_goal and self.current_goal.status == GoalStatus.IN_PROGRESS:
            self._archive_current_goal()
        
        self.current_goal = goal
        self._update_activity()
        
        logger.info("Created new conversation goal", 
                   session_id=self.session_id,
                   goal_id=goal_id,
                   description=description)
        
        return goal
    
    def add_step_to_current_goal(self, description: str, tool_name: Optional[str] = None,
                                parameters: Dict[str, Any] = None,
                                dependencies: List[str] = None) -> Optional[Step]:
        """Add a step to the current goal"""
        
        if not self.current_goal:
            logger.warning("No current goal to add step to", session_id=self.session_id)
            return None
        
        step_id = f"step_{int(time.time())}_{len(self.current_goal.steps)}"
        
        step = Step(
            id=step_id,
            description=description,
            tool_name=tool_name,
            parameters=parameters or {},
            dependencies=dependencies or []
        )
        
        self.current_goal.steps.append(step)
        self._update_activity()
        
        logger.info("Added step to current goal",
                   session_id=self.session_id,
                   goal_id=self.current_goal.id,
                   step_id=step_id,
                   description=description)
        
        return step
    
    def start_current_goal(self):
        """Mark current goal as started"""
        if self.current_goal and self.current_goal.status == GoalStatus.PENDING:
            self.current_goal.status = GoalStatus.IN_PROGRESS
            self.current_goal.started_at = time.time()
            self._update_activity()
    
    def complete_step(self, step_id: str, result: Any = None) -> bool:
        """Mark a step as completed"""
        
        if not self.current_goal:
            return False
        
        for step in self.current_goal.steps:
            if step.id == step_id:
                step.status = StepStatus.COMPLETED
                step.result = result
                step.completed_at = time.time()
                
                # Store result in memory for future reference
                self.store_memory(f"step_{step_id}_result", result, importance=0.8)
                
                self._update_activity()
                
                logger.info("Step completed",
                           session_id=self.session_id,
                           goal_id=self.current_goal.id,
                           step_id=step_id)
                
                # Check if goal is complete
                if self.current_goal.is_complete:
                    self._complete_current_goal()
                
                return True
        
        return False
    
    def fail_step(self, step_id: str, error: str) -> bool:
        """Mark a step as failed"""
        
        if not self.current_goal:
            return False
        
        for step in self.current_goal.steps:
            if step.id == step_id:
                step.status = StepStatus.FAILED
                step.error = error
                step.retry_count += 1
                
                self._update_activity()
                
                logger.warning("Step failed",
                              session_id=self.session_id,
                              goal_id=self.current_goal.id,
                              step_id=step_id,
                              error=error,
                              retry_count=step.retry_count)
                
                # Check if we can retry
                if step.retry_count < step.max_retries:
                    step.status = StepStatus.PENDING
                    logger.info("Step marked for retry", step_id=step_id)
                else:
                    # Step permanently failed - might fail the entire goal
                    self._handle_step_failure(step)
                
                return True
        
        return False
    
    def get_next_step(self) -> Optional[Step]:
        """Get the next step to execute"""
        
        if not self.current_goal or self.current_goal.status != GoalStatus.IN_PROGRESS:
            return None
        
        return self.current_goal.get_next_step()
    
    def store_memory(self, key: str, value: Any, importance: float = 1.0, 
                    expires_in: Optional[float] = None):
        """Store information in conversation memory"""
        
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in
        
        memory_item = ConversationMemory(
            key=key,
            value=value,
            importance=importance,
            expires_at=expires_at
        )
        
        self.memory[key] = memory_item
        self._update_activity()
        
        # Clean expired memories
        self._clean_expired_memories()
    
    def get_memory(self, key: str) -> Any:
        """Retrieve information from conversation memory"""
        
        memory_item = self.memory.get(key)
        if not memory_item:
            return None
        
        # Check if expired
        if memory_item.expires_at and time.time() > memory_item.expires_at:
            del self.memory[key]
            return None
        
        return memory_item.value
    
    def get_relevant_memories(self, query: str, limit: int = 5) -> List[ConversationMemory]:
        """Get memories relevant to a query"""
        
        query_lower = query.lower()
        relevant_memories = []
        
        for memory_item in self.memory.values():
            # Simple relevance scoring based on key matching and importance
            relevance_score = 0.0
            
            if query_lower in memory_item.key.lower():
                relevance_score += 0.5
            
            # Check if value contains relevant information
            if isinstance(memory_item.value, str) and query_lower in memory_item.value.lower():
                relevance_score += 0.3
            elif isinstance(memory_item.value, dict):
                value_str = json.dumps(memory_item.value).lower()
                if query_lower in value_str:
                    relevance_score += 0.3
            
            relevance_score *= memory_item.importance
            
            if relevance_score > 0:
                relevant_memories.append((memory_item, relevance_score))
        
        # Sort by relevance score
        relevant_memories.sort(key=lambda x: x[1], reverse=True)
        
        return [mem for mem, score in relevant_memories[:limit]]
    
    def add_context(self, context: Dict[str, Any]):
        """Add context information to history"""
        
        context_entry = {
            "timestamp": time.time(),
            "context": context
        }
        
        self.context_history.append(context_entry)
        
        # Limit context history size
        if len(self.context_history) > self.max_context_history:
            self.context_history = self.context_history[-self.max_context_history:]
        
        self._update_activity()
    
    def get_recent_context(self, minutes: int = 10) -> List[Dict[str, Any]]:
        """Get context from the last N minutes"""
        
        cutoff_time = time.time() - (minutes * 60)
        
        return [
            entry["context"] for entry in self.context_history
            if entry["timestamp"] > cutoff_time
        ]
    
    def has_recent_action(self, action_type: str, minutes: int = 2) -> bool:
        """Check if an action was recently performed"""
        
        cutoff_time = time.time() - (minutes * 60)
        
        # Check completed steps
        if self.current_goal:
            for step in self.current_goal.get_completed_steps():
                if (step.completed_at and step.completed_at > cutoff_time and 
                    step.tool_name == action_type):
                    return True
        
        # Check memory for recent actions
        for key, memory_item in self.memory.items():
            if (key.startswith(f"action_{action_type}") and 
                memory_item.timestamp > cutoff_time):
                return True
        
        return False
    
    def add_alternative_approach(self, goal_id: str, approach: Approach):
        """Add alternative approach for a goal"""
        
        if goal_id not in self.alternative_approaches:
            self.alternative_approaches[goal_id] = []
        
        self.alternative_approaches[goal_id].append(approach)
        
        logger.info("Added alternative approach",
                   session_id=self.session_id,
                   goal_id=goal_id,
                   approach_id=approach.id)
    
    def get_alternative_approaches(self, goal_id: str) -> List[Approach]:
        """Get alternative approaches for a goal"""
        return self.alternative_approaches.get(goal_id, [])
    
    def _complete_current_goal(self):
        """Complete the current goal"""
        
        if self.current_goal:
            self.current_goal.status = GoalStatus.COMPLETED
            self.current_goal.completed_at = time.time()
            
            self.completed_goals.append(self.current_goal)
            
            logger.info("Goal completed",
                       session_id=self.session_id,
                       goal_id=self.current_goal.id,
                       duration_seconds=self.current_goal.completed_at - self.current_goal.started_at
                       if self.current_goal.started_at else 0)
            
            self.current_goal = None
            self._update_activity()
    
    def _archive_current_goal(self):
        """Archive current goal without completing it"""
        
        if self.current_goal:
            if self.current_goal.status == GoalStatus.IN_PROGRESS:
                # Mark as failed if it was in progress
                self.current_goal.status = GoalStatus.FAILED
                self.failed_goals.append(self.current_goal)
            
            self.current_goal = None
            self._update_activity()
    
    def _handle_step_failure(self, failed_step: Step):
        """Handle permanent step failure"""
        
        logger.error("Step permanently failed",
                    session_id=self.session_id,
                    step_id=failed_step.id,
                    error=failed_step.error)
        
        # For now, mark goal as failed if any step fails permanently
        # In future, we could implement more sophisticated recovery
        if self.current_goal:
            self.current_goal.status = GoalStatus.FAILED
            self.failed_goals.append(self.current_goal)
            self.current_goal = None
    
    def _clean_expired_memories(self):
        """Remove expired memories"""
        
        current_time = time.time()
        expired_keys = []
        
        for key, memory_item in self.memory.items():
            if memory_item.expires_at and current_time > memory_item.expires_at:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory[key]
    
    def _update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current state"""
        
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "current_goal": {
                "id": self.current_goal.id,
                "description": self.current_goal.description,
                "status": self.current_goal.status.value,
                "progress": self.current_goal.progress_percentage,
                "steps_total": len(self.current_goal.steps),
                "steps_completed": len(self.current_goal.get_completed_steps()),
                "steps_failed": len(self.current_goal.get_failed_steps())
            } if self.current_goal else None,
            "completed_goals": len(self.completed_goals),
            "failed_goals": len(self.failed_goals),
            "memory_items": len(self.memory),
            "context_history_size": len(self.context_history),
            "last_activity": self.last_activity,
            "session_duration": time.time() - self.created_at
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary"""
        
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "current_goal": asdict(self.current_goal) if self.current_goal else None,
            "completed_goals": [asdict(goal) for goal in self.completed_goals],
            "failed_goals": [asdict(goal) for goal in self.failed_goals],
            "memory": {key: asdict(mem) for key, mem in self.memory.items()},
            "context_history": self.context_history,
            "alternative_approaches": {
                goal_id: [asdict(approach) for approach in approaches]
                for goal_id, approaches in self.alternative_approaches.items()
            },
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "retry_count": self.retry_count
        }

class ConversationStateManager:
    """Manages conversation states for multiple sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, ConversationState] = {}
        self._cleanup_interval = 3600  # 1 hour
        self._session_timeout = 7200  # 2 hours
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_expired_sessions())
    
    def get_or_create_session(self, session_id: str, user_id: str) -> ConversationState:
        """Get existing session or create new one"""
        
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationState(session_id, user_id)
            
            logger.info("Created new conversation session",
                       session_id=session_id,
                       user_id=user_id)
        
        return self.sessions[session_id]
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a session"""
        
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info("Removed conversation session", session_id=session_id)
            return True
        
        return False
    
    async def _cleanup_expired_sessions(self):
        """Periodically clean up expired sessions"""
        
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                
                current_time = time.time()
                expired_sessions = []
                
                for session_id, session in self.sessions.items():
                    if current_time - session.last_activity > self._session_timeout:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    del self.sessions[session_id]
                    logger.info("Cleaned up expired session", session_id=session_id)
                
                if expired_sessions:
                    logger.info("Session cleanup completed", 
                               removed_count=len(expired_sessions))
                    
            except Exception as e:
                logger.error("Error in session cleanup", error=str(e))
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len(self.sessions)
    
    def get_session_summaries(self) -> List[Dict[str, Any]]:
        """Get summaries of all active sessions"""
        
        return [session.get_state_summary() for session in self.sessions.values()]

# Global conversation state manager
conversation_state_manager = ConversationStateManager()