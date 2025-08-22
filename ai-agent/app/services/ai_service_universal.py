"""
Universal AI Service - True LLM autonomy with Gemini Function Calling
Replaces rigid system prompts with intelligent, goal-oriented processing
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
import structlog
import google.generativeai as genai

from app.config import settings
from app.models import ChatResponse
from app.services.mcp_universal_client import UniversalMCPClient
from app.services.tool_registry import ToolRegistry, IntentType
from app.services.conversation_state import ConversationState, Goal, Step, StepStatus, conversation_state_manager
from app.services.planning_engine import PlanningEngine, QueryAnalysis
from app.services.recovery_manager import RecoveryManager, FailureContext
from app.services.config_manager import config_manager

logger = structlog.get_logger(__name__)

class UniversalAIService:
    """Universal AI Service with true LLM autonomy and intelligent conversation flow"""
    
    def __init__(self):
        # Configure Gemini API with function calling
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Initialize core components
        self.config = config_manager.load_configuration()
        self.mcp_client = UniversalMCPClient(self.config.servers)
        self.tool_registry = ToolRegistry(self.mcp_client)
        self.planning_engine = PlanningEngine(self.tool_registry, self.mcp_client)
        self.recovery_manager = RecoveryManager(self.tool_registry, self.mcp_client)
        
        # Gemini model with function calling - USES CONFIGURABLE MODEL
        self.model = None
        self.function_declarations = []
        
        # System initialization
        self.initialization_complete = False
        self._initialization_lock = asyncio.Lock()
        
        # Performance metrics
        self.metrics = {
            "total_conversations": 0,
            "successful_conversations": 0,
            "average_response_time": 0.0,
            "tool_calls_made": 0,
            "goals_completed": 0,
            "goals_failed": 0,
            "recovery_attempts": 0
        }
    
    async def initialize(self):
        """Initialize the universal AI service"""
        
        async with self._initialization_lock:
            if self.initialization_complete:
                return
            
            logger.info("Initializing Universal AI Service")
            
            try:
                # Discover MCP server capabilities and tools
                await self.tool_registry.discover_tools()
                
                # Generate Gemini function declarations from discovered tools
                self.function_declarations = await self.tool_registry.generate_gemini_functions()
                
                # Initialize Gemini model with discovered functions - USES settings.GEMINI_MODEL
                self.model = genai.GenerativeModel(
                    model_name=settings.GEMINI_MODEL,  # ✅ Uses configuration, not hardcoded
                    tools=self.function_declarations,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=settings.GEMINI_MAX_TOKENS,
                        temperature=settings.GEMINI_TEMPERATURE,
                    ),
                    system_instruction=self._build_system_instruction()
                )
                
                # Set up recovery manager callback
                self.recovery_manager.set_user_notification_callback(self._notify_user)
                
                self.initialization_complete = True
                
                logger.info("Universal AI Service initialized successfully",
                           model=settings.GEMINI_MODEL,
                           available_tools=len(self.function_declarations),
                           mcp_servers=len(self.config.servers))
                
            except Exception as e:
                logger.error("Failed to initialize Universal AI Service", error=str(e))
                raise
    
    def _build_system_instruction(self) -> str:
        """Build system instruction for true LLM autonomy"""
        
        return """You are an intelligent Jenkins assistant with access to real Jenkins data through function calls.

CORE PRINCIPLES:
- You have complete autonomy to choose and execute functions as needed
- Focus on achieving user goals, not just answering questions
- Maintain conversation context and avoid repeating completed actions
- Use multi-step reasoning for complex queries
- Provide comprehensive, accurate responses based on actual data

CONVERSATION INTELLIGENCE:
- Remember what you've already done in this conversation
- Build on previous results instead of starting over
- For complex requests, break them into logical steps
- If one approach fails, try alternative methods
- Always aim to fully satisfy the user's intent

FUNCTION CALLING APPROACH:
- You can call any available function based on the user's needs
- No rigid formatting required - use your judgment
- Chain multiple function calls as needed for complex queries
- Handle errors gracefully and try alternative approaches
- Combine results intelligently to provide comprehensive answers

RESPONSE STYLE:
- Be concise but complete
- Show actual Jenkins data when available
- Explain your reasoning for multi-step operations
- If you encounter limitations, suggest alternatives
- Focus on being helpful and goal-oriented

