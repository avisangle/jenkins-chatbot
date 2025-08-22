package io.jenkins.plugins.chatbot;

import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import hudson.security.Permission;
import jenkins.model.Jenkins;
import org.acegisecurity.Authentication;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.UUID;
import java.util.List;
import java.util.ArrayList;
import java.util.logging.Logger;

/**
 * Manages chat sessions and user context for AI Chatbot
 * Handles session lifecycle, user permissions, and security context
 */
public class ChatSessionManager {
    
    private static final Logger LOGGER = Logger.getLogger(ChatSessionManager.class.getName());
    private static final ChatSessionManager INSTANCE = new ChatSessionManager();
    
    private final ConcurrentHashMap<String, ChatSession> activeSessions = new ConcurrentHashMap<>();
    private final ScheduledExecutorService cleanupExecutor = Executors.newSingleThreadScheduledExecutor();
    
    // Session configuration
    private static final long SESSION_TIMEOUT_MINUTES = 15;
    private static final long CLEANUP_INTERVAL_MINUTES = 5;
    private static final int MAX_CONVERSATION_LENGTH = 50;
    
    private ChatSessionManager() {}
    
    public static ChatSessionManager getInstance() {
        return INSTANCE;
    }
    
    public void initialize() {
        // Schedule periodic cleanup of expired sessions
        cleanupExecutor.scheduleWithFixedDelay(
            this::cleanupExpiredSessions,
            CLEANUP_INTERVAL_MINUTES,
            CLEANUP_INTERVAL_MINUTES,
            TimeUnit.MINUTES
        );
        
        LOGGER.info("ChatSessionManager initialized");
    }
    
    public void shutdown() {
        cleanupExecutor.shutdown();
        activeSessions.clear();
        LOGGER.info("ChatSessionManager shutdown");
    }
    
    /**
     * Creates a new chat session for the current user
     */
    public ChatSession createSession(User user) {
        if (user == null) {
            throw new IllegalArgumentException("User cannot be null");
        }
        
        String sessionId = UUID.randomUUID().toString();
        
        // Extract user permissions
        List<String> permissions = extractUserPermissions(user);
        
        // Generate short-lived user token
        String userToken = generateUserToken(user, sessionId);
        
        ChatSession session = new ChatSession(
            sessionId,
            user.getId(),
            permissions,
            userToken,
            System.currentTimeMillis(),
            SESSION_TIMEOUT_MINUTES * 60 * 1000 // Convert to milliseconds
        );
        
        activeSessions.put(sessionId, session);
        
        // Extract expiry for logging
        try {
            String[] parts = userToken.split("_");
            if (parts.length >= 4) {
                long tokenExpiry = Long.parseLong(parts[parts.length - 1]);
                LOGGER.info("Created chat session " + sessionId + " for user " + user.getId() + 
                           " with token expiry at " + new java.util.Date(tokenExpiry));
            }
        } catch (Exception e) {
            LOGGER.info("Created chat session " + sessionId + " for user " + user.getId());
        }
        
        return session;
    }
    
    /**
     * Retrieves an existing chat session
     */
    public ChatSession getSession(String sessionId) {
        ChatSession session = activeSessions.get(sessionId);
        
        if (session == null) {
            return null;
        }
        
        // Check if session is expired
        if (session.isExpired()) {
            removeSession(sessionId);
            return null;
        }
        
        // Update last activity
        session.updateLastActivity();
        return session;
    }
    
    /**
     * Gets existing session for user or creates new one if none exists or token is expiring soon
     */
    public ChatSession getOrCreateSession(User user) {
        if (user == null) {
            throw new IllegalArgumentException("User cannot be null");
        }
        
        // Look for existing active session for this user
        for (ChatSession session : activeSessions.values()) {
            if (session.getUserId().equals(user.getId()) && !session.isExpired()) {
                // Check if token is expiring soon (within 2 minutes)
                if (session.isTokenExpiringSoon()) {
                    LOGGER.info("Session token expiring soon for user " + user.getId() + ", creating new session");
                    // Remove the expiring session
                    removeSession(session.getSessionId());
                    // Create new session with fresh token
                    return createSession(user);
                }
                
                session.updateLastActivity();
                return session;
            }
        }
        
        // No active session found, create new one
        return createSession(user);
    }
    
