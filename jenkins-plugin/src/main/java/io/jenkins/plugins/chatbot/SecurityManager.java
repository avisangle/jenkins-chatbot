package io.jenkins.plugins.chatbot;

import hudson.model.User;
import hudson.security.ACL;
import hudson.security.Permission;
import jenkins.model.Jenkins;
import org.springframework.security.core.Authentication;

import java.util.logging.Logger;
import java.util.Set;
import java.util.HashSet;
import java.util.Arrays;

/**
 * Security manager for AI Chatbot
 * Handles permission validation, security policies, and audit logging
 */
public class SecurityManager {
    
    private static final Logger LOGGER = Logger.getLogger(SecurityManager.class.getName());
    private static final SecurityManager INSTANCE = new SecurityManager();
    
    // Sensitive operations that require additional validation
    private static final Set<String> SENSITIVE_PERMISSIONS = new HashSet<>(Arrays.asList(
        "Jenkins.ADMINISTER",
        "Job.DELETE",
        "Job.CREATE",
        "Build.DELETE",
        "Jenkins.RUN_SCRIPTS"
    ));
    
    // Operations that should be blocked from AI automation
    private static final Set<String> BLOCKED_OPERATIONS = new HashSet<>(Arrays.asList(
        "user_creation",
        "permission_modification",
        "plugin_installation",
        "system_configuration"
    ));
    
    private SecurityManager() {}
    
    public static SecurityManager getInstance() {
        return INSTANCE;
    }
    
    public void initialize() {
        LOGGER.info("SecurityManager initialized");
    }
    
    /**
     * Validates if a user can perform a specific action through the AI chatbot
     */
    public ValidationResult validateAction(String sessionId, String action, String resource, String userId) {
        try {
            // Get user session
            ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().getSession(sessionId);
            if (session == null) {
                return ValidationResult.failure("Invalid or expired session");
            }
            
            // Verify session belongs to the user
            if (!session.getUserId().equals(userId)) {
                logSecurityEvent("session_mismatch", userId, sessionId, "Session does not belong to user");
                return ValidationResult.failure("Session validation failed");
            }
            
            // Check if operation is blocked from AI automation
            if (BLOCKED_OPERATIONS.contains(action)) {
                logSecurityEvent("blocked_operation", userId, sessionId, "Attempted blocked operation: " + action);
                return ValidationResult.failure("This operation cannot be performed through the chatbot");
            }
            
            // Get required permission for the action
            String requiredPermission = getRequiredPermission(action, resource);
            if (requiredPermission == null) {
                logSecurityEvent("unknown_action", userId, sessionId, "Unknown action attempted: " + action);
                return ValidationResult.failure("Unknown operation");
            }
            
            // Check if user has the required permission
            if (!session.hasPermission(requiredPermission)) {
                logSecurityEvent("permission_denied", userId, sessionId, 
                    String.format("Missing permission %s for action %s on resource %s", 
                    requiredPermission, action, resource));
                return ValidationResult.failure(
                    String.format("Insufficient permissions. Required: %s", requiredPermission)
                );
            }
            
            // Additional validation for sensitive operations
            if (SENSITIVE_PERMISSIONS.contains(requiredPermission)) {
                ValidationResult sensitiveResult = validateSensitiveOperation(action, resource, userId, session);
                if (!sensitiveResult.isValid()) {
                    return sensitiveResult;
                }
            }
            
            // Log successful validation
            logSecurityEvent("action_validated", userId, sessionId, 
                String.format("Validated action %s on resource %s", action, resource));
            
            return ValidationResult.success();
            
        } catch (Exception e) {
            LOGGER.severe("Security validation failed: " + e.getMessage());
            logSecurityEvent("validation_error", userId, sessionId, "Security validation error: " + e.getMessage());
            return ValidationResult.failure("Security validation error");
        }
    }
    
    /**
     * Maps actions to required Jenkins permissions
     */
    private String getRequiredPermission(String action, String resource) {
        switch (action.toLowerCase()) {
            case "build_job":
            case "trigger_build":
                return "Job.BUILD";
            case "read_job":
            case "list_jobs":
            case "get_job_status":
                return "Job.READ";
            case "create_job":
                return "Job.CREATE";
            case "delete_job":
                return "Job.DELETE";
            case "configure_job":
                return "Job.CONFIGURE";
            case "read_build":
            case "get_build_log":
            case "get_build_status":
                return "Job.READ";
            case "delete_build":
                return "Build.DELETE";
            case "cancel_build":
                return "Job.BUILD";
            case "read_console":
                return "Job.READ";
            default:
                return null;
        }
    }
    
    /**
     * Additional validation for sensitive operations
     */
    private ValidationResult validateSensitiveOperation(String action, String resource, String userId, 
                                                       ChatSessionManager.ChatSession session) {
        
        // For sensitive operations, we might want to:
        // 1. Require recent authentication
        // 2. Check for multi-factor authentication
        // 3. Validate specific resource access
        // 4. Apply rate limiting
        
        long sessionAge = System.currentTimeMillis() - session.getCreatedAt();
        long maxSensitiveSessionAge = 5 * 60 * 1000; // 5 minutes
        
        if (sessionAge > maxSensitiveSessionAge) {
            logSecurityEvent("stale_session_sensitive", userId, session.getSessionId(), 
                "Sensitive operation attempted with stale session");
            return ValidationResult.failure("Please re-authenticate for sensitive operations");
        }
        
        // Additional checks could be added here
        return ValidationResult.success();
    }
    
    /**
     * Validates user token from AI Agent requests
     */
    public boolean validateUserToken(String token, String expectedUserId) {
        if (token == null || !token.startsWith("jenkins_token_")) {
            return false;
        }
        
        try {
            // Parse token components
            String[] parts = token.split("_");
            if (parts.length < 5) {
                return false;
            }
            
            String tokenUserId = parts[2];
            String sessionId = parts[3];
            long expiry = Long.parseLong(parts[4]);
            
            // Check if token is expired
            if (System.currentTimeMillis() > expiry) {
                logSecurityEvent("expired_token", tokenUserId, sessionId, "Expired token used");
                return false;
            }
            
            // Check if user matches
            if (!tokenUserId.equals(expectedUserId)) {
                logSecurityEvent("token_user_mismatch", tokenUserId, sessionId, "Token user mismatch");
                return false;
            }
            
            // Verify session exists and is valid
            ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().getSession(sessionId);
            if (session == null || !session.getUserId().equals(tokenUserId)) {
                logSecurityEvent("invalid_session_token", tokenUserId, sessionId, "Invalid session for token");
                return false;
            }
            
            return true;
            
        } catch (Exception e) {
            LOGGER.warning("Token validation failed: " + e.getMessage());
            return false;
        }
    }
    
    /**
     * Logs security events for audit purposes
     */
    private void logSecurityEvent(String eventType, String userId, String sessionId, String details) {
        // In a real implementation, this would write to audit database
        LOGGER.warning(String.format("SECURITY_EVENT: %s | User: %s | Session: %s | Details: %s", 
            eventType, userId, sessionId, details));
        
        // TODO: Implement database logging as per implementation plan
    }
    
    /**
     * Result class for validation operations
     */
    public static class ValidationResult {
        private final boolean valid;
        private final String message;
        
        private ValidationResult(boolean valid, String message) {
            this.valid = valid;
            this.message = message;
        }
        
        public static ValidationResult success() {
            return new ValidationResult(true, null);
        }
        
        public static ValidationResult failure(String message) {
            return new ValidationResult(false, message);
        }
        
        public boolean isValid() { return valid; }
        public String getMessage() { return message; }
    }
}