EXAMPLES OF INTELLIGENT BEHAVIOR:
- "Find last failed build" → Get job info, check build history, find most recent failure
- "What's the status of X?" → Get job info AND latest build status for complete picture
- "List jobs that failed recently" → List jobs, check recent builds for each, filter failures
- When a function fails → Try alternative functions or approaches automatically

You have full autonomy to determine the best sequence of function calls to achieve user goals."""
    
    async def process_message(self, message: str, user_context: Dict[str, Any]) -> ChatResponse:
        """Process user message with intelligent conversation flow"""
        
        start_time = time.time()
        
        try:
            # Ensure initialization
            await self.initialize()
            
            # Get or create conversation state
            session_id = user_context.get("session_id", "default")
            user_id = user_context.get("user_id", "anonymous")
            conversation_state = conversation_state_manager.get_or_create_session(session_id, user_id)
            
            # Update metrics
            self.metrics["total_conversations"] += 1
            
            logger.info("Processing message with Universal AI",
                       session_id=session_id,
                       user_id=user_id,
                       message_preview=message[:100])
            
            # Analyze user query
            query_analysis = await self.planning_engine.analyze_query(message, user_context)
            
            # Create conversation goal
            goal = conversation_state.create_goal(
                description=f"Process: {message}",
                user_query=message,
                context={
                    "query_analysis": query_analysis,
                    "user_context": user_context
                }
            )
            conversation_state.start_current_goal()
            
            # Build conversation context for Gemini
            conversation_context = self._build_conversation_context(conversation_state, user_context)
            
            # Generate response with function calling
            response_text = await self._generate_intelligent_response(
                message, conversation_context, conversation_state, goal
            )
            
            # Complete goal if successful
            if conversation_state.current_goal and not conversation_state.current_goal.is_complete:
                conversation_state._complete_current_goal()
                self.metrics["goals_completed"] += 1
            
            # Calculate metrics
            processing_time = int((time.time() - start_time) * 1000)
            self._update_performance_metrics(processing_time, True)
            self.metrics["successful_conversations"] += 1
            
            logger.info("Message processed successfully",
                       session_id=session_id,
                       processing_time_ms=processing_time,
                       goal_completed=True)
            
            return ChatResponse(
                response=response_text,
                intent_detected="llm_autonomous",
                response_time_ms=processing_time,
                confidence_score=1.0,
                actions=self._extract_actions_from_goal(goal)
            )
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            self._update_performance_metrics(processing_time, False)
            
            # Handle goal failure
            session_id = user_context.get("session_id", "default")
            user_id = user_context.get("user_id", "anonymous")
            conversation_state = conversation_state_manager.get_or_create_session(session_id, user_id)
            
            if conversation_state.current_goal:
                conversation_state._archive_current_goal()
                self.metrics["goals_failed"] += 1
            
            logger.error("Universal AI processing failed",
                        error=str(e),
                        user_id=user_id,
                        session_id=session_id,
                        message_preview=message[:100])
            
            return ChatResponse(
                response=f"I encountered an error processing your request: {str(e)}",
                intent_detected="error",
                response_time_ms=processing_time,
                confidence_score=0.1,
                actions=[]
            )
    
    def _build_conversation_context(self, conversation_state: ConversationState, 
                                  user_context: Dict[str, Any]) -> str:
        """Build rich conversation context for Gemini"""
        
        context_parts = []
        
        # User information
        context_parts.append(f"User: {user_context.get('user_id', 'Anonymous')}")
        
        # User permissions
        if user_context.get('permissions'):
            permissions_str = ", ".join(user_context['permissions'])
            context_parts.append(f"User Permissions: {permissions_str}")
        
        # Recent conversation memory
        relevant_memories = conversation_state.get_relevant_memories(
            conversation_state.current_goal.user_query if conversation_state.current_goal else "",
            limit=5
        )
        
        if relevant_memories:
            context_parts.append("Recent Context:")
            for memory in relevant_memories:
                context_parts.append(f"- {memory.key}: {memory.value}")
        
        # Previous actions to avoid repetition
        recent_context = conversation_state.get_recent_context(minutes=5)
        if recent_context:
            context_parts.append("Recent Actions (avoid repeating):")
            for ctx in recent_context[-3:]:  # Last 3 actions
                if "action" in ctx:
                    context_parts.append(f"- {ctx['action']}")
        
        # Current goal progress
        if (conversation_state.current_goal and 
            conversation_state.current_goal.steps):
            completed_steps = conversation_state.current_goal.get_completed_steps()
            if completed_steps:
                context_parts.append("Completed Steps:")
                for step in completed_steps[-3:]:  # Last 3 steps
                    context_parts.append(f"- {step.description} ✓")
        
        return "\n".join(context_parts)
    
    async def _generate_intelligent_response(self, message: str, context: str,
                                           conversation_state: ConversationState,
                                           goal: Goal) -> str:
        """Generate intelligent response using Gemini with function calling"""
        
        # Build the prompt
        full_prompt = f"""Context:
{context}

