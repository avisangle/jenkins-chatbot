"""
Intelligent Planning Engine - Complex query decomposition and execution strategy
Handles multi-step queries like "find last failed build" by breaking them into executable steps
"""

import re
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import structlog

from app.services.conversation_state import Goal, Step, Approach, StepStatus
from app.services.tool_registry import ToolRegistry, IntentType
from app.services.mcp_universal_client import UniversalMCPClient

logger = structlog.get_logger(__name__)

class QueryComplexity(str, Enum):
    """Query complexity levels"""
    SIMPLE = "simple"           # Single tool call
    MODERATE = "moderate"       # 2-3 sequential steps
    COMPLEX = "complex"         # Multi-step with branching logic
    HIGHLY_COMPLEX = "highly_complex"  # Requires iteration/search patterns

class QueryIntent(str, Enum):
    """High-level query intents"""
    LIST_ITEMS = "list_items"
    GET_SPECIFIC_INFO = "get_specific_info"  
    FIND_BY_CRITERIA = "find_by_criteria"
    ANALYZE_PATTERN = "analyze_pattern"
    COMPARE_ITEMS = "compare_items"
    MONITOR_STATUS = "monitor_status"
    TROUBLESHOOT_ISSUE = "troubleshoot_issue"
    PERFORM_ACTION = "perform_action"

@dataclass
class QueryAnalysis:
    """Analysis of user query"""
    original_query: str
    intent: QueryIntent
    complexity: QueryComplexity
    entities: Dict[str, Any]  # Extracted entities (job names, build numbers, etc.)
    filters: Dict[str, Any]   # Filtering criteria
    expected_steps: int
    confidence: float
    requires_iteration: bool = False
    requires_search: bool = False

@dataclass
class ExecutionPlan:
    """Plan for executing a complex query"""
    goal: Goal
    primary_approach: Approach
    alternative_approaches: List[Approach]
    estimated_duration: float
    success_probability: float
    resource_requirements: Dict[str, Any]

