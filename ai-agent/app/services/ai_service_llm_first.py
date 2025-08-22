"""
LLM-First AI Service with Iterative Tool Support
Replaces regex intent detection with intelligent Gemini function calling
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
import structlog
import google.generativeai as genai

from app.config import settings
from app.models import ChatResponse
from app.services.mcp_service import MCPService
from app.services.context_manager import context_manager

logger = structlog.get_logger(__name__)

class AIServiceLLMFirst:
    """LLM-First AI Service with direct tool integration and iterative support"""
    
    def __init__(self):
        # Configure Gemini API with function calling
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Initialize MCP service for tool execution
        self.mcp_service = MCPService()
        
        # Configure model without system_instruction for compatibility
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                max_output_tokens=settings.GEMINI_MAX_TOKENS,
                temperature=settings.GEMINI_TEMPERATURE,
            )
        )
        
        # Discover available tools at startup
        self.available_tools = None
        asyncio.create_task(self._discover_available_tools())
        
        # System prompt will be built after tool discovery
        self.system_prompt = None
    
    async def _discover_available_tools(self) -> None:
        """Discover all available tools from MCP server"""
        try:
            from mcp import ClientSession, types
            from mcp.client.streamable_http import streamablehttp_client
            
            async with streamablehttp_client(f"http://{settings.MCP_HTTP_HOST}:{settings.MCP_HTTP_PORT}{settings.MCP_HTTP_ENDPOINT}") as (
                read_stream, write_stream, _
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Get all available tools
                    tools_response = await session.list_tools()
                    
                    # Parse tool information
                    tools_info = {}
                    for tool in tools_response.tools:
                        tools_info[tool.name] = {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema.get("properties", {}) if tool.inputSchema else {}
                        }
                    
                    self.available_tools = tools_info
                    
                    # Build system prompt now that we have tools
                    self.system_prompt = self._build_dynamic_system_prompt()
                    
                    logger.info("Discovered MCP tools", tool_count=len(tools_info), tools=list(tools_info.keys()))
                    
        except Exception as e:
            logger.error("Failed to discover MCP tools", error=str(e))
            # Fallback to basic system prompt
            self.system_prompt = self._build_fallback_system_prompt()
    
    def _get_tool_descriptions(self) -> str:
        """Get tool descriptions for system prompt (current Gemini version approach)"""
        return """
Available Tools (request them when needed):
- list_jenkins_jobs: Get all available Jenkins jobs
- get_job_info(job_name, include_builds=true): Get job details and build history  
- get_console_log(job_name, build_number): Get console output for specific build
- get_job_status(job_name): Get current job status
- trigger_build(job_name): Start new build (check permissions)

To use tools, simply mention them in your response like: "I need to call get_job_info for JobName"
"""
    
    def _build_dynamic_system_prompt(self) -> str:
        """Build system prompt with all discovered MCP tools"""
        if not self.available_tools:
            return self._build_fallback_system_prompt()
        
        # Generate tool descriptions from discovered tools
        tool_descriptions = []
        for tool_name, tool_info in self.available_tools.items():
            desc = f"- {tool_name}"
            if tool_info.get("description"):
                desc += f": {tool_info['description']}"
            
            # Add parameter info if available
            params = tool_info.get("parameters", {})
            if params:
                param_list = []
                for param_name, param_info in params.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    param_list.append(f"{param_name}({param_type})")
                desc += f" - Parameters: {', '.join(param_list)}"
            
            tool_descriptions.append(desc)
        
        tools_text = "\n".join(tool_descriptions)
        
        return f"""You are a Jenkins assistant with access to real Jenkins data through tools.

Available Tools (use actual tool names):
{tools_text}

MANDATORY TOOL REQUEST FORMAT:
When you need to execute a tool, use EXACTLY this format:
TOOL: tool_name PARAMS: param1=value1,param2=value2

CRITICAL FORMATTING RULES:
- Use "TOOL:" (uppercase) followed by exact tool name
- Use "PARAMS:" (uppercase) for parameters (or PARAMS: none if no parameters)
- Separate multiple parameters with commas
- No backticks, quotes, or other formatting around tool names
- Each tool request must be on its own line