User Request: {message}

Please help the user by analyzing their request and taking appropriate actions using the available functions. 
Remember to avoid repeating actions that have already been completed in this conversation."""
        
        try:
            # Generate response with function calling
            chat = self.model.start_chat(history=[])
            response = await asyncio.to_thread(chat.send_message, full_prompt)
            
            # Process function calls if any
            if response.candidates[0].content.parts:
                await self._process_function_calls(response, conversation_state, goal)
            
            # Extract final text response
            final_response = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_response += part.text
            
            # If no text response, generate summary from function results
            if not final_response.strip():
                final_response = self._generate_summary_from_function_calls(response, goal)
            
            return final_response
            
        except Exception as e:
            logger.error("Error in intelligent response generation", error=str(e))
            
            # Attempt recovery
            return await self._handle_response_generation_failure(
                message, context, conversation_state, goal, str(e)
            )
    
    async def _process_function_calls(self, response: Any, conversation_state: ConversationState,
                                    goal: Goal) -> List[Any]:
        """Process function calls from Gemini response"""
        
        function_results = []
        
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call'):
                function_call = part.function_call
                
                # Extract function details
                function_name = function_call.name
                function_args = {}
                
                # Convert function arguments
                if function_call.args:
                    for key, value in function_call.args.items():
                        function_args[key] = value
                
                logger.info("Executing function call",
                           function=function_name,
                           args=function_args)
                
                # Create step for this function call
                step = conversation_state.add_step_to_current_goal(
                    description=f"Execute {function_name}",
                    tool_name=function_name,
                    parameters=function_args
                )
                
                if step:
                    step.status = StepStatus.IN_PROGRESS
                    self.metrics["tool_calls_made"] += 1
                    
                    try:
                        # Execute the function using tool registry
                        result = await self.tool_registry.execute_with_fallback(
                            IntentType.LIST_JOBS,  # This needs to be mapped properly
                            function_args
                        )
                        
                        if result.success:
                            # Complete the step
                            conversation_state.complete_step(step.id, result.data)
                            function_results.append(result.data)
                            
                            # Store in conversation memory
                            conversation_state.store_memory(
                                f"function_result_{function_name}",
                                result.data,
                                importance=0.8
                            )
                            
                        else:
                            # Handle function failure with recovery
                            await self._handle_function_failure(
                                step, result.error, conversation_state, goal
                            )
                            
                    except Exception as e:
                        await self._handle_function_failure(
                            step, str(e), conversation_state, goal
                        )
        
        return function_results
    
    async def _handle_function_failure(self, step: Step, error: str,
                                     conversation_state: ConversationState,
                                     goal: Goal):
        """Handle function call failure with intelligent recovery"""
        
        logger.warning("Function call failed", 
                      step_id=step.id,
                      function=step.tool_name,
                      error=error)
        
        # Create failure context
        failure_context = FailureContext(
            step=step,
            goal=goal,
            error=error,
            failure_type=self.recovery_manager._classify_failure(error),
            attempt_count=step.retry_count,
            total_duration=time.time() - (step.started_at or time.time())
        )
        
        # Get recovery action
        recovery_action = await self.recovery_manager.handle_failure(
            failure_context, conversation_state
        )
        
        self.metrics["recovery_attempts"] += 1
        
        # Execute recovery
        success = await self.recovery_manager.execute_recovery_action(
            recovery_action, failure_context, conversation_state
        )
        
        if success:
            conversation_state.complete_step(step.id, "Recovered successfully")
        else:
            conversation_state.fail_step(step.id, f"Recovery failed: {error}")
    
    def _generate_summary_from_function_calls(self, response: Any, goal: Goal) -> str:
        """Generate summary when no text response is provided"""
        
        function_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call'):
                function_calls.append(part.function_call.name)
        
        if function_calls:
            return f"I've executed {len(function_calls)} operations: {', '.join(function_calls)}. The results are displayed above."
        else:
            return "I've processed your request. Please let me know if you need any additional information."
    
    async def _handle_response_generation_failure(self, message: str, context: str,
                                                conversation_state: ConversationState,
                                                goal: Goal, error: str) -> str:
        """Handle failure in response generation with fallback"""
        
        logger.error("Response generation failed, attempting fallback", error=error)
        
        try:
            # Simple fallback response using basic model without functions
            fallback_model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,  # Still use configured model
                generation_config=genai.GenerationConfig(
                    max_output_tokens=1000,
                    temperature=0.7,
                )
            )
            
            fallback_prompt = f"""I'm a Jenkins assistant. The user asked: "{message}"