class PlanningEngine:
    """Intelligent planning engine for complex query decomposition"""
    
    def __init__(self, tool_registry: ToolRegistry, mcp_client: UniversalMCPClient):
        self.tool_registry = tool_registry
        self.mcp_client = mcp_client
        
        # Query pattern recognition
        self.patterns = self._initialize_query_patterns()
        
        # Planning templates for common scenarios
        self.planning_templates = self._initialize_planning_templates()
        
        # Entity extraction patterns
        self.entity_patterns = self._initialize_entity_patterns()
    
    def _initialize_query_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize query pattern recognition"""
        
        return {
            # Simple patterns
            "list_jobs": {
                "patterns": [r"list.*jobs?", r"show.*jobs?", r"what.*jobs?", r"all.*jobs?"],
                "intent": QueryIntent.LIST_ITEMS,
                "complexity": QueryComplexity.SIMPLE,
                "tools": [IntentType.LIST_JOBS]
            },
            
            "get_job_info": {
                "patterns": [r"info.*about\s+(\w+)", r"details.*(\w+)", r"status.*of\s+(\w+)"],
                "intent": QueryIntent.GET_SPECIFIC_INFO,
                "complexity": QueryComplexity.SIMPLE,
                "tools": [IntentType.GET_JOB_INFO],
                "entities": ["job_name"]
            },
            
            # Complex patterns requiring multi-step execution
            "find_last_failed_build": {
                "patterns": [
                    r"(?:find|get|show).*(?:last|latest|most recent).*failed.*build",
                    r"(?:last|latest).*(?:failed|failure).*build",
                    r"when.*did.*(\w+).*(?:last|recently).*fail",
                    r"(?:find|show).*failed.*build.*for\s+(\w+)"
                ],
                "intent": QueryIntent.FIND_BY_CRITERIA,
                "complexity": QueryComplexity.COMPLEX,
                "requires_iteration": True,
                "tools": [IntentType.GET_JOB_INFO, IntentType.GET_BUILD_HISTORY, IntentType.GET_BUILD_STATUS],
                "entities": ["job_name"]
            },
            
            "find_failed_builds_timerange": {
                "patterns": [
                    r"(?:failed|failure).*builds?.*(?:in|during|from|since).*(?:last|past)\s+(\w+)",
                    r"builds?.*that.*failed.*(?:yesterday|today|this week|last week)",
                    r"show.*failures?.*(?:in|during).*(\w+)"
                ],
                "intent": QueryIntent.FIND_BY_CRITERIA,
                "complexity": QueryComplexity.HIGHLY_COMPLEX,
                "requires_iteration": True,
                "requires_search": True,
                "tools": [IntentType.LIST_JOBS, IntentType.GET_BUILD_HISTORY, IntentType.GET_BUILD_STATUS],
                "entities": ["time_range"]
            },
            
            "compare_build_performance": {
                "patterns": [
                    r"compare.*builds?.*performance",
                    r"which.*builds?.*(?:faster|slower|longer)",
                    r"(?:performance|duration).*comparison.*builds?"
                ],
                "intent": QueryIntent.COMPARE_ITEMS,
                "complexity": QueryComplexity.HIGHLY_COMPLEX,
                "requires_iteration": True,
                "tools": [IntentType.GET_BUILD_HISTORY, IntentType.GET_BUILD_STATUS]
            },
            
            "troubleshoot_build_failure": {
                "patterns": [
                    r"why.*did.*(\w+).*fail",
                    r"what.*(?:caused|wrong).*build.*(\w+)",
                    r"troubleshoot.*(\w+)",
                    r"debug.*build.*failure.*(\w+)"
                ],
                "intent": QueryIntent.TROUBLESHOOT_ISSUE,
                "complexity": QueryComplexity.COMPLEX,
                "tools": [IntentType.GET_BUILD_STATUS, IntentType.GET_CONSOLE_LOG, IntentType.ANALYZE_FAILURE],
                "entities": ["job_name", "build_number"]
            },
            
            "trigger_and_monitor": {
                "patterns": [
                    r"(?:start|trigger|run).*(\w+).*(?:and|then).*(?:monitor|watch|check)",
                    r"build.*(\w+).*(?:and|then).*(?:wait|check|monitor)"
                ],
                "intent": QueryIntent.PERFORM_ACTION,
                "complexity": QueryComplexity.COMPLEX,
                "tools": [IntentType.TRIGGER_BUILD, IntentType.GET_BUILD_STATUS],
                "entities": ["job_name"]
            }
        }
    
    def _initialize_planning_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize planning templates for common scenarios"""
        
        return {
            "find_last_failed_build": {
                "description": "Find the most recent failed build for a job",
                "steps": [
                    {
                        "description": "Get job information and latest build number",
                        "tool": "get_job_info",
                        "params_template": {"job_name": "{job_name}"},
                        "extract_data": ["last_build_number", "job_status"]
                    },
                    {
                        "description": "Get build history to find failed builds", 
                        "tool": "get_build_history",
                        "params_template": {"job_name": "{job_name}", "limit": 20},
                        "filter_condition": "result == 'FAILURE'",
                        "extract_data": ["failed_builds"]
                    },
                    {
                        "description": "Get detailed status of most recent failed build",
                        "tool": "get_build_status",
                        "params_template": {"job_name": "{job_name}", "build_number": "{latest_failed_build}"},
                        "extract_data": ["failure_details"]
                    }
                ],
                "success_criteria": "found_failed_build",
                "fallback_strategy": "search_all_jobs_for_failures"
            },
            
            "find_builds_by_status": {
                "description": "Find builds matching specific status criteria",
                "steps": [
                    {
                        "description": "List all available jobs",
                        "tool": "list_jobs",
                        "extract_data": ["job_list"]
                    },
                    {
                        "description": "Get build history for each job",
                        "tool": "get_build_history", 
                        "params_template": {"job_name": "{job_name}", "limit": 10},
                        "iterate_over": "job_list",
                        "filter_condition": "{status_filter}",
                        "extract_data": ["matching_builds"]
                    }
                ],
                "success_criteria": "found_matching_builds"
            },
            
            "troubleshoot_failure": {
                "description": "Analyze and troubleshoot a build failure",
                "steps": [
                    {
                        "description": "Get build status and basic info",
                        "tool": "get_build_status",
                        "params_template": {"job_name": "{job_name}", "build_number": "{build_number}"},
                        "extract_data": ["build_info", "failure_reason"]
                    },
                    {
                        "description": "Get console log for error analysis",
                        "tool": "get_console_log",
                        "params_template": {"job_name": "{job_name}", "build_number": "{build_number}"},
                        "extract_data": ["console_output", "error_patterns"]
                    },
                    {
                        "description": "Analyze failure patterns and suggest fixes",
                        "tool": "analyze_failure",
                        "params_template": {
                            "job_name": "{job_name}", 
                            "build_number": "{build_number}",
                            "console_log": "{console_output}"
                        },
                        "extract_data": ["failure_analysis", "recommendations"]
                    }
                ],
                "success_criteria": "provided_troubleshooting_info"
            }
        }
    
    def _initialize_entity_patterns(self) -> Dict[str, str]:
        """Initialize entity extraction patterns"""
        
        return {
            "job_name": r"(?:job|build)\s+([A-Za-z0-9_-]+)|([A-Za-z0-9_-]+)(?:\s+(?:job|build))?",
            "build_number": r"(?:build|#)\s*(\d+)|(\d+)(?:\s*(?:build|#))?",
            "time_range": r"(?:last|past)\s+(\d+)\s+(minutes?|hours?|days?|weeks?|months?)",
            "status": r"(success|successful|fail|failed|failure|abort|aborted|unstable)",
            "user_name": r"(?:user|by)\s+([a-zA-Z0-9_.-]+)"
        }
    
    async def analyze_query(self, query: str, context: Dict[str, Any] = None) -> QueryAnalysis:
        """Analyze user query to understand intent and complexity"""
        
        context = context or {}
        query_lower = query.lower().strip()
        
        logger.info("Analyzing query", query=query)
        
        # Pattern matching
        matched_pattern = None
        highest_confidence = 0.0
        
        for pattern_name, pattern_config in self.patterns.items():
            for pattern in pattern_config["patterns"]:
                match = re.search(pattern, query_lower)
                if match:
                    # Simple confidence scoring based on match quality
                    confidence = len(match.group(0)) / len(query_lower)
                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        matched_pattern = pattern_config
                        
                        # Extract entities if pattern defines them
                        entities = {}
                        if "entities" in pattern_config:
                            entities = self._extract_entities(query, pattern_config["entities"], match)
                        
                        matched_pattern["extracted_entities"] = entities
        
        if matched_pattern:
            analysis = QueryAnalysis(
                original_query=query,
                intent=matched_pattern["intent"],
                complexity=matched_pattern["complexity"],
                entities=matched_pattern.get("extracted_entities", {}),
                filters={},
                expected_steps=len(matched_pattern.get("tools", [])),
                confidence=highest_confidence,
                requires_iteration=matched_pattern.get("requires_iteration", False),
                requires_search=matched_pattern.get("requires_search", False)
            )
        else:
            # Fallback analysis for unrecognized queries
            analysis = self._fallback_analysis(query, context)
        
        logger.info("Query analysis completed", 
                   intent=analysis.intent, 
                   complexity=analysis.complexity,
                   confidence=analysis.confidence)
        
        return analysis
    
    def _extract_entities(self, query: str, entity_types: List[str], 
                         match_groups: Any) -> Dict[str, Any]:
        """Extract entities from query based on patterns"""
        
        entities = {}
        
        for entity_type in entity_types:
            if entity_type in self.entity_patterns:
                pattern = self.entity_patterns[entity_type]
                entity_match = re.search(pattern, query, re.IGNORECASE)
                if entity_match:
                    # Get first non-None group
                    for group in entity_match.groups():
                        if group:
                            entities[entity_type] = group.strip()
                            break
        
        # Also extract from regex match groups if available
        if hasattr(match_groups, 'groups'):
            groups = match_groups.groups()
            if groups:
                # Map to entity types based on order
                entity_mapping = {
                    0: "job_name",
                    1: "build_number",
                    2: "time_range"
                }
                
                for i, group in enumerate(groups):
                    if group and i in entity_mapping:
                        entities[entity_mapping[i]] = group.strip()
        
        return entities
    
    def _fallback_analysis(self, query: str, context: Dict[str, Any]) -> QueryAnalysis:
        """Fallback analysis for unrecognized queries"""
        
        query_lower = query.lower()
        
        # Simple keyword-based classification
        if any(word in query_lower for word in ["list", "show", "all", "get"]):
            intent = QueryIntent.LIST_ITEMS
            complexity = QueryComplexity.SIMPLE
        elif any(word in query_lower for word in ["find", "search", "where", "which"]):
            intent = QueryIntent.FIND_BY_CRITERIA
            complexity = QueryComplexity.MODERATE
        elif any(word in query_lower for word in ["why", "what", "how", "troubleshoot", "debug"]):
            intent = QueryIntent.TROUBLESHOOT_ISSUE
            complexity = QueryComplexity.COMPLEX
        elif any(word in query_lower for word in ["start", "trigger", "run", "build"]):
            intent = QueryIntent.PERFORM_ACTION
            complexity = QueryComplexity.MODERATE
        else:
            intent = QueryIntent.GET_SPECIFIC_INFO
            complexity = QueryComplexity.SIMPLE
        
        return QueryAnalysis(
            original_query=query,
            intent=intent,
            complexity=complexity,
            entities=self._extract_all_entities(query),
            filters={},
            expected_steps=1 if complexity == QueryComplexity.SIMPLE else 3,
            confidence=0.3  # Low confidence for fallback
        )
    
    def _extract_all_entities(self, query: str) -> Dict[str, Any]:
        """Extract all possible entities from query"""
        
        entities = {}
        
        for entity_type, pattern in self.entity_patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                for group in match.groups():
                    if group:
                        entities[entity_type] = group.strip()
                        break
        
        return entities
    
    async def create_execution_plan(self, analysis: QueryAnalysis, 
                                  context: Dict[str, Any] = None) -> ExecutionPlan:
        """Create execution plan based on query analysis"""
        
        context = context or {}
        
        logger.info("Creating execution plan", 
                   intent=analysis.intent,
                   complexity=analysis.complexity)
        
        # Create goal
        goal = Goal(
            id=f"goal_{int(time.time())}",
            description=f"Execute: {analysis.original_query}",
            user_query=analysis.original_query,
            context=context
        )
        
        # Select planning template
        primary_approach = await self._create_primary_approach(analysis, goal.id)
        
        # Create alternative approaches
        alternative_approaches = await self._create_alternative_approaches(analysis, goal.id)
        
        # Estimate execution metrics
        estimated_duration = self._estimate_duration(primary_approach)
        success_probability = self._estimate_success_probability(analysis, primary_approach)
        
        plan = ExecutionPlan(
            goal=goal,
            primary_approach=primary_approach,
            alternative_approaches=alternative_approaches,
            estimated_duration=estimated_duration,
            success_probability=success_probability,
            resource_requirements={"tools": len(primary_approach.steps)}
        )
        
        logger.info("Execution plan created",
                   primary_steps=len(primary_approach.steps),
                   alternatives=len(alternative_approaches),
                   estimated_duration=estimated_duration)
        
        return plan
    
    async def _create_primary_approach(self, analysis: QueryAnalysis, 
                                     goal_id: str) -> Approach:
        """Create primary approach for query execution"""
        
        # Check if we have a specific template
        template_key = self._find_matching_template(analysis)
        
        if template_key and template_key in self.planning_templates:
            return await self._create_approach_from_template(
                template_key, analysis, goal_id
            )
        else:
            return await self._create_approach_from_analysis(analysis, goal_id)
    
    def _find_matching_template(self, analysis: QueryAnalysis) -> Optional[str]:
        """Find matching planning template for analysis"""
        
        query_lower = analysis.original_query.lower()
        
        # Direct pattern matching
        template_patterns = {
            "find_last_failed_build": [r"(?:last|latest).*failed.*build"],
            "find_builds_by_status": [r"find.*builds.*(?:status|result)", r"builds.*that.*(?:failed|success)"],
            "troubleshoot_failure": [r"why.*fail", r"troubleshoot", r"debug.*failure"]
        }
        
        for template_key, patterns in template_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return template_key
        
        return None
    
    async def _create_approach_from_template(self, template_key: str, 
                                           analysis: QueryAnalysis,
                                           goal_id: str) -> Approach:
        """Create approach from planning template"""
        
        template = self.planning_templates[template_key]
        
        approach = Approach(
            id=f"approach_{goal_id}_primary",
            description=template["description"]
        )
        
        # Create steps from template
        for i, step_template in enumerate(template["steps"]):
            step = Step(
                id=f"step_{goal_id}_{i}",
                description=step_template["description"],
                tool_name=step_template["tool"],
                parameters=self._resolve_parameters(step_template.get("params_template", {}), analysis)
            )
            
            approach.steps.append(step)
        
        return approach
    
    async def _create_approach_from_analysis(self, analysis: QueryAnalysis, 
                                           goal_id: str) -> Approach:
        """Create approach based on analysis without template"""
        
        approach = Approach(
            id=f"approach_{goal_id}_primary", 
            description=f"Execute {analysis.intent.value} query"
        )
        
        # Simple approach generation based on intent
        if analysis.intent == QueryIntent.LIST_ITEMS:
            step = Step(
                id=f"step_{goal_id}_0",
                description="List requested items",
                tool_name="list_jobs" if "job" in analysis.original_query.lower() else "list_items"
            )
            approach.steps.append(step)
            
        elif analysis.intent == QueryIntent.GET_SPECIFIC_INFO:
            job_name = analysis.entities.get("job_name")
            if job_name:
                step = Step(
                    id=f"step_{goal_id}_0",
                    description=f"Get information about {job_name}",
                    tool_name="get_job_info",
                    parameters={"job_name": job_name}
                )
                approach.steps.append(step)
            
        elif analysis.intent == QueryIntent.FIND_BY_CRITERIA:
            # Multi-step approach for finding items by criteria
            if analysis.requires_search:
                # Step 1: Get list of items
                step1 = Step(
                    id=f"step_{goal_id}_0",
                    description="Get list of items to search",
                    tool_name="list_jobs"
                )
                approach.steps.append(step1)
                
                # Step 2: Filter items based on criteria  
                step2 = Step(
                    id=f"step_{goal_id}_1", 
                    description="Filter items by criteria",
                    tool_name="get_build_history",
                    dependencies=[step1.id]
                )
                approach.steps.append(step2)
        
        return approach
    
    def _resolve_parameters(self, params_template: Dict[str, Any], 
                           analysis: QueryAnalysis) -> Dict[str, Any]:
        """Resolve parameter template with actual values"""
        
        resolved_params = {}
        
        for key, template_value in params_template.items():
            if isinstance(template_value, str) and template_value.startswith("{") and template_value.endswith("}"):
                # Template variable
                var_name = template_value[1:-1]
                if var_name in analysis.entities:
                    resolved_params[key] = analysis.entities[var_name]
                else:
                    # Keep template for runtime resolution
                    resolved_params[key] = template_value
            else:
                resolved_params[key] = template_value
        
        return resolved_params
    
    async def _create_alternative_approaches(self, analysis: QueryAnalysis, 
                                           goal_id: str) -> List[Approach]:
        """Create alternative approaches for fallback"""
        
        alternatives = []
        
        # Alternative approach 1: Broader search
        if analysis.intent == QueryIntent.FIND_BY_CRITERIA:
            alt1 = Approach(
                id=f"approach_{goal_id}_alt1",
                description="Broader search approach",
                success_probability=0.7
            )
            
            # Add steps for broader search
            step = Step(
                id=f"step_{goal_id}_alt1_0",
                description="Search all available items",
                tool_name="search_jobs" if "job" in analysis.original_query.lower() else "search_items",
                parameters={"pattern": "*"}
            )
            alt1.steps.append(step)
            alternatives.append(alt1)
        
        # Alternative approach 2: Simplified execution
        alt2 = Approach(
            id=f"approach_{goal_id}_alt2", 
            description="Simplified execution",
            success_probability=0.8
        )
        
        # Single step fallback
        step = Step(
            id=f"step_{goal_id}_alt2_0",
            description="Execute simplified version of request",
            tool_name="list_jobs"  # Safe fallback
        )
        alt2.steps.append(step)
        alternatives.append(alt2)
        
        return alternatives
    
    def _estimate_duration(self, approach: Approach) -> float:
        """Estimate execution duration in seconds"""
        
        # Base time per step
        base_time_per_step = 2.0  # seconds
        
        # Add complexity factors
        total_steps = len(approach.steps)
        estimated_time = total_steps * base_time_per_step
        
        # Add overhead for complex operations
        for step in approach.steps:
            if step.tool_name in ["get_build_history", "search_jobs"]:
                estimated_time += 3.0  # Extra time for complex operations
            elif step.tool_name in ["get_console_log"]:
                estimated_time += 1.0  # Medium complexity
        
        return estimated_time
    
    def _estimate_success_probability(self, analysis: QueryAnalysis, 
                                    approach: Approach) -> float:
        """Estimate probability of successful execution"""
        
        base_probability = 0.8
        
        # Adjust based on complexity
        complexity_factors = {
            QueryComplexity.SIMPLE: 0.95,
            QueryComplexity.MODERATE: 0.85,
            QueryComplexity.COMPLEX: 0.75,
            QueryComplexity.HIGHLY_COMPLEX: 0.65
        }
        
        complexity_factor = complexity_factors.get(analysis.complexity, 0.7)
        
        # Adjust based on entity extraction confidence
        entity_factor = 1.0
        if analysis.entities:
            # Lower confidence if entities weren't extracted well
            entity_factor = 0.9 if len(analysis.entities) < analysis.expected_steps else 1.0
        
        # Adjust based on analysis confidence
        analysis_factor = min(1.0, analysis.confidence + 0.3)
        
        return base_probability * complexity_factor * entity_factor * analysis_factor
    
    async def optimize_execution_order(self, approach: Approach) -> Approach:
        """Optimize step execution order for better performance"""
        
        # Simple dependency-based optimization
        optimized_steps = []
        remaining_steps = approach.steps.copy()
        
        while remaining_steps:
            # Find steps with no unmet dependencies
            ready_steps = []
            for step in remaining_steps:
                deps_met = all(
                    any(s.id == dep_id for s in optimized_steps) 
                    for dep_id in step.dependencies
                )
                if deps_met:
                    ready_steps.append(step)
            
            if ready_steps:
                # Add ready steps (could optimize further with parallel execution)
                optimized_steps.extend(ready_steps)
                for step in ready_steps:
                    remaining_steps.remove(step)
            else:
                # Break circular dependencies or add remaining steps
                optimized_steps.extend(remaining_steps)
                break
        
        approach.steps = optimized_steps
        return approach
    
    def get_planning_statistics(self) -> Dict[str, Any]:
        """Get planning engine statistics"""
        
        return {
            "supported_patterns": len(self.patterns),
            "planning_templates": len(self.planning_templates),
            "entity_types": len(self.entity_patterns),
            "complexity_levels": len(QueryComplexity),
            "intent_types": len(QueryIntent)
        }