    /**
     * Removes a chat session
     */
    public void removeSession(String sessionId) {
        ChatSession removed = activeSessions.remove(sessionId);
        if (removed != null) {
            LOGGER.info("Removed chat session " + sessionId);
        }
    }
    
    /**
     * Validates session and user permissions for a specific action
     */
    public boolean validateSessionAction(String sessionId, String requiredPermission, String resource) {
        ChatSession session = getSession(sessionId);
        if (session == null) {
            return false;
        }
        
        // Check if user has the required permission
        return session.hasPermission(requiredPermission);
    }
    
    /**
     * Extracts user permissions from Jenkins ACL
     */
    private List<String> extractUserPermissions(User user) {
        List<String> permissions = new ArrayList<>();
        Authentication auth = user.impersonate();
        
        try (ACLContext context = ACL.as(auth)) {
            Jenkins jenkins = Jenkins.get();
            
            // Check common permissions
            if (jenkins.hasPermission(Jenkins.READ)) {
                permissions.add("Jenkins.READ");
            }
            if (jenkins.hasPermission(Jenkins.ADMINISTER)) {
                permissions.add("Jenkins.ADMINISTER");
            }
            
            // Check job-related permissions
            permissions.addAll(extractJobPermissions(auth));
            
            // Check build permissions
            permissions.addAll(extractBuildPermissions(auth));
            
        } catch (Exception e) {
            LOGGER.warning("Failed to extract permissions for user " + user.getId() + ": " + e.getMessage());
        }
        
        return permissions;
    }
    
    private List<String> extractJobPermissions(Authentication auth) {
        List<String> jobPermissions = new ArrayList<>();
        
        try (ACLContext context = ACL.as(auth)) {
            Jenkins jenkins = Jenkins.get();
            
            if (jenkins.hasPermission(hudson.model.Item.READ)) {
                jobPermissions.add("Job.READ");
            }
            if (jenkins.hasPermission(hudson.model.Item.BUILD)) {
                jobPermissions.add("Job.BUILD");
            }
            if (jenkins.hasPermission(hudson.model.Item.CREATE)) {
                jobPermissions.add("Job.CREATE");
            }
            if (jenkins.hasPermission(hudson.model.Item.DELETE)) {
                jobPermissions.add("Job.DELETE");
            }
            if (jenkins.hasPermission(hudson.model.Item.CONFIGURE)) {
                jobPermissions.add("Job.CONFIGURE");
            }
        } catch (Exception e) {
            LOGGER.warning("Failed to extract job permissions: " + e.getMessage());
        }
        
        return jobPermissions;
    }
    
    private List<String> extractBuildPermissions(Authentication auth) {
        List<String> buildPermissions = new ArrayList<>();
        
        try (ACLContext context = ACL.as(auth)) {
            Jenkins jenkins = Jenkins.get();
            
            if (jenkins.hasPermission(hudson.model.Run.DELETE)) {
                buildPermissions.add("Build.DELETE");
            }
            if (jenkins.hasPermission(hudson.model.Run.UPDATE)) {
                buildPermissions.add("Build.UPDATE");
            }
        } catch (Exception e) {
            LOGGER.warning("Failed to extract build permissions: " + e.getMessage());
        }
        
        return buildPermissions;
    }
    
    /**
     * Generates a short-lived token for user authentication with AI Agent
     */
    private String generateUserToken(User user, String sessionId) {
        // In a real implementation, this would generate a JWT or secure token
        // For MVP, using a simple token format
        long expiry = System.currentTimeMillis() + (SESSION_TIMEOUT_MINUTES * 60 * 1000);
        return "jenkins_token_" + user.getId() + "_" + sessionId + "_" + expiry;
    }
    
