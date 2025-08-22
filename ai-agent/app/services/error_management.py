"""
Advanced Error Handling - Circuit breakers, graceful degradation, and comprehensive error management
Provides production-grade reliability and self-healing capabilities
"""

import asyncio
import time
import traceback
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ServiceState(str, Enum):
    """Service health states"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"

class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class ErrorEvent:
    """Represents an error event"""
    timestamp: float
    error_type: str
    error_message: str
    service_name: str
    severity: ErrorSeverity
    context: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

@dataclass
class CircuitBreaker:
    """Circuit breaker implementation"""
    name: str
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 60.0  # seconds
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    
    def should_allow_request(self) -> bool:
        """Determine if request should be allowed"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """Record successful operation"""
        self.last_success_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed operation"""
        self.last_failure_time = time.time()
        self.failure_count += 1
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0

@dataclass
class HealthCheck:
    """Health check configuration"""
    name: str
    check_function: Callable[[], bool]
    interval: float = 30.0  # seconds
    timeout: float = 5.0    # seconds
    consecutive_failures_threshold: int = 3
    last_check_time: float = 0.0
    last_result: bool = True
    consecutive_failures: int = 0

class ErrorHandler:
    """Centralized error handling with categorization and recovery"""
    
    def __init__(self):
        self.error_patterns = self._initialize_error_patterns()
        self.error_history: List[ErrorEvent] = []
        self.max_error_history = 1000
        self.notification_callbacks: List[Callable] = []
    
    def _initialize_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize error pattern matching"""
        
        return {
            "connection_error": {
                "patterns": [r"connection.*error", r"connection.*refused", r"timeout", r"network.*error"],
                "severity": ErrorSeverity.HIGH,
                "recovery_actions": ["retry_with_backoff", "use_fallback_service"],
                "escalate_after": 3
            },
            "authentication_error": {
                "patterns": [r"authentication.*failed", r"unauthorized", r"403.*forbidden", r"invalid.*credentials"],
                "severity": ErrorSeverity.CRITICAL,
                "recovery_actions": ["refresh_token", "request_user_auth"],
                "escalate_after": 1
            },
            "rate_limit_error": {
                "patterns": [r"rate.*limit", r"too.*many.*requests", r"429.*error", r"quota.*exceeded"],
                "severity": ErrorSeverity.MEDIUM,
                "recovery_actions": ["exponential_backoff", "use_secondary_service"],
                "escalate_after": 5
            },
            "resource_not_found": {
                "patterns": [r"not.*found", r"404.*error", r"resource.*does.*not.*exist"],
                "severity": ErrorSeverity.LOW,
                "recovery_actions": ["suggest_alternatives", "search_similar_resources"],
                "escalate_after": 2
            },
            "server_error": {
                "patterns": [r"internal.*server.*error", r"500.*error", r"service.*unavailable", r"502.*error"],
                "severity": ErrorSeverity.HIGH,
                "recovery_actions": ["retry_with_backoff", "use_fallback_service", "graceful_degradation"],
                "escalate_after": 2
            },
            "validation_error": {
                "patterns": [r"validation.*error", r"invalid.*parameter", r"bad.*request", r"400.*error"],
                "severity": ErrorSeverity.MEDIUM,
                "recovery_actions": ["fix_parameters", "provide_user_guidance"],
                "escalate_after": 3
            }
        }
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorEvent:
        """Handle and categorize an error"""
        
        context = context or {}
        error_message = str(error)
        error_type = type(error).__name__
        
        # Classify error
        severity, pattern_name = self._classify_error(error_message, error_type)
        
        # Create error event
        error_event = ErrorEvent(
            timestamp=time.time(),
            error_type=error_type,
            error_message=error_message,
            service_name=context.get("service", "unknown"),
            severity=severity,
            context=context,
            stack_trace=traceback.format_exc(),
            user_id=context.get("user_id"),
            session_id=context.get("session_id")
        )
        
        # Record error
        self._record_error(error_event)
        
        # Log error with appropriate level
        log_level = self._get_log_level(severity)
        logger.log(log_level, "Error handled",
                   error_type=error_type,
                   severity=severity,
                   pattern=pattern_name,
                   service=error_event.service_name,
                   user_id=error_event.user_id)
        
        # Notify if critical
        if severity == ErrorSeverity.CRITICAL:
            self._notify_error(error_event)
        
        return error_event
    
    def _classify_error(self, error_message: str, error_type: str) -> tuple[ErrorSeverity, str]:
        """Classify error based on message and type"""
        
        error_lower = error_message.lower()
        
        for pattern_name, pattern_config in self.error_patterns.items():
            for pattern in pattern_config["patterns"]:
                import re
                if re.search(pattern, error_lower):
                    return pattern_config["severity"], pattern_name
        
        # Default classification based on error type
        critical_types = ["SecurityError", "AuthenticationError", "PermissionError"]
        high_types = ["ConnectionError", "TimeoutError", "ServiceUnavailableError"]
        medium_types = ["ValueError", "ValidationError", "TypeError"]
        
        if error_type in critical_types:
            return ErrorSeverity.CRITICAL, "unknown_critical"
        elif error_type in high_types:
            return ErrorSeverity.HIGH, "unknown_high"
        elif error_type in medium_types:
            return ErrorSeverity.MEDIUM, "unknown_medium"
        else:
            return ErrorSeverity.LOW, "unknown_low"
    
    def _record_error(self, error_event: ErrorEvent):
        """Record error in history"""
        
        self.error_history.append(error_event)
        
        # Maintain history size
        if len(self.error_history) > self.max_error_history:
            self.error_history = self.error_history[-self.max_error_history:]
    
    def _get_log_level(self, severity: ErrorSeverity) -> str:
        """Map severity to log level"""
        
        severity_mapping = {
            ErrorSeverity.LOW: "info",
            ErrorSeverity.MEDIUM: "warning", 
            ErrorSeverity.HIGH: "error",
            ErrorSeverity.CRITICAL: "critical"
        }
        
        return severity_mapping.get(severity, "error")
    
    def _notify_error(self, error_event: ErrorEvent):
        """Notify about critical errors"""
        
        for callback in self.notification_callbacks:
            try:
                callback(error_event)
            except Exception as e:
                logger.error("Error notification callback failed", error=str(e))
    
    def add_notification_callback(self, callback: Callable[[ErrorEvent], None]):
        """Add error notification callback"""
        self.notification_callbacks.append(callback)
    
    def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get error statistics for the last N hours"""
        
        cutoff_time = time.time() - (hours * 3600)
        recent_errors = [e for e in self.error_history if e.timestamp > cutoff_time]
        
        # Group by severity
        severity_counts = {}
        for severity in ErrorSeverity:
            severity_counts[severity.value] = len([e for e in recent_errors if e.severity == severity])
        
        # Group by service
        service_counts = {}
        for error in recent_errors:
            service_counts[error.service_name] = service_counts.get(error.service_name, 0) + 1
        
        # Group by error type
        type_counts = {}
        for error in recent_errors:
            type_counts[error.error_type] = type_counts.get(error.error_type, 0) + 1
        
        return {
            "total_errors": len(recent_errors),
            "error_rate": len(recent_errors) / hours,
            "by_severity": severity_counts,
            "by_service": service_counts,
            "by_type": type_counts,
            "time_period_hours": hours
        }