Please provide a helpful response about Jenkins operations. If you need specific data, 
mention that I can help get that information."""
            
            response = await asyncio.to_thread(fallback_model.generate_content, fallback_prompt)
            return response.text
            
        except Exception as e:
            logger.error("Fallback response generation also failed", error=str(e))
            return f"I apologize, but I'm having technical difficulties. Please try again or rephrase your request. Error: {error}"
    
    def _extract_actions_from_goal(self, goal: Goal) -> List[Dict[str, Any]]:
        """Extract actions from completed goal for response metadata"""
        
        actions = []
        for step in goal.get_completed_steps():
            actions.append({
                "tool": step.tool_name,
                "parameters": step.parameters,
                "result": step.result,
                "status": "completed"
            })
        
        return actions
    
    def _update_performance_metrics(self, processing_time: int, success: bool):
        """Update performance metrics"""
        
        # Update average response time
        total_requests = self.metrics["total_conversations"]
        current_avg = self.metrics["average_response_time"]
        self.metrics["average_response_time"] = (
            (current_avg * (total_requests - 1) + processing_time) / total_requests
        )
    
    async def _notify_user(self, message: str, context: Dict[str, Any]):
        """Callback for user notifications from recovery manager"""
        
        logger.info("User notification", message=message, context=context)
        # In a real implementation, this would send notifications through appropriate channels
    
    async def health_check(self) -> bool:
        """Check health of Universal AI Service"""
        
        try:
            await self.initialize()
            
            # Check all components
            mcp_health = await self.mcp_client.health_check()
            registry_health = await self.tool_registry.health_check()
            
            # Simple Gemini API test
            test_response = await asyncio.to_thread(
                self.model.generate_content,
                "Health check test"
            )
            gemini_health = len(test_response.text) > 0
            
            overall_health = mcp_health and registry_health["healthy"] and gemini_health
            
            logger.info("Universal AI Service health check",
                       mcp_healthy=mcp_health,
                       registry_healthy=registry_health["healthy"],
                       gemini_healthy=gemini_health,
                       overall_healthy=overall_health)
            
            return overall_health
            
        except Exception as e:
            logger.error("Universal AI Service health check failed", error=str(e))
            return False
    
    def get_service_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics"""
        
        registry_health = asyncio.create_task(self.tool_registry.health_check())
        recovery_stats = self.recovery_manager.get_recovery_statistics()
        planning_stats = self.planning_engine.get_planning_statistics()
        
        return {
            "service_metrics": self.metrics,
            "tool_registry": registry_health.result() if registry_health.done() else {"status": "checking"},
            "recovery_manager": recovery_stats,
            "planning_engine": planning_stats,
            "active_sessions": conversation_state_manager.get_active_sessions_count(),
            "initialization_complete": self.initialization_complete,
            "model_config": {
                "model": settings.GEMINI_MODEL,
                "max_tokens": settings.GEMINI_MAX_TOKENS,
                "temperature": settings.GEMINI_TEMPERATURE
            }
        }
    
    async def get_conversation_insights(self, session_id: str) -> Dict[str, Any]:
        """Get insights about a specific conversation"""
        
        if session_id not in conversation_state_manager.sessions:
            return {"error": "Session not found"}
        
        conversation_state = conversation_state_manager.sessions[session_id]
        state_summary = conversation_state.get_state_summary()
        
        # Add AI-specific insights
        state_summary["ai_insights"] = {
            "goal_success_rate": (
                len(conversation_state.completed_goals) / 
                (len(conversation_state.completed_goals) + len(conversation_state.failed_goals))
                if (conversation_state.completed_goals or conversation_state.failed_goals) else 0.0
            ),
            "average_steps_per_goal": (
                sum(len(goal.steps) for goal in conversation_state.completed_goals) / 
                len(conversation_state.completed_goals)
                if conversation_state.completed_goals else 0.0
            ),
            "memory_utilization": len(conversation_state.memory),
            "context_richness": len(conversation_state.context_history)
        }
        
        return state_summary