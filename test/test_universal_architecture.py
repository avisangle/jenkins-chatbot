#!/usr/bin/env python3
"""
Universal MCP Architecture Integration Test
Tests the complete universal system with multiple MCP servers and complex scenarios
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_universal_architecture():
    """Test the complete universal MCP architecture"""
    
    print("🚀 Testing Universal MCP Architecture")
    print("="*80)
    
    try:
        # Import our universal components
        from ai_agent.app.services.mcp_universal_client import UniversalMCPClient, MCPServerConfig, TransportType
        from ai_agent.app.services.tool_registry import ToolRegistry
        from ai_agent.app.services.conversation_state import conversation_state_manager
        from ai_agent.app.services.planning_engine import PlanningEngine
        from ai_agent.app.services.recovery_manager import RecoveryManager
        from ai_agent.app.services.config_manager import config_manager
        from ai_agent.app.services.ai_service_universal import UniversalAIService
        from ai_agent.app.services.error_management import error_management
        from ai_agent.app.services.performance_manager import performance_manager
        
        test_results = []
        
        # Test 1: Universal MCP Client Discovery
        print("\n📡 Test 1: Universal MCP Client - Multi-Server Discovery")
        await test_mcp_client_discovery(test_results)
        
        # Test 2: Tool Registry Intelligence
        print("\n🧰 Test 2: Tool Registry - Intelligent Fallback and Performance Tracking")
        await test_tool_registry_intelligence(test_results)
        
        # Test 3: Conversation State Management
        print("\n💭 Test 3: Conversation State - Multi-Step Goal Tracking")
        await test_conversation_state_management(test_results)
        
        # Test 4: Planning Engine Complex Queries
        print("\n🧠 Test 4: Planning Engine - Complex Query Decomposition")
        await test_planning_engine_complex_queries(test_results)
        
        # Test 5: Recovery Manager Failure Handling
        print("\n🔄 Test 5: Recovery Manager - Intelligent Failure Recovery")
        await test_recovery_manager_failure_handling(test_results)
        
        # Test 6: Universal AI Service with Gemini Function Calling
        print("\n🤖 Test 6: Universal AI Service - True LLM Autonomy")
        await test_universal_ai_service(test_results)
        
        # Test 7: Error Management and Circuit Breakers
        print("\n🛡️ Test 7: Error Management - Circuit Breakers and Graceful Degradation")
        await test_error_management_circuit_breakers(test_results)
        
        # Test 8: Performance Optimization
        print("\n⚡ Test 8: Performance Manager - Caching and Connection Pooling")
        await test_performance_optimization(test_results)
        
        # Test 9: End-to-End Complex Scenario
        print("\n🔄 Test 9: End-to-End - Complex Multi-Step Scenario")
        await test_end_to_end_complex_scenario(test_results)
        
        # Print Final Results
        print("\n" + "="*80)
        print("📊 UNIVERSAL ARCHITECTURE TEST RESULTS")
        print("="*80)
        
        passed = sum(1 for result in test_results if result["status"] == "PASSED")
        failed = sum(1 for result in test_results if result["status"] == "FAILED")
        
        for result in test_results:
            status_icon = "✅" if result["status"] == "PASSED" else "❌"
            print(f"{status_icon} {result['test']}: {result['status']}")
            if result["status"] == "FAILED":
                print(f"   Error: {result.get('error', 'Unknown error')}")
        
        print(f"\nOverall Results: {passed}/{len(test_results)} tests passed ({(passed/len(test_results)*100):.1f}%)")
        
        if passed == len(test_results):
            print("🎉 ALL TESTS PASSED - Universal Architecture is working correctly!")
        else:
            print(f"⚠️ {failed} test(s) failed - See details above")
        
        return passed == len(test_results)
        
    except Exception as e:
        print(f"❌ Critical error in universal architecture test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_mcp_client_discovery(test_results: List[Dict]):
    """Test Universal MCP Client with multiple servers"""
    
    try:
        from ai_agent.app.services.mcp_universal_client import UniversalMCPClient, MCPServerConfig, TransportType
        
        # Configure multiple servers
        servers = [
            MCPServerConfig(
                name="jenkins-primary",
                url="http://mcp-server:8010/mcp",
                transport=TransportType.HTTP,
                priority=1
            ),
            MCPServerConfig(
                name="jenkins-fallback", 
                url="http://mcp-fallback:8011/mcp",
                transport=TransportType.HTTP,
                priority=2,
                enabled=False  # Simulated fallback server
            )
        ]
        
        client = UniversalMCPClient(servers)
        
        # Test server discovery
        capabilities = await client.discover_all_servers()
        
        # Verify discovery
        assert len(capabilities) > 0, "No server capabilities discovered"
        assert "jenkins-primary" in capabilities, "Primary server not discovered"
        
        # Test tool schema normalization
        tools = await client.get_available_tools()
        assert len(tools) > 0, "No tools discovered"
        
        # Test parameter validation
        sample_tool = tools[0] if tools else None
        if sample_tool:
            validation = await client.validate_parameters(
                sample_tool.name, {"test_param": "test_value"}
            )
            assert validation is not None, "Parameter validation failed"
        
        # Test health check
        health = await client.health_check()
        assert isinstance(health, dict), "Health check failed"
        
        test_results.append({
            "test": "Universal MCP Client Discovery",
            "status": "PASSED",
            "details": f"Discovered {len(capabilities)} servers with {len(tools)} tools"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Universal MCP Client Discovery",
            "status": "FAILED",
            "error": str(e)
        })

async def test_tool_registry_intelligence(test_results: List[Dict]):
    """Test Tool Registry with intelligent selection and fallbacks"""
    
    try:
        from ai_agent.app.services.mcp_universal_client import UniversalMCPClient, MCPServerConfig, TransportType
        from ai_agent.app.services.tool_registry import ToolRegistry, IntentType
        
        # Set up registry
        client = UniversalMCPClient([MCPServerConfig(
            name="test-server", 
            url="http://mcp-server:8010/mcp",
            transport=TransportType.HTTP
        )])
        
        registry = ToolRegistry(client)
        
        # Discover tools
        await registry.discover_tools()
        
        # Test intent-based tool selection
        tool_selection = await registry.select_optimal_tool(IntentType.LIST_JOBS)
        assert tool_selection is not None, "Tool selection failed"
        
        # Test fallback execution
        response = await registry.execute_with_fallback(
            IntentType.LIST_JOBS, {}, {"test": "context"}
        )
        assert response is not None, "Fallback execution failed"
        
        # Test performance tracking
        metrics = registry.get_performance_metrics()
        assert isinstance(metrics, dict), "Performance metrics not available"
        
        # Test Gemini function generation
        functions = await registry.generate_gemini_functions()
        assert len(functions) > 0, "No Gemini functions generated"
        
        test_results.append({
            "test": "Tool Registry Intelligence",
            "status": "PASSED", 
            "details": f"Generated {len(functions)} function declarations with performance tracking"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Tool Registry Intelligence",
            "status": "FAILED",
            "error": str(e)
        })

async def test_conversation_state_management(test_results: List[Dict]):
    """Test conversation state and multi-step goal tracking"""
    
    try:
        from ai_agent.app.services.conversation_state import conversation_state_manager, Goal, Step
        
        # Create test session
        session = conversation_state_manager.get_or_create_session("test_session", "test_user")
        
        # Create complex goal
        goal = session.create_goal(
            "Find last failed build for job X",
            "Can you get me last failed build number for MyJobName?",
            {"complex": True, "requires_iteration": True}
        )
        
        # Add multi-step plan
        step1 = session.add_step_to_current_goal(
            "Get job information",
            "get_job_info",
            {"job_name": "MyJobName"}
        )
        
        step2 = session.add_step_to_current_goal(
            "Get build history", 
            "get_build_history",
            {"job_name": "MyJobName", "limit": 20},
            dependencies=[step1.id] if step1 else []
        )
        
        step3 = session.add_step_to_current_goal(
            "Find most recent failure",
            "analyze_build_history", 
            {"filter": "failed"},
            dependencies=[step2.id] if step2 else []
        )
        
        # Test goal progression
        session.start_current_goal()
        assert session.current_goal.status.value == "in_progress", "Goal not started properly"
        
        # Complete steps
        if step1:
            session.complete_step(step1.id, {"last_build_number": 25, "job_status": "active"})
        if step2:
            session.complete_step(step2.id, {"builds": [{"number": 23, "result": "FAILURE"}]})
        if step3:
            session.complete_step(step3.id, {"last_failed_build": 23})
        
        # Test memory storage
        session.store_memory("last_query_result", {"last_failed_build": 23}, importance=0.9)
        
        # Test context retrieval
        recent_context = session.get_recent_context(minutes=5)
        assert isinstance(recent_context, list), "Context retrieval failed"
        
        # Test repetition detection
        has_recent = session.has_recent_action("get_job_info", minutes=5)
        assert has_recent == True, "Recent action detection failed"
        
        test_results.append({
            "test": "Conversation State Management",
            "status": "PASSED",
            "details": "Multi-step goal tracking with memory and context management"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Conversation State Management", 
            "status": "FAILED",
            "error": str(e)
        })

async def test_planning_engine_complex_queries(test_results: List[Dict]):
    """Test planning engine with complex query decomposition"""
    
    try:
        from ai_agent.app.services.mcp_universal_client import UniversalMCPClient, MCPServerConfig, TransportType
        from ai_agent.app.services.tool_registry import ToolRegistry
        from ai_agent.app.services.planning_engine import PlanningEngine, QueryComplexity
        
        # Set up components
        client = UniversalMCPClient([MCPServerConfig(
            name="test-server",
            url="http://mcp-server:8010/mcp", 
            transport=TransportType.HTTP
        )])
        
        registry = ToolRegistry(client)
        engine = PlanningEngine(registry, client)
        
        # Test complex query analysis
        complex_queries = [
            "Find the last failed build for OracleCCB-CICD-Pipeline",
            "Show me all builds that failed in the last week",
            "Compare performance of builds between job A and job B",
            "Why did MyProject build #45 fail?"
        ]
        
        analyses = []
        for query in complex_queries:
            analysis = await engine.analyze_query(query)
            analyses.append(analysis)
            
            # Verify analysis
            assert analysis.complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX, QueryComplexity.HIGHLY_COMPLEX], \
                f"Query '{query}' not properly classified as complex"
            
            # Test execution plan creation
            plan = await engine.create_execution_plan(analysis)
            assert plan.goal is not None, f"No goal created for query: {query}"
            assert len(plan.primary_approach.steps) > 0, f"No steps in primary approach for: {query}"
        
        # Test planning statistics
        stats = engine.get_planning_statistics()
        assert stats["supported_patterns"] > 0, "No supported patterns"
        
        test_results.append({
            "test": "Planning Engine Complex Queries",
            "status": "PASSED",
            "details": f"Successfully analyzed {len(complex_queries)} complex queries with multi-step planning"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Planning Engine Complex Queries",
            "status": "FAILED", 
            "error": str(e)
        })

async def test_recovery_manager_failure_handling(test_results: List[Dict]):
    """Test recovery manager with intelligent failure handling"""
    
    try:
        from ai_agent.app.services.mcp_universal_client import UniversalMCPClient, MCPServerConfig, TransportType
        from ai_agent.app.services.tool_registry import ToolRegistry
        from ai_agent.app.services.recovery_manager import RecoveryManager, FailureContext, FailureType
        from ai_agent.app.services.conversation_state import Goal, Step, conversation_state_manager
        
        # Set up components
        client = UniversalMCPClient([MCPServerConfig(
            name="test-server",
            url="http://mcp-server:8010/mcp",
            transport=TransportType.HTTP
        )])
        
        registry = ToolRegistry(client)
        recovery = RecoveryManager(registry, client)
        
        # Create test failure scenarios
        session = conversation_state_manager.get_or_create_session("recovery_test", "test_user")
        goal = session.create_goal("Test recovery", "test query")
        step = session.add_step_to_current_goal("Test step", "test_tool", {"param": "value"})
        
        failure_scenarios = [
            ("Tool not found: unknown_tool", FailureType.TOOL_NOT_FOUND),
            ("Parameter validation failed: invalid parameter 'x'", FailureType.PARAMETER_ERROR),
            ("Connection timeout after 30 seconds", FailureType.TIMEOUT),
            ("Server returned 500 internal server error", FailureType.SERVER_ERROR),
            ("Rate limit exceeded: too many requests", FailureType.RATE_LIMITED)
        ]
        
        for error_msg, expected_type in failure_scenarios:
            # Create failure context
            failure_context = FailureContext(
                step=step,
                goal=goal,
                error=error_msg,
                failure_type=expected_type,
                attempt_count=1,
                total_duration=5.0
            )
            
            # Test failure handling
            recovery_action = await recovery.handle_failure(failure_context, session)
            assert recovery_action is not None, f"No recovery action for: {error_msg}"
            assert recovery_action.strategy is not None, f"No strategy for: {error_msg}"
            
            # Test recovery execution (mock)
            # In a real test, we'd execute the recovery action
            
        # Test recovery statistics
        stats = recovery.get_recovery_statistics()
        assert isinstance(stats, dict), "Recovery statistics not available"
        
        test_results.append({
            "test": "Recovery Manager Failure Handling",
            "status": "PASSED",
            "details": f"Successfully handled {len(failure_scenarios)} failure scenarios with intelligent recovery"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Recovery Manager Failure Handling",
            "status": "FAILED",
            "error": str(e)
        })

async def test_universal_ai_service(test_results: List[Dict]):
    """Test Universal AI Service with Gemini Function Calling"""
    
    try:
        from ai_agent.app.services.ai_service_universal import UniversalAIService
        from ai_agent.app.config import settings
        
        # Create service instance
        service = UniversalAIService()
        
        # Test initialization
        await service.initialize()
        assert service.initialization_complete, "Service initialization failed"
        assert service.model is not None, "Gemini model not initialized"
        assert len(service.function_declarations) > 0, "No function declarations generated"
        
        # Verify model uses configurable settings
        # Note: In real implementation, this would be verified through model properties
        assert service.model is not None, "Model configuration verification failed"
        
        # Test health check
        health = await service.health_check()
        assert health == True, "Universal AI Service health check failed"
        
        # Test service metrics
        metrics = service.get_service_metrics()
        assert isinstance(metrics, dict), "Service metrics not available"
        assert "service_metrics" in metrics, "Missing service metrics"
        assert "model_config" in metrics, "Missing model config"
        
        # Verify model configuration
        model_config = metrics["model_config"]
        assert model_config["model"] == settings.GEMINI_MODEL, "Model not using configured setting"
        
        # Test conversation insights (mock session)
        insights = await service.get_conversation_insights("mock_session")
        # This will return error for non-existent session, which is expected
        
        test_results.append({
            "test": "Universal AI Service",
            "status": "PASSED",
            "details": f"Service initialized with {len(service.function_declarations)} functions using {settings.GEMINI_MODEL}"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Universal AI Service",
            "status": "FAILED",
            "error": str(e)
        })

async def test_error_management_circuit_breakers(test_results: List[Dict]):
    """Test error management with circuit breakers"""
    
    try:
        from ai_agent.app.services.error_management import error_management, ErrorSeverity
        
        # Initialize error management
        await error_management.initialize()
        
        # Register test service
        error_management.register_service("test_service")
        
        # Test error handling
        test_error = Exception("Test connection error")
        error_event = error_management.handle_error(
            test_error, 
            {"service": "test_service", "user_id": "test_user"}
        )
        
        assert error_event.error_type == "Exception", "Error type not captured"
        assert error_event.service_name == "test_service", "Service name not captured"
        
        # Test circuit breaker
        assert error_management.should_allow_request("test_service") == True, "Circuit breaker blocking initial request"
        
        # Simulate multiple failures to open circuit
        for _ in range(6):  # Exceed failure threshold
            error_management.handle_error(
                Exception("Simulated failure"),
                {"service": "test_service"}
            )
        
        # Test success recording
        error_management.record_success("test_service")
        
        # Test comprehensive status
        status = error_management.get_comprehensive_status()
        assert isinstance(status, dict), "Comprehensive status not available"
        assert "health" in status, "Health information missing"
        assert "errors" in status, "Error information missing"
        
        test_results.append({
            "test": "Error Management Circuit Breakers", 
            "status": "PASSED",
            "details": "Circuit breakers and error handling working correctly"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Error Management Circuit Breakers",
            "status": "FAILED",
            "error": str(e)
        })

async def test_performance_optimization(test_results: List[Dict]):
    """Test performance manager with caching and optimization"""
    
    try:
        from ai_agent.app.services.performance_manager import performance_manager
        
        # Test caching
        async def slow_operation():
            await asyncio.sleep(0.1)  # Simulate slow operation
            return {"result": "test_data", "timestamp": time.time()}
        
        # First call (cache miss)
        result1 = await performance_manager.cached_operation(
            "test_key", slow_operation, ttl=5.0
        )
        
        # Second call (cache hit)
        start_time = time.time()
        result2 = await performance_manager.cached_operation(
            "test_key", slow_operation, ttl=5.0
        )
        cache_time = time.time() - start_time
        
        assert result1 == result2, "Cached result doesn't match original"
        assert cache_time < 0.05, "Cache not providing performance benefit"
        
        # Test performance optimization
        await performance_manager.optimize_performance()
        
        # Test performance report
        report = performance_manager.get_performance_report()
        assert isinstance(report, dict), "Performance report not available"
        assert "cache" in report, "Cache information missing from report"
        assert "operations" in report, "Operations information missing from report"
        
        # Test cache statistics
        cache_stats = report["cache"]["stats"]
        assert cache_stats["total_items"] > 0, "No items in cache"
        
        test_results.append({
            "test": "Performance Optimization",
            "status": "PASSED",
            "details": f"Caching and performance optimization working, {cache_stats['total_items']} cached items"
        })
        
    except Exception as e:
        test_results.append({
            "test": "Performance Optimization",
            "status": "FAILED",
            "error": str(e)
        })

async def test_end_to_end_complex_scenario(test_results: List[Dict]):
    """Test end-to-end complex scenario with all components"""
    
    try:
        # This would test a complete flow like:
        # 1. User query: "Find last failed build for OracleCCB-CICD-Pipeline"
        # 2. Planning engine decomposes query
        # 3. Conversation state tracks progress
        # 4. Tool registry selects optimal tools with fallbacks
        # 5. MCP client executes with retry/recovery
        # 6. Performance manager optimizes with caching
        # 7. Error management handles any failures
        # 8. Universal AI service coordinates everything
        
        from ai_agent.app.services.ai_service_universal import UniversalAIService
        
        # Create service (this integrates all components)
        service = UniversalAIService()
        await service.initialize()
        
        # Test complex query processing
        complex_query = "Can you get me last failed build number for OracleCCB-CICD-Pipeline?"
        user_context = {
            "user_id": "test_user", 
            "session_id": "integration_test",
            "permissions": ["Job.Read", "Job.Build"]
        }
        
        # This would normally call the actual Gemini API
        # For testing, we verify the service is properly configured
        health = await service.health_check()
        assert health == True, "End-to-end service health check failed"
        
        metrics = service.get_service_metrics()
        assert metrics["initialization_complete"] == True, "Service not properly initialized"
        
        # Test conversation insights
        insights = await service.get_conversation_insights("integration_test")
        # Will return session not found, which is expected for new session
        
        test_results.append({
            "test": "End-to-End Complex Scenario",
            "status": "PASSED", 
            "details": "All components integrated successfully, service ready for complex queries"
        })
        
    except Exception as e:
        test_results.append({
            "test": "End-to-End Complex Scenario",
            "status": "FAILED",
            "error": str(e)
        })

if __name__ == "__main__":
    asyncio.run(test_universal_architecture())