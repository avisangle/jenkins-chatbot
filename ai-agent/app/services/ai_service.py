"""
AI Service for processing chat messages using Google Gemini API
Handles natural language understanding and response generation
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
import structlog
import google.generativeai as genai
import httpx

from app.config import settings
from app.models import ChatResponse, Action
from app.services.mcp_service import MCPService
from app.services.jenkins_service import JenkinsService

logger = structlog.get_logger(__name__)

class AIService:
    """Service for AI-powered chat processing using Google Gemini"""
    
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                max_output_tokens=settings.GEMINI_MAX_TOKENS,
                temperature=settings.GEMINI_TEMPERATURE,
            )
        )
        self.mcp_service = MCPService()
        self.jenkins_service = JenkinsService()
        
        # Legacy service - now serves as simple fallback only
        # Most functionality has moved to LLM-First architecture
        # Note: This service is deprecated in favor of AIServiceLLMFirst
    
    async def process_message(self, message: str, user_context: Dict[str, Any]) -> ChatResponse:
        """
        Legacy fallback service - simplified implementation
        
        DEPRECATED: This service is now a simple fallback. The LLM-First architecture 
        (AIServiceLLMFirst) provides full functionality with access to all 21 MCP tools 
        and intelligent tool selection. Enable USE_LLM_FIRST_ARCHITECTURE=true for 
        optimal performance.
        """
        start_time = time.time()
        
        logger.warning(
            "Using deprecated legacy AI service",
            user_id=user_context.get("user_id"),
            recommendation="Enable LLM-First architecture for full functionality"
        )
        
        try:
            # Simple fallback response recommending LLM-First
            base_response = (
                "I can help with basic Jenkins tasks. For full functionality including "
                "access to all 21 Jenkins tools and intelligent responses, please enable "
                "the LLM-First architecture."
            )
            
            # Try to provide some basic functionality via MCP if available
            if settings.MCP_ENABLED:
                try:
                    mcp_recommendations = await asyncio.wait_for(
                        self.mcp_service.get_jenkins_recommendations(user_context, message),
                        timeout=2.0
                    )
                    
                    if mcp_recommendations:
                        response = "Here are some available Jenkins jobs:\n"
                        for i, rec in enumerate(mcp_recommendations[:5], 1):  # Limit to 5
                            job_name = rec.get('job_name', 'Unknown')
                            status = rec.get('last_build_status', 'unknown')
                            response += f"{i}. **{job_name}** - {status}\n"
                        response += "\nFor more advanced operations, enable LLM-First architecture."
                    else:
                        response = base_response
                        
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning("MCP service unavailable in legacy mode", error=str(e))
                    response = base_response + " (MCP service unavailable)"
            else:
                response = base_response + " (MCP disabled)"
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return ChatResponse(
                response=response,
                intent_detected="legacy_fallback",
                response_time_ms=processing_time,
                confidence_score=0.2,  # Low confidence indicates legacy fallback
                actions=[]  # No actions in legacy mode
            )
            
        except Exception as e:
            logger.error("Legacy AI service failed", error=str(e))
            
            return ChatResponse(
                response="I'm experiencing issues. Please try enabling the LLM-First architecture or contact support.",
                intent_detected="error",
                response_time_ms=int((time.time() - start_time) * 1000),
                confidence_score=0.1,
                actions=[]
            )
    
    def _detect_intent(self, message: str) -> tuple[str, float]:
        """
        DEPRECATED: Legacy intent detection - regex patterns replaced by LLM intelligence
        
        This method is maintained for backward compatibility only. The LLM-First 
        architecture uses intelligent natural language understanding instead of 
        brittle regex patterns.
        """
        # Simplified legacy detection - just return basic intent
        return "legacy_request", 0.2
    
    async def _build_ai_context(self, user_context: Dict[str, Any], mcp_recommendations: Optional[List[Dict[str, Any]]] = None) -> str:
        """Build context string for AI prompt"""
        context_parts = []
        
        # User information
        context_parts.append(f"User: {user_context['user_id']}")
        
        # User permissions
        if user_context.get('permissions'):
            permissions_str = ", ".join(user_context['permissions'])
            context_parts.append(f"User Permissions: {permissions_str}")
        
        # Current context from request
        if user_context.get('context'):
            ctx = user_context['context']
            if ctx.get('current_job'):
                context_parts.append(f"Current Job: {ctx['current_job']}")
            if ctx.get('last_build_status'):
                context_parts.append(f"Last Build Status: {ctx['last_build_status']}")
            if ctx.get('workspace'):
                context_parts.append(f"Workspace: {ctx['workspace']}")
            if ctx.get('jenkins_url'):
                context_parts.append(f"Jenkins URL: {ctx['jenkins_url']}")
        
        # Add MCP recommendations if available
        if mcp_recommendations:
            context_parts.append("MCP Server Recommendations:")
            for rec in mcp_recommendations[:5]:  # Limit to 5 recommendations
                if rec.get('suggestion'):
                    context_parts.append(f"- {rec['suggestion']}")
                if rec.get('related_jobs'):
                    jobs_str = ", ".join(rec['related_jobs'][:3])  # Limit to 3 jobs
                    context_parts.append(f"  Related Jobs: {jobs_str}")
        
        # Note: Jenkins job information will be provided by MCP server in enhancement step
        # Following MCP architecture: AI Agent → MCP Server → Jenkins API
        # No direct Jenkins API calls from AI Agent
        
        return "\n".join(context_parts)
    
    async def _generate_response(self, message: str, context: str, intent: str) -> str:
        """Generate AI response using Google Gemini"""
        
        # Build system prompt
        system_prompt = self._build_system_prompt(intent)
        
        # Build full prompt with context
        full_prompt = f"""{system_prompt}