RESPONSE FORMAT:
- Start with "I'll [action] for you"
- Use numbered lists for job listings: 1. **JobName**
- Keep responses concise (<100 words) unless detailed analysis requested
- Show actual Jenkins data when available

EXAMPLES:
- "list jobs" → "I'll list all Jenkins jobs for you." → "TOOL: list_jobs PARAMS: none"
- "job info for X" → "I'll get job information for X." → "TOOL: get_job_info PARAMS: job_name=X"
- "console log for build 5 of job X" → "I'll get the console log." → "TOOL: get_console_log PARAMS: job_name=X,build_number=5"
- "server info" → "I'll get server information." → "TOOL: server_info PARAMS: none"

MULTI-STEP EXAMPLES:
- "build status of JobName" → "I'll get the job info first to find the latest build, then get its status." → "TOOL: get_job_info PARAMS: job_name=JobName" → (wait for result) → "TOOL: get_build_status PARAMS: job_name=JobName,build_number=N"
- "job info for JobName" → "I'll get comprehensive job information including build status." → "TOOL: get_job_info PARAMS: job_name=JobName" → (if result has build_number but no status) → "TOOL: get_build_status PARAMS: job_name=JobName,build_number=N"
- "latest console log for JobName" → "I'll get job info first, then the console log." → "TOOL: get_job_info PARAMS: job_name=JobName" → (wait for result) → "TOOL: get_console_log PARAMS: job_name=JobName,build_number=N"

AUTOMATIC FOLLOW-UP RULES:
- When get_job_info returns last_build_number but last_build_status is null/None, ALWAYS follow up with get_build_status
- When user asks for job info, provide COMPLETE information including actual build status
- Never say "status is unknown" when you can get it with get_build_status

PARAMETER TYPES:
- build_number must be INTEGER (20, not "20")
- get_build_status requires BOTH job_name AND build_number
- get_console_log requires BOTH job_name AND build_number

Always check user permissions before suggesting build/modify actions."""
    
    def _build_fallback_system_prompt(self) -> str:
        """Fallback system prompt when tool discovery fails"""
        return self._build_iterative_system_prompt()
    
    def _build_iterative_system_prompt(self) -> str:
        """Build system prompt for iterative tool usage"""
        return f"""You are a Jenkins assistant with access to real Jenkins data through tools.

{self._get_tool_descriptions()}

MANDATORY TOOL REQUEST FORMAT:
When you need to execute a tool, use EXACTLY this format:
TOOL: tool_name PARAMS: param1=value1,param2=value2

CRITICAL FORMATTING RULES:
- Use "TOOL:" (uppercase) followed by exact tool name
- Use "PARAMS:" (uppercase) for parameters (or PARAMS: none if no parameters)
- Separate multiple parameters with commas
- No backticks, quotes, or other formatting around tool names
- Each tool request must be on its own line

RESPONSE FORMAT:
- Start with "I'll [action] for you"
- Use numbered lists: 1. **JobName**
- Keep responses concise (<100 words)
- Show reasoning for multi-step queries

EXAMPLES:
- "list jobs" → "I'll list all Jenkins jobs for you." → "TOOL: list_jobs PARAMS: none"
- "job info for X" → "I'll get comprehensive job information including build status." → "TOOL: get_job_info PARAMS: job_name=X" → (if result has build_number but no status) → "TOOL: get_build_status PARAMS: job_name=X,build_number=N"
- "latest successful build console for X" → "I'll get job info first, then console log." → "TOOL: get_job_info PARAMS: job_name=X" → analyze → "TOOL: get_console_log PARAMS: job_name=X,build_number=N"

AUTOMATIC FOLLOW-UP RULES:
- When get_job_info returns last_build_number but last_build_status is null/None, ALWAYS follow up with get_build_status
- When user asks for job info, provide COMPLETE information including actual build status
- Never say "status is unknown" when you can get it with get_build_status