class HealthMonitor:
    """Health monitoring and service state management"""
    
    def __init__(self):
        self.services: Dict[str, ServiceState] = {}
        self.health_checks: Dict[str, HealthCheck] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
    
    def register_service(self, service_name: str, 
                        health_check: Optional[HealthCheck] = None,
                        circuit_breaker: Optional[CircuitBreaker] = None):
        """Register a service for monitoring"""
        
        self.services[service_name] = ServiceState.HEALTHY
        
        if health_check:
            self.health_checks[service_name] = health_check
        
        if circuit_breaker:
            self.circuit_breakers[service_name] = circuit_breaker
        
        logger.info("Service registered for monitoring", service=service_name)
    
    def get_circuit_breaker(self, service_name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker for service"""
        return self.circuit_breakers.get(service_name)
    
    def create_circuit_breaker(self, service_name: str, **kwargs) -> CircuitBreaker:
        """Create and register circuit breaker for service"""
        
        circuit_breaker = CircuitBreaker(name=service_name, **kwargs)
        self.circuit_breakers[service_name] = circuit_breaker
        
        logger.info("Circuit breaker created", service=service_name, config=kwargs)
        return circuit_breaker
    
    async def start_monitoring(self):
        """Start health monitoring"""
        
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        
        while self._running:
            try:
                # Run health checks
                for service_name, health_check in self.health_checks.items():
                    if (time.time() - health_check.last_check_time) >= health_check.interval:
                        await self._run_health_check(service_name, health_check)
                
                # Update service states based on circuit breakers
                for service_name, circuit_breaker in self.circuit_breakers.items():
                    self._update_service_state_from_circuit(service_name, circuit_breaker)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error("Error in health monitoring loop", error=str(e))
                await asyncio.sleep(30)  # Longer sleep on error
    
    async def _run_health_check(self, service_name: str, health_check: HealthCheck):
        """Run individual health check"""
        
        try:
            # Run health check with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(health_check.check_function),
                timeout=health_check.timeout
            )
            
            health_check.last_check_time = time.time()
            health_check.last_result = result
            
            if result:
                health_check.consecutive_failures = 0
                if self.services[service_name] != ServiceState.HEALTHY:
                    logger.info("Service recovered", service=service_name)
                    self.services[service_name] = ServiceState.HEALTHY
            else:
                health_check.consecutive_failures += 1
                logger.warning("Health check failed", 
                             service=service_name,
                             consecutive_failures=health_check.consecutive_failures)
                
                if (health_check.consecutive_failures >= 
                    health_check.consecutive_failures_threshold):
                    self.services[service_name] = ServiceState.UNHEALTHY
                    
        except asyncio.TimeoutError:
            health_check.consecutive_failures += 1
            logger.error("Health check timeout", service=service_name)
            
        except Exception as e:
            health_check.consecutive_failures += 1
            logger.error("Health check error", service=service_name, error=str(e))
    
    def _update_service_state_from_circuit(self, service_name: str, circuit_breaker: CircuitBreaker):
        """Update service state based on circuit breaker"""
        
        current_state = self.services.get(service_name, ServiceState.HEALTHY)
        
        if circuit_breaker.state == CircuitState.OPEN:
            if current_state != ServiceState.FAILED:
                logger.warning("Service marked as failed due to circuit breaker", 
                             service=service_name)
                self.services[service_name] = ServiceState.FAILED
        elif circuit_breaker.state == CircuitState.HALF_OPEN:
            if current_state != ServiceState.DEGRADED:
                self.services[service_name] = ServiceState.DEGRADED
        elif circuit_breaker.state == CircuitState.CLOSED:
            if current_state in [ServiceState.FAILED, ServiceState.DEGRADED]:
                if service_name not in self.health_checks:  # No health check override
                    self.services[service_name] = ServiceState.HEALTHY
    
    def get_service_state(self, service_name: str) -> ServiceState:
        """Get current service state"""
        return self.services.get(service_name, ServiceState.HEALTHY)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        
        total_services = len(self.services)
        healthy_services = len([s for s in self.services.values() if s == ServiceState.HEALTHY])
        degraded_services = len([s for s in self.services.values() if s == ServiceState.DEGRADED])
        unhealthy_services = len([s for s in self.services.values() if s == ServiceState.UNHEALTHY])
        failed_services = len([s for s in self.services.values() if s == ServiceState.FAILED])
        
        # Calculate overall health score
        health_score = 0.0
        if total_services > 0:
            health_score = (
                (healthy_services * 1.0 + degraded_services * 0.7 + 
                 unhealthy_services * 0.3 + failed_services * 0.0) / total_services
            )
        
        # Determine overall state
        if health_score >= 0.9:
            overall_state = ServiceState.HEALTHY
        elif health_score >= 0.7:
            overall_state = ServiceState.DEGRADED
        elif health_score >= 0.3:
            overall_state = ServiceState.UNHEALTHY
        else:
            overall_state = ServiceState.FAILED
        
        return {
            "overall_state": overall_state,
            "health_score": health_score,
            "total_services": total_services,
            "service_states": {
                "healthy": healthy_services,
                "degraded": degraded_services,
                "unhealthy": unhealthy_services,
                "failed": failed_services
            },
            "services": dict(self.services),
            "circuit_breakers": {
                name: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "success_count": cb.success_count
                }
                for name, cb in self.circuit_breakers.items()
            }
        }

class ErrorManagementSystem:
    """Comprehensive error management system"""
    
    def __init__(self):
        self.error_handler = ErrorHandler()
        self.health_monitor = HealthMonitor()
        self._initialized = False
    
    async def initialize(self):
        """Initialize error management system"""
        
        if self._initialized:
            return
        
        # Start health monitoring
        await self.health_monitor.start_monitoring()
        
        self._initialized = True
        logger.info("Error Management System initialized")
    
    async def shutdown(self):
        """Shutdown error management system"""
        
        await self.health_monitor.stop_monitoring()
        logger.info("Error Management System shut down")
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorEvent:
        """Handle error with full error management"""
        
        error_event = self.error_handler.handle_error(error, context)
        
        # Update circuit breaker if service specified
        if context and "service" in context:
            service_name = context["service"]
            circuit_breaker = self.health_monitor.get_circuit_breaker(service_name)
            if circuit_breaker:
                circuit_breaker.record_failure()
        
        return error_event
    
    def record_success(self, service_name: str):
        """Record successful operation"""
        
        circuit_breaker = self.health_monitor.get_circuit_breaker(service_name)
        if circuit_breaker:
            circuit_breaker.record_success()
    
    def should_allow_request(self, service_name: str) -> bool:
        """Check if request should be allowed (circuit breaker)"""
        
        circuit_breaker = self.health_monitor.get_circuit_breaker(service_name)
        if circuit_breaker:
            return circuit_breaker.should_allow_request()
        return True
    
    def register_service(self, service_name: str, **kwargs):
        """Register service for monitoring"""
        
        self.health_monitor.register_service(service_name, **kwargs)
    
    def add_error_notification(self, callback: Callable[[ErrorEvent], None]):
        """Add error notification callback"""
        
        self.error_handler.add_notification_callback(callback)
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        
        return {
            "health": self.health_monitor.get_system_health(),
            "errors": self.error_handler.get_error_statistics(),
            "initialized": self._initialized
        }

# Global error management system instance
error_management = ErrorManagementSystem()