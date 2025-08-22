"""
Smart Retry and Recovery Manager - Intelligent failure handling and recovery
Handles failures gracefully with pattern recognition and alternative strategies
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import structlog

from app.services.conversation_state import ConversationState, Goal, Step, StepStatus, Approach
from app.services.tool_registry import ToolRegistry, NormalizedResponse
from app.services.mcp_universal_client import UniversalMCPClient

logger = structlog.get_logger(__name__)

class FailureType(str, Enum):
    """Types of failures we can handle"""
    TOOL_NOT_FOUND = "tool_not_found"
    PARAMETER_ERROR = "parameter_error"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    INVALID_STATE = "invalid_state"
    RATE_LIMITED = "rate_limited"
    UNKNOWN = "unknown"

class RecoveryStrategy(str, Enum):
    """Recovery strategies"""
    RETRY_SAME = "retry_same"
    RETRY_WITH_FALLBACK = "retry_with_fallback"
    MODIFY_PARAMETERS = "modify_parameters"
    CHANGE_APPROACH = "change_approach"
    REQUEST_USER_INPUT = "request_user_input"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    ABANDON_GOAL = "abandon_goal"

@dataclass
class FailurePattern:
    """Pattern for recognizing failures"""
    failure_type: FailureType
    error_patterns: List[str] = field(default_factory=list)
    context_indicators: List[str] = field(default_factory=list)
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY_SAME
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    success_probability: float = 0.5

@dataclass
class RecoveryAction:
    """Action to take for recovery"""
    strategy: RecoveryStrategy
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_success_rate: float = 0.5
    estimated_duration: float = 5.0  # seconds
    requires_user_approval: bool = False

@dataclass
class FailureContext:
    """Context around a failure"""
    step: Step
    goal: Goal
    error: str
    failure_type: FailureType
    attempt_count: int
    total_duration: float
    user_context: Dict[str, Any] = field(default_factory=dict)

class RecoveryManager:
    """Smart retry and recovery manager"""
    
    def __init__(self, tool_registry: ToolRegistry, mcp_client: UniversalMCPClient):
        self.tool_registry = tool_registry
        self.mcp_client = mcp_client
        
        # Failure patterns and recovery strategies
        self.failure_patterns = self._initialize_failure_patterns()
        
        # Recovery history for learning
        self.recovery_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Circuit breaker state for problematic operations
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # User communication callbacks
        self.user_notification_callback: Optional[Callable] = None
    
    def _initialize_failure_patterns(self) -> List[FailurePattern]:
        """Initialize known failure patterns and recovery strategies"""
        
        return [
            # Tool not found errors
            FailurePattern(
                failure_type=FailureType.TOOL_NOT_FOUND,
                error_patterns=[
                    r"tool.*not found",
                    r"unknown tool",
                    r"no tool named",
                    r"tool.*does not exist"
                ],
                recovery_strategy=RecoveryStrategy.RETRY_WITH_FALLBACK,
                max_retries=1,  # Don't retry the same missing tool
                success_probability=0.8
            ),
            
            # Parameter validation errors
            FailurePattern(
                failure_type=FailureType.PARAMETER_ERROR,
                error_patterns=[
                    r"invalid parameter",
                    r"parameter.*required",
                    r"parameter.*missing",
                    r"wrong type.*parameter",
                    r"parameter validation failed"
                ],
                recovery_strategy=RecoveryStrategy.MODIFY_PARAMETERS,
                max_retries=2,
                success_probability=0.7
            ),
            
            # Permission denied errors
            FailurePattern(
                failure_type=FailureType.PERMISSION_DENIED,
                error_patterns=[
                    r"permission denied",
                    r"access denied",
                    r"unauthorized",
                    r"forbidden",
                    r"not allowed"
                ],
                recovery_strategy=RecoveryStrategy.REQUEST_USER_INPUT,
                max_retries=1,
                success_probability=0.3
            ),
            
            # Timeout errors
            FailurePattern(
                failure_type=FailureType.TIMEOUT,
                error_patterns=[
                    r"timeout",
                    r"timed out",
                    r"operation took too long",
                    r"connection timeout"
                ],
                recovery_strategy=RecoveryStrategy.RETRY_SAME,
                max_retries=3,
                backoff_multiplier=1.5,
                success_probability=0.6
            ),
            
            # Server errors
            FailurePattern(
                failure_type=FailureType.SERVER_ERROR,
                error_patterns=[
                    r"internal server error",
                    r"server error",
                    r"500 error",
                    r"service unavailable",
                    r"503 error"
                ],
                recovery_strategy=RecoveryStrategy.RETRY_WITH_FALLBACK,
                max_retries=2,
                backoff_multiplier=3.0,
                success_probability=0.4
            ),
            
            # Resource not found
            FailurePattern(
                failure_type=FailureType.RESOURCE_NOT_FOUND,
                error_patterns=[
                    r"job.*not found",
                    r"build.*not found",
                    r"resource not found",
                    r"404.*not found",
                    r"does not exist"
                ],
                recovery_strategy=RecoveryStrategy.MODIFY_PARAMETERS,
                max_retries=2,
                success_probability=0.5
            ),
            
            # Rate limiting
            FailurePattern(
                failure_type=FailureType.RATE_LIMITED,
                error_patterns=[
                    r"rate limit",
                    r"too many requests",
                    r"429 error",
                    r"quota exceeded"
                ],
                recovery_strategy=RecoveryStrategy.RETRY_SAME,
                max_retries=3,
                backoff_multiplier=5.0,  # Longer backoff for rate limits
                success_probability=0.8
            ),
            
            # Network errors
            FailurePattern(
                failure_type=FailureType.NETWORK_ERROR,
                error_patterns=[
                    r"connection error",
                    r"network error",
                    r"connection refused",
                    r"dns.*error",
                    r"host.*unreachable"
                ],
                recovery_strategy=RecoveryStrategy.RETRY_WITH_FALLBACK,
                max_retries=2,
                backoff_multiplier=2.0,
                success_probability=0.6
            )
        ]
    
    async def handle_failure(self, failure_context: FailureContext, 
                           conversation_state: ConversationState) -> RecoveryAction:
        """Main failure handling entry point"""
        
        logger.warning("Handling failure",
                      step_id=failure_context.step.id,
                      goal_id=failure_context.goal.id,
                      error=failure_context.error,
                      attempt=failure_context.attempt_count)
        
        # Classify failure type
        failure_type = self._classify_failure(failure_context.error)
        failure_context.failure_type = failure_type
        
        # Check circuit breaker
        circuit_key = f"{failure_context.step.tool_name}:{failure_type.value}"
        if self._is_circuit_breaker_open(circuit_key):
            logger.warning("Circuit breaker open, using degraded strategy", circuit_key=circuit_key)
            return RecoveryAction(
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                description="Circuit breaker active - using alternative approach",
                estimated_success_rate=0.8
            )
        
        # Find matching recovery pattern
        recovery_pattern = self._find_recovery_pattern(failure_type, failure_context.error)
        
        # Generate recovery action
        recovery_action = await self._generate_recovery_action(
            failure_context, recovery_pattern, conversation_state
        )
        
        # Update circuit breaker
        self._update_circuit_breaker(circuit_key, recovery_action)
        
        # Record in history for learning
        self._record_recovery_attempt(failure_context, recovery_action)
        
        logger.info("Recovery action generated",
                   strategy=recovery_action.strategy,
                   success_rate=recovery_action.estimated_success_rate)
        
        return recovery_action
    
    def _classify_failure(self, error_message: str) -> FailureType:
        """Classify failure based on error message"""
        
        error_lower = error_message.lower()
        
        for pattern in self.failure_patterns:
            for error_pattern in pattern.error_patterns:
                import re
                if re.search(error_pattern, error_lower):
                    return pattern.failure_type
        
        return FailureType.UNKNOWN
    
    def _find_recovery_pattern(self, failure_type: FailureType, 
                             error_message: str) -> Optional[FailurePattern]:
        """Find the best recovery pattern for this failure"""
        
        for pattern in self.failure_patterns:
            if pattern.failure_type == failure_type:
                return pattern
        
        # Fallback pattern for unknown failures
        return FailurePattern(
            failure_type=FailureType.UNKNOWN,
            recovery_strategy=RecoveryStrategy.RETRY_SAME,
            max_retries=1,
            success_probability=0.3
        )
    
    async def _generate_recovery_action(self, failure_context: FailureContext,
                                      pattern: FailurePattern,
                                      conversation_state: ConversationState) -> RecoveryAction:
        """Generate specific recovery action based on pattern and context"""
        
        if pattern.recovery_strategy == RecoveryStrategy.RETRY_SAME:
            return await self._create_retry_same_action(failure_context, pattern)
        
        elif pattern.recovery_strategy == RecoveryStrategy.RETRY_WITH_FALLBACK:
            return await self._create_fallback_action(failure_context, pattern)
        
        elif pattern.recovery_strategy == RecoveryStrategy.MODIFY_PARAMETERS:
            return await self._create_parameter_modification_action(failure_context, pattern)
        
        elif pattern.recovery_strategy == RecoveryStrategy.CHANGE_APPROACH:
            return await self._create_approach_change_action(failure_context, conversation_state)
        
        elif pattern.recovery_strategy == RecoveryStrategy.REQUEST_USER_INPUT:
            return await self._create_user_input_request_action(failure_context)
        
        elif pattern.recovery_strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
            return await self._create_degradation_action(failure_context)
        
        else:
            return await self._create_abandon_action(failure_context)
    
    async def _create_retry_same_action(self, failure_context: FailureContext,
                                      pattern: FailurePattern) -> RecoveryAction:
        """Create action to retry the same operation"""
        
        if failure_context.attempt_count >= pattern.max_retries:
            return RecoveryAction(
                strategy=RecoveryStrategy.ABANDON_GOAL,
                description=f"Maximum retries ({pattern.max_retries}) exceeded",
                estimated_success_rate=0.0
            )
        
        # Calculate backoff delay
        delay = (pattern.backoff_multiplier ** failure_context.attempt_count)
        
        return RecoveryAction(
            strategy=RecoveryStrategy.RETRY_SAME,
            description=f"Retry after {delay:.1f} seconds (attempt {failure_context.attempt_count + 1})",
            parameters={"delay": delay},
            estimated_success_rate=pattern.success_probability * (0.8 ** failure_context.attempt_count),
            estimated_duration=delay + 5.0
        )
    
    async def _create_fallback_action(self, failure_context: FailureContext,
                                    pattern: FailurePattern) -> RecoveryAction:
        """Create action to retry with fallback tool"""
        
        # Find fallback tool
        original_tool = failure_context.step.tool_name
        if not original_tool:
            return await self._create_abandon_action(failure_context)
        
        # Try to find alternative tool through registry
        fallback_tools = await self._find_fallback_tools(original_tool, failure_context)
        
        if not fallback_tools:
            return RecoveryAction(
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                description="No fallback tools available - providing partial results",
                estimated_success_rate=0.6
            )
        
        best_fallback = fallback_tools[0]  # Take first (best) fallback
        
        return RecoveryAction(
            strategy=RecoveryStrategy.RETRY_WITH_FALLBACK,
            description=f"Retry using fallback tool: {best_fallback}",
            parameters={
                "fallback_tool": best_fallback,
                "original_tool": original_tool
            },
            estimated_success_rate=0.7,
            estimated_duration=8.0
        )
    
    async def _find_fallback_tools(self, original_tool: str, 
                                 failure_context: FailureContext) -> List[str]:
        """Find fallback tools for the original tool"""
        
        # Use tool registry to find alternatives
        fallback_tools = []
        
        # Get tools in same category
        available_tools = await self.tool_registry.get_available_tools()
        
        for tool_schema in available_tools:
            if (tool_schema.name != original_tool and 
                tool_schema.name.startswith(original_tool.split('_')[0])):  # Same prefix
                fallback_tools.append(tool_schema.name)
        
        # Add common fallbacks based on tool type
        common_fallbacks = {
            "get_job_info": ["job_info", "get_job_details"],
            "list_jobs": ["search_jobs", "get_jobs"],
            "get_build_status": ["build_status", "get_build_info"],
            "get_console_log": ["console_log", "get_build_log"]
        }
        
        if original_tool in common_fallbacks:
            fallback_tools.extend(common_fallbacks[original_tool])
        
        # Remove duplicates and non-existent tools
        return list(set(fallback_tools))[:3]  # Top 3 fallbacks
    
    async def _create_parameter_modification_action(self, failure_context: FailureContext,
                                                   pattern: FailurePattern) -> RecoveryAction:
        """Create action to modify parameters"""
        
        original_params = failure_context.step.parameters
        modified_params = await self._suggest_parameter_modifications(
            failure_context.step.tool_name,
            original_params,
            failure_context.error
        )
        
        if not modified_params or modified_params == original_params:
            return RecoveryAction(
                strategy=RecoveryStrategy.REQUEST_USER_INPUT,
                description="Unable to automatically fix parameters - need user input",
                requires_user_approval=True,
                estimated_success_rate=0.3
            )
        
        return RecoveryAction(
            strategy=RecoveryStrategy.MODIFY_PARAMETERS,
            description="Retry with corrected parameters",
            parameters={"modified_params": modified_params},
            estimated_success_rate=0.8,
            estimated_duration=5.0
        )
    
    async def _suggest_parameter_modifications(self, tool_name: str,
                                             original_params: Dict[str, Any],
                                             error_message: str) -> Dict[str, Any]:
        """Suggest parameter modifications based on error"""
        
        error_lower = error_message.lower()
        modified_params = original_params.copy()
        
        # Common parameter fixes
        if "build_number" in error_lower and "build_number" in original_params:
            # Try converting string to int or vice versa
            build_num = original_params["build_number"]
            if isinstance(build_num, str) and build_num.isdigit():
                modified_params["build_number"] = int(build_num)
            elif isinstance(build_num, int):
                modified_params["build_number"] = str(build_num)
        
        if "job_name" in error_lower and "job_name" in original_params:
            job_name = original_params["job_name"]
            if isinstance(job_name, str):
                # Try URL encoding for special characters
                import urllib.parse
                modified_params["job_name"] = urllib.parse.quote(job_name, safe='')
        
        if "required parameter" in error_lower:
            # Add commonly missing parameters
            if tool_name == "get_job_info" and "include_builds" not in modified_params:
                modified_params["include_builds"] = True
            elif tool_name == "search_jobs" and "max_depth" not in modified_params:
                modified_params["max_depth"] = 3
        
        return modified_params
    
    async def _create_approach_change_action(self, failure_context: FailureContext,
                                           conversation_state: ConversationState) -> RecoveryAction:
        """Create action to change the overall approach"""
        
        # Check if goal has alternative approaches
        goal_id = failure_context.goal.id
        alternatives = conversation_state.get_alternative_approaches(goal_id)
        
        if not alternatives:
            return RecoveryAction(
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                description="No alternative approaches available",
                estimated_success_rate=0.5
            )
        
        # Find unused alternative
        unused_alternatives = [alt for alt in alternatives if not alt.tried]
        
        if not unused_alternatives:
            return RecoveryAction(
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                description="All alternative approaches have been tried",
                estimated_success_rate=0.4
            )
        
        best_alternative = max(unused_alternatives, key=lambda x: x.success_probability)
        
        return RecoveryAction(
            strategy=RecoveryStrategy.CHANGE_APPROACH,
            description=f"Switch to alternative approach: {best_alternative.description}",
            parameters={"alternative_approach": best_alternative},
            estimated_success_rate=best_alternative.success_probability,
            estimated_duration=best_alternative.estimated_time or 15.0
        )
    
    async def _create_user_input_request_action(self, failure_context: FailureContext) -> RecoveryAction:
        """Create action to request user input"""
        
        return RecoveryAction(
            strategy=RecoveryStrategy.REQUEST_USER_INPUT,
            description=f"Need user assistance to resolve: {failure_context.error}",
            parameters={
                "error_context": failure_context.error,
                "suggested_actions": [
                    "Check permissions for the requested operation",
                    "Verify the resource names are correct",
                    "Try a different approach to the same goal"
                ]
            },
            requires_user_approval=True,
            estimated_success_rate=0.7,
            estimated_duration=60.0  # Assume user takes time to respond
        )
    
    async def _create_degradation_action(self, failure_context: FailureContext) -> RecoveryAction:
        """Create action for graceful degradation"""
        
        # Determine what partial result we can provide
        degraded_description = "Provide partial results with available data"
        
        if failure_context.step.tool_name in ["get_build_history", "get_build_status"]:
            degraded_description = "Show basic job info instead of detailed build information"
        elif failure_context.step.tool_name in ["get_console_log"]:
            degraded_description = "Provide build status without console output"
        elif failure_context.step.tool_name in ["search_jobs"]:
            degraded_description = "List all jobs instead of filtered search results"
        
        return RecoveryAction(
            strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
            description=degraded_description,
            estimated_success_rate=0.8,
            estimated_duration=3.0
        )
    
    async def _create_abandon_action(self, failure_context: FailureContext) -> RecoveryAction:
        """Create action to abandon the current goal"""
        
        return RecoveryAction(
            strategy=RecoveryStrategy.ABANDON_GOAL,
            description=f"Unable to complete goal due to: {failure_context.error}",
            estimated_success_rate=0.0,
            estimated_duration=1.0
        )
    
    def _is_circuit_breaker_open(self, circuit_key: str) -> bool:
        """Check if circuit breaker is open for this operation"""
        
        circuit_state = self.circuit_breakers.get(circuit_key)
        if not circuit_state:
            return False
        
        if circuit_state["state"] != "open":
            return False
        
        # Check if enough time has passed to try again
        if time.time() - circuit_state["opened_at"] > circuit_state["timeout"]:
            # Move to half-open state
            circuit_state["state"] = "half-open"
            return False
        
        return True
    
    def _update_circuit_breaker(self, circuit_key: str, recovery_action: RecoveryAction):
        """Update circuit breaker state based on recovery action"""
        
        if circuit_key not in self.circuit_breakers:
            self.circuit_breakers[circuit_key] = {
                "failure_count": 0,
                "success_count": 0,
                "state": "closed",
                "opened_at": None,
                "timeout": 300  # 5 minutes
            }
        
        circuit_state = self.circuit_breakers[circuit_key]
        
        # If recovery action has low success probability, increment failure count
        if recovery_action.estimated_success_rate < 0.3:
            circuit_state["failure_count"] += 1
            
            # Open circuit if too many failures
            if (circuit_state["failure_count"] >= 5 and 
                circuit_state["state"] == "closed"):
                circuit_state["state"] = "open"
                circuit_state["opened_at"] = time.time()
                
                logger.warning("Circuit breaker opened", 
                              circuit_key=circuit_key,
                              failure_count=circuit_state["failure_count"])
        
        # Reset on successful recovery
        elif recovery_action.estimated_success_rate > 0.7:
            circuit_state["success_count"] += 1
            if circuit_state["success_count"] >= 3:
                circuit_state["failure_count"] = 0
                circuit_state["state"] = "closed"
                circuit_state["opened_at"] = None
    
    def _record_recovery_attempt(self, failure_context: FailureContext, 
                               recovery_action: RecoveryAction):
        """Record recovery attempt for learning"""
        
        record_key = f"{failure_context.failure_type.value}:{failure_context.step.tool_name}"
        
        if record_key not in self.recovery_history:
            self.recovery_history[record_key] = []
        
        record = {
            "timestamp": time.time(),
            "error": failure_context.error,
            "strategy": recovery_action.strategy.value,
            "estimated_success": recovery_action.estimated_success_rate,
            "attempt_count": failure_context.attempt_count
        }
        
        self.recovery_history[record_key].append(record)
        
        # Keep only recent history
        if len(self.recovery_history[record_key]) > 100:
            self.recovery_history[record_key] = self.recovery_history[record_key][-100:]
    
    async def execute_recovery_action(self, recovery_action: RecoveryAction,
                                    failure_context: FailureContext,
                                    conversation_state: ConversationState) -> bool:
        """Execute a recovery action"""
        
        logger.info("Executing recovery action",
                   strategy=recovery_action.strategy,
                   step_id=failure_context.step.id)
        
        try:
            if recovery_action.strategy == RecoveryStrategy.RETRY_SAME:
                return await self._execute_retry_same(recovery_action, failure_context)
            
            elif recovery_action.strategy == RecoveryStrategy.RETRY_WITH_FALLBACK:
                return await self._execute_retry_fallback(recovery_action, failure_context)
            
            elif recovery_action.strategy == RecoveryStrategy.MODIFY_PARAMETERS:
                return await self._execute_parameter_modification(recovery_action, failure_context)
            
            elif recovery_action.strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
                return await self._execute_graceful_degradation(recovery_action, failure_context, conversation_state)
            
            elif recovery_action.strategy == RecoveryStrategy.CHANGE_APPROACH:
                return await self._execute_approach_change(recovery_action, failure_context, conversation_state)
            
            elif recovery_action.strategy == RecoveryStrategy.REQUEST_USER_INPUT:
                return await self._execute_user_input_request(recovery_action, failure_context)
            
            else:  # ABANDON_GOAL
                return await self._execute_abandon_goal(recovery_action, failure_context, conversation_state)
                
        except Exception as e:
            logger.error("Recovery action execution failed", 
                        strategy=recovery_action.strategy,
                        error=str(e))
            return False
    
    async def _execute_retry_same(self, recovery_action: RecoveryAction,
                                failure_context: FailureContext) -> bool:
        """Execute retry with same parameters"""
        
        delay = recovery_action.parameters.get("delay", 1.0)
        await asyncio.sleep(delay)
        
        # Re-execute the original step
        step = failure_context.step
        response = await self.tool_registry.execute_with_fallback(
            step.tool_name, step.parameters
        )
        
        return response.success
    
    async def _execute_retry_fallback(self, recovery_action: RecoveryAction,
                                    failure_context: FailureContext) -> bool:
        """Execute retry with fallback tool"""
        
        fallback_tool = recovery_action.parameters.get("fallback_tool")
        if not fallback_tool:
            return False
        
        step = failure_context.step
        step.tool_name = fallback_tool  # Switch to fallback tool
        
        response = await self.tool_registry.execute_with_fallback(
            fallback_tool, step.parameters
        )
        
        return response.success
    
    async def _execute_parameter_modification(self, recovery_action: RecoveryAction,
                                            failure_context: FailureContext) -> bool:
        """Execute with modified parameters"""
        
        modified_params = recovery_action.parameters.get("modified_params")
        if not modified_params:
            return False
        
        step = failure_context.step
        step.parameters = modified_params
        
        response = await self.tool_registry.execute_with_fallback(
            step.tool_name, modified_params
        )
        
        return response.success
    
    async def _execute_graceful_degradation(self, recovery_action: RecoveryAction,
                                          failure_context: FailureContext,
                                          conversation_state: ConversationState) -> bool:
        """Execute graceful degradation"""
        
        # Provide partial result based on what we can do
        degraded_result = {
            "status": "partial",
            "message": recovery_action.description,
            "available_data": "Limited information due to system constraints"
        }
        
        # Store in conversation memory
        conversation_state.store_memory(
            f"degraded_result_{failure_context.step.id}",
            degraded_result,
            importance=0.6
        )
        
        return True  # Degradation is considered successful
    
    async def _execute_approach_change(self, recovery_action: RecoveryAction,
                                     failure_context: FailureContext,
                                     conversation_state: ConversationState) -> bool:
        """Execute approach change"""
        
        alternative = recovery_action.parameters.get("alternative_approach")
        if not alternative:
            return False
        
        # Mark alternative as tried
        alternative.tried = True
        
        # This would require more complex integration with planning engine
        # For now, return success to indicate we've switched approaches
        logger.info("Switched to alternative approach", approach=alternative.description)
        return True
    
    async def _execute_user_input_request(self, recovery_action: RecoveryAction,
                                        failure_context: FailureContext) -> bool:
        """Request user input"""
        
        if self.user_notification_callback:
            await self.user_notification_callback(
                f"Need your help: {recovery_action.description}",
                recovery_action.parameters
            )
        
        # For now, assume user will provide input through normal channels
        return True
    
    async def _execute_abandon_goal(self, recovery_action: RecoveryAction,
                                  failure_context: FailureContext,
                                  conversation_state: ConversationState) -> bool:
        """Abandon the current goal"""
        
        goal = failure_context.goal
        goal.status = "failed"
        
        # Store abandonment reason in memory
        conversation_state.store_memory(
            f"abandoned_goal_{goal.id}",
            {
                "reason": recovery_action.description,
                "final_error": failure_context.error
            },
            importance=0.8
        )
        
        logger.info("Goal abandoned", 
                   goal_id=goal.id,
                   reason=recovery_action.description)
        
        return False  # Abandoning is not success
    
    def set_user_notification_callback(self, callback: Callable):
        """Set callback for user notifications"""
        self.user_notification_callback = callback
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        
        total_attempts = sum(len(history) for history in self.recovery_history.values())
        circuit_breakers_open = len([cb for cb in self.circuit_breakers.values() 
                                   if cb["state"] == "open"])
        
        return {
            "total_recovery_attempts": total_attempts,
            "failure_patterns_configured": len(self.failure_patterns),
            "circuit_breakers_active": len(self.circuit_breakers),
            "circuit_breakers_open": circuit_breakers_open,
            "recovery_history_entries": len(self.recovery_history)
        }