Always check user permissions before suggesting build/modify actions."""
    
    def _build_user_context(self, user_context: Dict[str, Any]) -> str:
        """Build context string for the user"""
        context_parts = []
        
        # User information
        context_parts.append(f"User: {user_context['user_id']}")
        
        # User permissions
        if user_context.get('permissions'):
            permissions_str = ", ".join(user_context['permissions'])
            context_parts.append(f"User Permissions: {permissions_str}")
        
        # Jenkins context
        if user_context.get('context'):
            ctx = user_context['context']
            if ctx.get('jenkins_url'):
                context_parts.append(f"Jenkins URL: {ctx['jenkins_url']}")
        
        return "\n".join(context_parts)
    
    async def _get_conversation_context(self, user_context: Dict[str, Any], conversation_service=None) -> str:
        """
        Retrieve and format conversation history for context continuity using enhanced context manager
        """
        if not conversation_service:
            return "No previous conversation history available."
        
        try:
            session_id = user_context.get("session_id")
            if not session_id:
                return "No session context available."
            
            # Get structured context summary from context manager
            context_summary = await context_manager.get_context_summary(session_id)
            
            # Get conversation history from service
            history = await conversation_service.get_conversation_history(session_id, limit=10)
            
            if not history:
                return f"This is the start of our conversation.\\n\\nContext: {context_summary}"
            
            # Format recent conversation with focus on tool results
            formatted_history = []
            
            for msg in history[-6:]:  # Last 6 messages for brevity
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                tool_results = msg.get("tool_results", [])
                
                # Add to formatted history
                if role == "user":
                    formatted_history.append(f"User: {content}")
                elif role == "assistant":
                    formatted_history.append(f"Assistant: {content[:150]}{'...' if len(content) > 150 else ''}")
                    # Include important tool results
                    if tool_results:
                        for result in tool_results[:2]:  # Limit to 2 most recent results
                            if isinstance(result, dict) and result.get('success'):
                                tool_name = result.get('tool', 'unknown')
                                tool_data = str(result.get('data', ''))[:100]
                                formatted_history.append(f"Tool {tool_name}: {tool_data}...")
            
            result = "\\n".join(formatted_history)
            result += f"\\n\\nEnhanced Context: {context_summary}"
            
            return result
            
        except Exception as e:
            logger.error("Failed to retrieve conversation context", error=str(e))
            return "Error retrieving conversation history."
    
    async def process_message(self, message: str, user_context: Dict[str, Any], conversation_service=None) -> ChatResponse:
        """
        Process user message with intelligent tool detection and execution
        Now includes conversation history for context continuity
        """
        start_time = time.time()
        
        try:
            # Extract and update contextual entities from user message
            session_id = user_context.get("session_id")
            if session_id:
                await context_manager.update_context_from_message(message, session_id, "user")
                # Resolve references in the message for better understanding
                resolved_message = await context_manager.resolve_references_in_message(message, session_id)
                if resolved_message != message:
                    logger.info("Message references resolved", original=message[:50], resolved=resolved_message[:50])
                    message = resolved_message
            
            # Build user context
            context = self._build_user_context(user_context)
            
            # Retrieve conversation history for context continuity
            conversation_history = await self._get_conversation_context(user_context, conversation_service)
            
            # Ensure system prompt is ready (wait for tool discovery if needed)
            if self.system_prompt is None:
                # Wait for tool discovery to complete
                max_wait = 10  # 10 seconds max wait
                wait_count = 0
                while self.system_prompt is None and wait_count < max_wait:
                    await asyncio.sleep(1)
                    wait_count += 1
                
                # If still not ready, use fallback
                if self.system_prompt is None:
                    self.system_prompt = self._build_fallback_system_prompt()
            
            # Generate initial response with system prompt + conversation history
            full_prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nConversation History:\n{conversation_history}\n\nUser: {message}"
            response = await asyncio.to_thread(self.model.generate_content, full_prompt)
            
            # Parse response for tool requests and execute iteratively
            iteration = 0
            max_iterations = 5
            conversation_history = [full_prompt, response.text]
            
            while iteration < max_iterations and self._needs_tools(response.text):
                logger.info("Processing tool requests", iteration=iteration, response_text=response.text[:200])
                
                # Extract tool requests from response
                tool_requests = self._extract_tool_requests(response.text)
                
                if not tool_requests:
                    logger.warning("No tool requests extracted despite needs_tools=True", response_text=response.text)
                    break
                
                logger.info("Extracted tool requests", tool_requests=tool_requests)
                
                # Execute requested tools
                tool_results = []
                for tool_request in tool_requests:
                    logger.info("Executing tool request", tool_request=tool_request)
                    result = await self._execute_tool_from_request(tool_request)
                    logger.info("Tool execution result", tool=tool_request["tool"], success=result.get("success"))
                    tool_results.append(result)
                
                # Continue conversation with tool results
                if tool_results:
                    tool_prompt = f"Tool results: {tool_results}\n\nNow provide the final answer to the user based on this data."
                    response = await asyncio.to_thread(self.model.generate_content, 
                                                     "\n".join(conversation_history + [tool_prompt]))
                    conversation_history.append(tool_prompt)
                    conversation_history.append(response.text)
                    iteration += 1
                else:
                    break
            
            # Extract final response
            final_response = self._clean_response(response.text)
            
            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.info("LLM-First message processed",
                       user_id=user_context["user_id"],
                       processing_time_ms=processing_time,
                       iterations_used=iteration,
                       conversation_context_used=len(conversation_history) > 0)
            
            return ChatResponse(
                response=final_response,
                intent_detected="llm_determined",
                response_time_ms=processing_time,
                confidence_score=1.0,
                actions=[],
                tool_results=tool_results if 'tool_results' in locals() else []
            )
            
        except Exception as e:
            logger.error("LLM-First processing failed",
                        error=str(e),
                        user_id=user_context.get("user_id"),
                        message_preview=message[:100])
            
            # Return fallback response
            return ChatResponse(
                response=f"I'm sorry, I encountered an error processing your request: {str(e)}",
                intent_detected="error", 
                response_time_ms=int((time.time() - start_time) * 1000),
                confidence_score=0.1,
                actions=[]
            )
    
    def _needs_tools(self, response_text: str) -> bool:
        """Check if response indicates need for tool execution using standardized format"""
        # Check for the standardized format: "TOOL: tool_name PARAMS:"
        return "TOOL:" in response_text and "PARAMS:" in response_text
    
    def _extract_tool_requests(self, response_text: str) -> List[Dict[str, Any]]:
        """Extract tool requests from AI response using dynamic tool discovery"""
        import re
        
        requests = []
        
        # Use standardized format: "TOOL: tool_name PARAMS: param1=value1,param2=value2"
        pattern = r"TOOL:\s*(\w+)\s+PARAMS:\s*([^\n]+)"
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        
        for match in matches:
            tool_name = match[0].strip()
            params_text = match[1].strip()
            
            # Validate tool exists (if we have discovered tools)
            if self.available_tools and tool_name not in self.available_tools:
                logger.warning(f"Unknown tool requested: {tool_name}")
                continue
            
            # Parse parameters
            parsed_params = self._parse_standardized_parameters(params_text)
            
            requests.append({
                "tool": tool_name,
                "params": parsed_params
            })
        
        return requests
    
    def _parse_standardized_parameters(self, params_text: str) -> Dict[str, Any]:
        """Parse parameters from standardized format: param1=value1,param2=value2"""
        params = {}
        
        # Handle "none" case
        if params_text.lower() == "none":
            return params
        
        # Parse comma-separated key=value pairs
        param_pairs = params_text.split(',')
        for pair in param_pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)  # Split on first = only
                key = key.strip()
                value = value.strip()
                
                # Convert numeric values to integers for MCP compatibility
                if key in ['build_number', 'max_depth', 'limit'] and value.isdigit():
                    params[key] = int(value)
                # Convert boolean values
                elif value.lower() in ['true', 'false']:
                    params[key] = value.lower() == 'true'
                else:
                    params[key] = value
        
        return params
    
    def _parse_tool_parameters(self, tool_name: str, params_text: str) -> Dict[str, Any]:
        """Parse parameters from LLM response text"""
        import re
        
        params = {}
        
        if not params_text:
            return params
        
        # Common parameter patterns
        patterns = {
            "job_name": r"(?:job_name|job|for)\s*[=:]\s*([^\s,]+)",
            "build_number": r"(?:build_number|build|#)\s*[=:]\s*(\d+)",
            "pattern": r"(?:pattern|search)\s*[=:]\s*([^\s,]+)",
            "recursive": r"(?:recursive)\s*[=:]\s*(true|false)",
            "max_depth": r"(?:max_depth|depth)\s*[=:]\s*(\d+)"
        }
        
        # Try to extract structured parameters
        for param_name, pattern in patterns.items():
            match = re.search(pattern, params_text, re.IGNORECASE)
            if match:
                value = match.group(1)
                # Convert to appropriate type
                if param_name in ["build_number", "max_depth"]:
                    params[param_name] = int(value)
                elif param_name == "recursive":
                    params[param_name] = value.lower() == "true"
                else:
                    params[param_name] = value
        
        # If no structured params found, treat as simple text for job_name
        if not params and params_text.strip():
            # Extract potential job name from natural language
            job_name = self._extract_job_name(params_text)
            if job_name:
                params["job_name"] = job_name
        
        return params
    
    def _clean_response(self, response_text: str) -> str:
        """Remove tool requests from final response"""
        lines = response_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip lines that contain tool requests
            if not any(phrase in line for phrase in ["I need to call", "I need list_jenkins_jobs", "I need get_"]):
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    async def _execute_tool_from_request(self, tool_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute any MCP tool from parsed request"""
        tool_name = tool_request["tool"]
        params = tool_request["params"]
        
        logger.info("Executing tool from request", tool=tool_name, params=params)
        
        try:
            # Use universal tool executor
            result = await self._execute_any_mcp_tool(tool_name, params)
            
            return {
                "success": True,
                "tool": tool_name,
                "data": result,
                "message": f"Successfully executed {tool_name}"
            }
            
        except Exception as e:
            logger.warning("Tool execution failed", tool=tool_name, error=str(e))
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e),
                "message": f"Tool {tool_name} failed: {str(e)}"
            }
    
    async def _execute_any_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute any of the available MCP tools dynamically"""
        logger.info("Executing MCP tool", tool=tool_name, params=params)
        
        try:
            from mcp import ClientSession, types
            from mcp.client.streamable_http import streamablehttp_client
            
            async with streamablehttp_client(f"http://{settings.MCP_HTTP_HOST}:{settings.MCP_HTTP_PORT}{settings.MCP_HTTP_ENDPOINT}") as (
                read_stream, write_stream, _
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Call the tool with provided parameters
                    response = await session.call_tool(tool_name, arguments=params)
                    
                    if response.isError:
                        raise ValueError(f"MCP tool {tool_name} failed: {response.content}")
                    
                    # Extract content using the established pattern
                    for content in response.content:
                        if isinstance(content, types.TextContent):
                            try:
                                import json
                                # Try to parse as JSON first
                                return json.loads(content.text)
                            except json.JSONDecodeError:
                                # Return as text if not valid JSON
                                return {"response": content.text}
                    
                    return {"error": "No valid content in response"}
                    
        except Exception as e:
            logger.error("MCP tool execution failed", tool=tool_name, error=str(e))
            return {
                "error": str(e),
                "tool": tool_name,
                "success": False
            }
    
    def _extract_job_name(self, text: str) -> Optional[str]:
        """Extract job name from text"""
        # Simple extraction - look for job-like names
        import re
        
        # Remove common words
        text = re.sub(r'\b(job|build|for|with|of|the|a|an)\b', '', text, flags=re.IGNORECASE)
        text = text.strip()
        
        # Return the cleaned text if it looks like a job name
        if text and len(text) > 0:
            return text
        return None
    
    def _extract_job_and_build(self, text: str) -> tuple[Optional[str], Optional[int]]:
        """Extract job name and build number from text"""
        import re
        
        # Look for patterns like "JobName build 123" or "JobName #123"
        pattern = r'(\S+).*?(?:build|#)\s*(\d+)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            return match.group(1), int(match.group(2))
        
        # Fallback - just try to extract job name
        job_name = self._extract_job_name(text)
        return job_name, None
    
    async def health_check(self) -> bool:
        """Check if LLM-First service is healthy"""
        try:
            # Simple test call to Gemini API
            response = await asyncio.to_thread(
                self.model.generate_content,
                "Health check"
            )
            gemini_healthy = len(response.text) > 0
            
            # Check MCP server health
            mcp_healthy = await self.mcp_service.health_check()
            
            logger.info("LLM-First health check completed",
                       gemini_healthy=gemini_healthy,
                       mcp_healthy=mcp_healthy)
            
            return gemini_healthy and mcp_healthy
            
        except Exception as e:
            logger.error("LLM-First health check failed", error=str(e))
            return False