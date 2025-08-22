"""
Audit Service for comprehensive logging and security event tracking
Handles PostgreSQL audit logs and security monitoring
"""

import time
from typing import Dict, List, Optional, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, func
from datetime import datetime, timedelta

from app.database import get_db_session, AuditLogTable, SecurityEventTable, JenkinsApiCallTable

logger = structlog.get_logger(__name__)

class AuditService:
    """Service for audit logging and security monitoring"""
    
    def __init__(self):
        pass
    
    async def log_interaction_start(
        self,
        session_id: str,
        user_id: str,
        query: str,
        permissions: List[str]
    ) -> int:
        """Log the start of an AI interaction"""
        
        try:
            async with get_db_session() as db:
                # Create audit entry
                audit_entry = AuditLogTable(
                    session_id=session_id,
                    user_id=user_id,
                    user_query=query,
                    permissions_used=permissions,
                    success=False  # Will be updated on completion
                )
                
                db.add(audit_entry)
                await db.commit()
                await db.refresh(audit_entry)
                
                logger.info("Interaction audit started",
                           interaction_id=audit_entry.id,
                           session_id=session_id,
                           user_id=user_id)
                
                return audit_entry.id
                
        except Exception as e:
            logger.error("Failed to log interaction start",
                        error=str(e),
                        session_id=session_id,
                        user_id=user_id)
            return 0  # Return 0 on error to avoid breaking the flow
    
    async def log_interaction_complete(
        self,
        interaction_id: int,
        response: str,
        actions: Optional[List[Any]] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> bool:
        """Log the completion of an AI interaction"""
        
        try:
            if interaction_id == 0:  # Skip if initial logging failed
                return False
                
            async with get_db_session() as db:
                # Update existing audit entry
                stmt = (
                    update(AuditLogTable)
                    .where(AuditLogTable.id == interaction_id)
                    .values(
                        ai_response=response,
                        actions_planned=actions,
                        success=success,
                        error_message=error,
                        response_time_ms=int((time.time() - 
                            (await db.get(AuditLogTable, interaction_id)).timestamp.timestamp()) * 1000)
                    )
                )
                
                await db.execute(stmt)
                await db.commit()
                
                logger.info("Interaction audit completed",
                           interaction_id=interaction_id,
                           success=success,
                           error=error)
                
                return True
                
        except Exception as e:
            logger.error("Failed to log interaction completion",
                        error=str(e),
                        interaction_id=interaction_id)
            return False
    
    async def log_jenkins_api_call(
        self,
        session_id: str,
        user_id: str,
        ai_interaction_id: Optional[int],
        endpoint: str,
        method: str,
        permission_required: Optional[str] = None,
        request_body: Optional[Dict[str, Any]] = None
    ) -> int:
        """Log Jenkins API call start"""
        
        try:
            async with get_db_session() as db:
                api_call_entry = JenkinsApiCallTable(
                    session_id=session_id,
                    user_id=user_id,
                    ai_interaction_id=ai_interaction_id,
                    endpoint=endpoint,
                    method=method,
                    permission_required=permission_required,
                    permission_granted=False,  # Will be updated on completion
                    request_body=request_body
                )
                
                db.add(api_call_entry)
                await db.commit()
                await db.refresh(api_call_entry)
                
                logger.info("Jenkins API call audit started",
                           call_id=api_call_entry.id,
                           endpoint=endpoint,
                           user_id=user_id)
                
                return api_call_entry.id
                
        except Exception as e:
            logger.error("Failed to log Jenkins API call start",
                        error=str(e),
                        endpoint=endpoint,
                        user_id=user_id)
            return 0
    
    async def log_jenkins_api_call_complete(
        self,
        call_id: int,
        status_code: int,
        response_body: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
        permission_granted: bool = True,
        error_details: Optional[str] = None
    ) -> bool:
        """Log Jenkins API call completion"""
        
        try:
            if call_id == 0:  # Skip if initial logging failed
                return False
                
            async with get_db_session() as db:
                stmt = (
                    update(JenkinsApiCallTable)
                    .where(JenkinsApiCallTable.id == call_id)
                    .values(
                        status_code=status_code,
                        response_body=response_body,
                        execution_time_ms=execution_time_ms,
                        permission_granted=permission_granted,
                        error_details=error_details
                    )
                )
                
                await db.execute(stmt)
                await db.commit()
                
                logger.info("Jenkins API call audit completed",
                           call_id=call_id,
                           status_code=status_code,
                           permission_granted=permission_granted)
                
                return True
                
        except Exception as e:
            logger.error("Failed to log Jenkins API call completion",
                        error=str(e),
                        call_id=call_id)
            return False
    
    async def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "medium",
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Log security event"""
        
        try:
            async with get_db_session() as db:
                security_event = SecurityEventTable(
                    event_type=event_type,
                    user_id=user_id,
                    session_id=session_id,
                    source_ip=source_ip,
                    user_agent=user_agent,
                    details=details,
                    severity=severity,
                    resolved=False
                )
                
                db.add(security_event)
                await db.commit()
                await db.refresh(security_event)
                
                # Log to structured logger for immediate alerting
                log_level = logger.error if severity in ["high", "critical"] else logger.warning
                log_level("SECURITY_EVENT",
                         event_id=security_event.id,
                         event_type=event_type,
                         user_id=user_id,
                         session_id=session_id,
                         severity=severity,
                         details=details)
                
                return True
                
        except Exception as e:
            logger.error("Failed to log security event",
                        error=str(e),
                        event_type=event_type,
                        user_id=user_id)
            return False
    
    async def get_user_audit_history(
        self,
        user_id: str,
        hours_back: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit history for a user"""
        
        try:
            async with get_db_session() as db:
                # Calculate time threshold
                time_threshold = datetime.utcnow() - timedelta(hours=hours_back)
                
                # Query audit logs
                stmt = (
                    select(AuditLogTable)
                    .where(
                        AuditLogTable.user_id == user_id,
                        AuditLogTable.timestamp >= time_threshold
                    )
                    .order_by(AuditLogTable.timestamp.desc())
                    .limit(limit)
                )
                
                result = await db.execute(stmt)
                audit_entries = result.scalars().all()
                
                # Convert to dict format
                history = []
                for entry in audit_entries:
                    history.append({
                        "id": entry.id,
                        "timestamp": entry.timestamp.isoformat(),
                        "session_id": entry.session_id,
                        "user_query": entry.user_query,
                        "ai_response": entry.ai_response,
                        "intent_detected": entry.intent_detected,
                        "success": entry.success,
                        "response_time_ms": entry.response_time_ms,
                        "error_message": entry.error_message
                    })
                
                return history
                
        except Exception as e:
            logger.error("Failed to get user audit history",
                        error=str(e),
                        user_id=user_id)
            return []
    
    async def get_security_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get security events with filtering"""
        
        try:
            async with get_db_session() as db:
                # Build query
                stmt = select(SecurityEventTable)
                
                # Apply filters
                conditions = []
                if user_id:
                    conditions.append(SecurityEventTable.user_id == user_id)
                if event_type:
                    conditions.append(SecurityEventTable.event_type == event_type)
                if severity:
                    conditions.append(SecurityEventTable.severity == severity)
                
                time_threshold = datetime.utcnow() - timedelta(hours=hours_back)
                conditions.append(SecurityEventTable.timestamp >= time_threshold)
                
                if conditions:
                    stmt = stmt.where(*conditions)
                
                stmt = stmt.order_by(SecurityEventTable.timestamp.desc()).limit(limit)
                
                result = await db.execute(stmt)
                events = result.scalars().all()
                
                # Convert to dict format
                security_events = []
                for event in events:
                    security_events.append({
                        "id": event.id,
                        "timestamp": event.timestamp.isoformat(),
                        "event_type": event.event_type,
                        "user_id": event.user_id,
                        "session_id": event.session_id,
                        "severity": event.severity,
                        "details": event.details,
                        "resolved": event.resolved,
                        "source_ip": event.source_ip
                    })
                
                return security_events
                
        except Exception as e:
            logger.error("Failed to get security events",
                        error=str(e),
                        user_id=user_id,
                        event_type=event_type)
            return []
    
    async def get_audit_statistics(
        self, 
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """Get audit statistics for monitoring"""
        
        try:
            async with get_db_session() as db:
                time_threshold = datetime.utcnow() - timedelta(hours=hours_back)
                
                # Total interactions
                total_interactions = await db.scalar(
                    select(func.count(AuditLogTable.id))
                    .where(AuditLogTable.timestamp >= time_threshold)
                )
                
                # Successful interactions
                successful_interactions = await db.scalar(
                    select(func.count(AuditLogTable.id))
                    .where(
                        AuditLogTable.timestamp >= time_threshold,
                        AuditLogTable.success == True
                    )
                )
                
                # Failed interactions
                failed_interactions = await db.scalar(
                    select(func.count(AuditLogTable.id))
                    .where(
                        AuditLogTable.timestamp >= time_threshold,
                        AuditLogTable.success == False
                    )
                )
                
                # Unique users
                unique_users = await db.scalar(
                    select(func.count(func.distinct(AuditLogTable.user_id)))
                    .where(AuditLogTable.timestamp >= time_threshold)
                )
                
                # Security events by severity
                security_events_high = await db.scalar(
                    select(func.count(SecurityEventTable.id))
                    .where(
                        SecurityEventTable.timestamp >= time_threshold,
                        SecurityEventTable.severity == "high"
                    )
                )
                
                security_events_critical = await db.scalar(
                    select(func.count(SecurityEventTable.id))
                    .where(
                        SecurityEventTable.timestamp >= time_threshold,
                        SecurityEventTable.severity == "critical"
                    )
                )
                
                # Average response time
                avg_response_time = await db.scalar(
                    select(func.avg(AuditLogTable.response_time_ms))
                    .where(
                        AuditLogTable.timestamp >= time_threshold,
                        AuditLogTable.response_time_ms.isnot(None)
                    )
                )
                
                return {
                    "total_interactions": total_interactions or 0,
                    "successful_interactions": successful_interactions or 0,
                    "failed_interactions": failed_interactions or 0,
                    "success_rate": (successful_interactions / total_interactions * 100) if total_interactions else 0,
                    "unique_users": unique_users or 0,
                    "security_events_high": security_events_high or 0,
                    "security_events_critical": security_events_critical or 0,
                    "average_response_time_ms": int(avg_response_time) if avg_response_time else 0,
                    "time_period_hours": hours_back
                }
                
        except Exception as e:
            logger.error("Failed to get audit statistics", error=str(e))
            return {
                "total_interactions": 0,
                "successful_interactions": 0,
                "failed_interactions": 0,
                "success_rate": 0,
                "unique_users": 0,
                "security_events_high": 0,
                "security_events_critical": 0,
                "average_response_time_ms": 0,
                "time_period_hours": hours_back
            }
    
    async def cleanup_old_audit_logs(self, days_to_keep: int = 90) -> int:
        """Clean up old audit logs based on retention policy"""
        
        try:
            async with get_db_session() as db:
                # Calculate cutoff date
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # Delete old audit entries
                audit_delete_stmt = (
                    delete(AuditLogTable)
                    .where(AuditLogTable.timestamp < cutoff_date)
                )
                audit_result = await db.execute(audit_delete_stmt)
                
                # Delete old API call logs
                api_delete_stmt = (
                    delete(JenkinsApiCallTable)
                    .where(JenkinsApiCallTable.timestamp < cutoff_date)
                )
                api_result = await db.execute(api_delete_stmt)
                
                # Delete old security events (keep unresolved ones)
                security_delete_stmt = (
                    delete(SecurityEventTable)
                    .where(
                        SecurityEventTable.timestamp < cutoff_date,
                        SecurityEventTable.resolved == True
                    )
                )
                security_result = await db.execute(security_delete_stmt)
                
                await db.commit()
                
                total_deleted = (
                    audit_result.rowcount + 
                    api_result.rowcount + 
                    security_result.rowcount
                )
                
                logger.info("Audit log cleanup completed",
                           audit_logs_deleted=audit_result.rowcount,
                           api_logs_deleted=api_result.rowcount,
                           security_events_deleted=security_result.rowcount,
                           total_deleted=total_deleted,
                           days_kept=days_to_keep)
                
                return total_deleted
                
        except Exception as e:
            logger.error("Failed to cleanup old audit logs", error=str(e))
            return 0