Context:
{context}

User Message: {message}

Please provide a helpful response. If the user is asking to perform an action (like triggering a build), explain what you would do and mention any permissions or requirements."""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt
            )
            
            return response.text
            
        except Exception as e:
            logger.error("Gemini API error", error=str(e))
            raise
    
    def _build_system_prompt(self, intent: str) -> str:
        """Build system prompt based on detected intent"""
        
        base_prompt = """You are a Jenkins assistant. Be concise and direct.

Response Guidelines:
- Lead with action: "I'll [action] for you"
- Show actual data when available, not explanations
- Use numbered lists for job listings
- Keep responses under 100 words
- End with one helpful follow-up question
- Always check user permissions before suggesting actions
- Use natural language that's easy to understand
- Focus on the user's immediate needs"""

        intent_specific = {
            "build_trigger": "\nFocus: Help the user trigger builds or deployments. Check they have Job.BUILD permission.",
            "status_query": "\nFocus: Provide clear status information about builds, jobs, or systems.",
            "log_access": "\nFocus: Help access and interpret build logs and console output.",
            "list_jobs": "\nFor job listings: Start with 'I'll list all the Jenkins jobs for you.' then show numbered list using actual job names from the data: 1. **C2M-DEMO-JENKINS** format.",
            "help_request": "\nFocus: Provide helpful guidance and examples for Jenkins tasks."
        }
        
        return base_prompt + intent_specific.get(intent, "")
    
    async def _parse_actions(self, ai_response: str, user_context: Dict[str, Any]) -> Optional[List[Action]]:
        """Parse AI response for actionable items"""
        actions = []
        
        # Simple action parsing - in production this would be more sophisticated
        response_lower = ai_response.lower()
        
        # Check for build triggers (updated to match new intent names)
        if any(word in response_lower for word in ["trigger", "start", "build", "run"]):
            # Try to extract job name from context or response
            job_name = self._extract_job_name(ai_response, user_context)
            if job_name:
                actions.append(Action(
                    type="jenkins_api_call",
                    endpoint=f"/job/{job_name}/build",
                    method="POST",
                    requires_permission="Job.BUILD",
                    parameters={"job_name": job_name}
                ))
        
        # Check for status queries
        if any(word in response_lower for word in ["status", "check", "state"]):
            job_name = self._extract_job_name(ai_response, user_context)
            if job_name:
                actions.append(Action(
                    type="jenkins_api_call",
                    endpoint=f"/job/{job_name}/api/json",
                    method="GET",
                    requires_permission="Job.READ",
                    parameters={"job_name": job_name}
                ))
        
        # Check for log access
        if any(word in response_lower for word in ["log", "console", "output"]):
            build_info = self._extract_build_info(ai_response, user_context)
            if build_info:
                job_name, build_number = build_info
                actions.append(Action(
                    type="jenkins_api_call",
                    endpoint=f"/job/{job_name}/{build_number}/consoleText",
                    method="GET",
                    requires_permission="Job.READ",
                    parameters={"job_name": job_name, "build_number": build_number}
                ))
        
        return actions if actions else None
    
    def _extract_job_name(self, text: str, user_context: Dict[str, Any]) -> Optional[str]:
        """Extract job name from text and context"""
        import re
        
        # Check if there's a current job in context
        if user_context.get('context', {}).get('current_job'):
            return user_context['context']['current_job']
        
        # Check for jobs in user's accessible jobs if available
        if 'accessible_jobs' in user_context:
            text_lower = text.lower()
            for job in user_context['accessible_jobs']:
                if job.lower() in text_lower:
                    return job
        
        # Enhanced pattern matching for job names
        job_patterns = [
            r"job\s+['\"]?([^'\"\s]+)['\"]?",
            r"build\s+['\"]?([^'\"\s]+)['\"]?",
            r"project\s+['\"]?([^'\"\s]+)['\"]?",
            r"['\"]([^'\"]+)['\"]",
            r"(\w+[-_]\w+)"  # hyphenated or underscored names
        ]
        
        for pattern in job_patterns:
            matches = re.findall(pattern, text)
            if matches:
                job_name = matches[0].strip()
                # Filter out common non-job words
                if job_name.lower() not in ['the', 'a', 'an', 'this', 'that', 'my', 'our', 'new', 'old']:
                    return job_name
        
        return None
    
    def _extract_build_number(self, text: str) -> Optional[int]:
        """Extract build number from text"""
        import re
        
        build_patterns = [
            r"build\s+#?(\d+)",
            r"#(\d+)",
            r"number\s+(\d+)",
            r"build\s*#\s*(\d+)"
        ]
        
        for pattern in build_patterns:
            matches = re.findall(pattern, text.lower())
            if matches:
                try:
                    return int(matches[0])
                except ValueError:
                    continue
        
        return None
    
    def _extract_build_info(self, text: str, user_context: Dict[str, Any]) -> Optional[tuple]:
        """Extract job name and build number from text"""
        build_number = self._extract_build_number(text)
        if build_number:
            job_name = self._extract_job_name(text, user_context)
            if job_name:
                return (job_name, build_number)
        
        return None
    
    def _calculate_confidence(self, intent: str, actions: Optional[List[Action]]) -> float:
        """Calculate confidence score for the response"""
        base_score = 0.5  # Lower base confidence since we now use regex confidence
        
        # Boost confidence for recognized intents
        if intent != "general_query":
            base_score += 0.2
        
        # Boost confidence if we have actionable items
        if actions:
            base_score += 0.2
        
        return min(base_score, 1.0)
    
    def _get_fallback_response(self, message: str) -> str:
        """Generate fallback response when AI service fails"""
        
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["build", "trigger", "start"]):
            return ("I'd like to help you trigger a build, but I'm having trouble connecting to my AI brain right now. "
                   "You can manually trigger builds by going to your job page and clicking 'Build Now'.")
        
        elif any(word in message_lower for word in ["status", "check", "how"]):
            return ("I'd help you check the status, but I'm experiencing technical difficulties. "
                   "You can check build status by visiting your job page and looking at the recent builds.")
        
        elif any(word in message_lower for word in ["log", "console", "error"]):
            return ("I'd show you the logs, but I'm having connectivity issues. "
                   "You can access build logs by clicking on a build number and selecting 'Console Output'.")
        
        else:
            return ("I'm sorry, I'm having trouble processing your request right now. "
                   "Please try again later or use the Jenkins UI directly.")
    
    async def health_check(self) -> bool:
        """Check if AI service is healthy"""
        try:
            # Simple test call to Gemini API
            response = await asyncio.to_thread(
                self.model.generate_content,
                "Health check"
            )
            gemini_healthy = len(response.text) > 0
            
            # Check MCP server health (optional)
            mcp_healthy = True
            try:
                mcp_healthy = await asyncio.wait_for(
                    self.mcp_service.health_check(),
                    timeout=3.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("MCP health check failed, continuing without MCP", error=str(e))
                mcp_healthy = False
            
            # Service is healthy if Gemini is working (MCP is optional)
            logger.info("Health check completed", 
                       gemini_healthy=gemini_healthy, 
                       mcp_healthy=mcp_healthy)
            return gemini_healthy
            
        except Exception as e:
            logger.error("AI service health check failed", error=str(e))
            return False