    /**
     * Cleans up expired sessions and sessions with expired tokens
     */
    private void cleanupExpiredSessions() {
        int cleanedUpExpired = 0;
        int cleanedUpExpiredTokens = 0;
        
        // Create a copy of keySet to avoid ConcurrentModificationException
        java.util.Set<String> sessionIds = new java.util.HashSet<>(activeSessions.keySet());
        
        for (String sessionId : sessionIds) {
            ChatSession session = activeSessions.get(sessionId);
            if (session != null) {
                if (session.isExpired()) {
                    activeSessions.remove(sessionId);
                    cleanedUpExpired++;
                } else if (session.isTokenExpiringSoon()) {
                    // Clean up sessions with tokens that have already expired
                    // (expired soon check has a 2-minute buffer, so tokens that are truly expired will be caught here)
                    try {
                        String[] parts = session.getUserToken().split("_");
                        if (parts.length >= 4) {
                            long tokenExpiry = Long.parseLong(parts[parts.length - 1]);
                            if (System.currentTimeMillis() > tokenExpiry) {
                                activeSessions.remove(sessionId);
                                cleanedUpExpiredTokens++;
                            }
                        }
                    } catch (NumberFormatException e) {
                        // Remove sessions with unparseable tokens
                        activeSessions.remove(sessionId);
                        cleanedUpExpiredTokens++;
                    }
                }
            }
        }
        
        if (cleanedUpExpired > 0 || cleanedUpExpiredTokens > 0) {
            LOGGER.info("Cleaned up " + cleanedUpExpired + " expired sessions and " + 
                       cleanedUpExpiredTokens + " sessions with expired tokens");
        }
    }
    
    /**
     * Returns the number of active sessions
     */
    public int getActiveSessionCount() {
        return activeSessions.size();
    }
    
    /**
     * Chat session data class
     */
    public static class ChatSession {
        private final String sessionId;
        private final String userId;
        private final List<String> permissions;
        private final String userToken;
        private final long createdAt;
        private final long timeoutMs;
        private volatile long lastActivity;
        
        public ChatSession(String sessionId, String userId, List<String> permissions, 
                         String userToken, long createdAt, long timeoutMs) {
            this.sessionId = sessionId;
            this.userId = userId;
            this.permissions = new ArrayList<>(permissions);
            this.userToken = userToken;
            this.createdAt = createdAt;
            this.timeoutMs = timeoutMs;
            this.lastActivity = createdAt;
        }
        
        public String getSessionId() { return sessionId; }
        public String getUserId() { return userId; }
        public List<String> getPermissions() { return new ArrayList<>(permissions); }
        public String getUserToken() { return userToken; }
        public long getCreatedAt() { return createdAt; }
        public long getLastActivity() { return lastActivity; }
        
        public boolean hasPermission(String permission) {
            return permissions.contains(permission);
        }
        
        public boolean isExpired() {
            return System.currentTimeMillis() - lastActivity > timeoutMs;
        }
        
        /**
         * Check if the session token is expiring soon (within 2 minutes)
         * This is important for proactive token renewal before 401 errors occur
         */
        public boolean isTokenExpiringSoon() {
            // Extract expiry from token: jenkins_token_userId_sessionId_expiry
            try {
                String[] parts = userToken.split("_");
                if (parts.length >= 4) {
                    long tokenExpiry = Long.parseLong(parts[parts.length - 1]);
                    long currentTime = System.currentTimeMillis();
                    long timeUntilExpiry = tokenExpiry - currentTime;
                    
                    // Return true if token expires within 2 minutes (120,000 ms)
                    return timeUntilExpiry < 120000;
                }
            } catch (NumberFormatException e) {
                // If we can't parse the token, assume it's expiring soon to be safe
                return true;
            }
            return false;
        }
        
        public void updateLastActivity() {
            this.lastActivity = System.currentTimeMillis();
        }
    }
}