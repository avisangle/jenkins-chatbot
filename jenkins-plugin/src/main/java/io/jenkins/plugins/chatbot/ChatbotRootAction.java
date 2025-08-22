package io.jenkins.plugins.chatbot;

import hudson.Extension;
import hudson.model.RootAction;
import jenkins.model.Jenkins;
import org.kohsuke.stapler.StaplerRequest;
import org.kohsuke.stapler.StaplerResponse;

import javax.servlet.ServletException;
import java.io.IOException;
import java.util.logging.Logger;

/**
 * Adds "AI Assistant" link to Jenkins main sidebar navigation
 * This is what makes the chatbot accessible from the main Jenkins interface
 */
@Extension
public class ChatbotRootAction implements RootAction {
    
    private static final Logger LOGGER = Logger.getLogger(ChatbotRootAction.class.getName());
    
    @Override
    public String getIconFileName() {
        // Only show if user has permission to use chatbot
        if (Jenkins.get().hasPermission(ChatbotPlugin.USE_CHATBOT)) {
            return "symbol-chat";  // Use Jenkins built-in chat symbol
        }
        return null; // Hide from sidebar if no permission
    }
    
    @Override
    public String getDisplayName() {
        return "AI Assistant";
    }
    
    @Override
    public String getUrlName() {
        return "ai-assistant";
    }
    
    /**
     * Main entry point - redirects to chat interface
     */
    public void doIndex(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        // Check permission
        Jenkins.get().checkPermission(ChatbotPlugin.USE_CHATBOT);
        
        // Forward to chat interface
        ChatbotPlugin plugin = ChatbotPlugin.getInstance();
        if (plugin != null) {
            plugin.doChatInterface(req, rsp);
        } else {
            LOGGER.severe("ChatbotPlugin instance not found");
            rsp.sendError(500, "Plugin not properly initialized");
        }
    }
    
    /**
     * Health check endpoint for the sidebar action
     */
    public void doHealth(StaplerRequest req, StaplerResponse rsp) throws IOException {
        Jenkins.get().checkPermission(ChatbotPlugin.USE_CHATBOT);
        
        ChatbotPlugin plugin = ChatbotPlugin.getInstance();
        if (plugin != null) {
            plugin.doHealth(req, rsp);
        } else {
            rsp.sendError(500, "Plugin not available");
        }
    }
    
    /**
     * API endpoint for session creation and chat operations
     */
    public void doApi(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        LOGGER.info("ChatbotRootAction - doApi called: method=" + req.getMethod() + ", pathInfo='" + req.getPathInfo() + "', requestURI='" + req.getRequestURI() + "'");
        
        Jenkins.get().checkPermission(ChatbotPlugin.USE_CHATBOT);
        
        // Handle POST requests for chat messages directly
        if ("POST".equals(req.getMethod()) && (req.getPathInfo() == null || req.getPathInfo().equals("/") || req.getPathInfo().isEmpty())) {
            LOGGER.info("ChatbotRootAction - Handling chat message directly");
            handleChatMessage(req, rsp);
            return;
        }
        
        ChatbotPlugin plugin = ChatbotPlugin.getInstance();
        if (plugin != null) {
            LOGGER.info("ChatbotRootAction - Forwarding to ChatbotPlugin.doApi");
            plugin.doApi(req, rsp);
        } else {
            LOGGER.severe("ChatbotRootAction - ChatbotPlugin instance not available");
            rsp.sendError(500, "Plugin not available");
        }
    }
    
    /**
     * WebSocket endpoint through RootAction
     */
    public void doChatWebSocket(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        Jenkins.get().checkPermission(ChatbotPlugin.USE_CHATBOT);
        
        ChatbotPlugin plugin = ChatbotPlugin.getInstance();
        if (plugin != null) {
            plugin.doChatWebSocket(req, rsp);
        } else {
            rsp.sendError(500, "Plugin not available");
        }
    }
    
    /**
     * Direct handler for session creation - bypasses complex path routing
     */
    public void doApiSession(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        LOGGER.info("ChatbotRootAction - doApiSession called directly: method=" + req.getMethod());
        
        Jenkins.get().checkPermission(ChatbotPlugin.USE_CHATBOT);
        
        if ("POST".equals(req.getMethod())) {
            // Handle session creation directly
            handleSessionCreation(req, rsp);
        } else {
            rsp.sendError(405, "Method not allowed");
        }
    }
    
    /**
     * Handle session creation directly without path parsing
     */
    private void handleSessionCreation(StaplerRequest req, StaplerResponse rsp) throws IOException {
        try {
            LOGGER.info("ChatbotRootAction - Creating session for user");
            
            hudson.model.User currentUser = hudson.model.User.current();
            if (currentUser == null) {
                rsp.sendError(401, "Authentication required");
                return;
            }
            
            // Create session using ChatSessionManager for consistency
            ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().createSession(currentUser);
            
            rsp.setContentType("application/json");
            rsp.setStatus(201);
            
            // Use session's last activity for expiry calculation (like ChatApiHandler does)
            long expiresAt = session.getLastActivity() + (15 * 60 * 1000); // 15 minutes from last activity
            
            String sessionResponse = String.format(
                "{\"sessionId\":\"%s\",\"userId\":\"%s\",\"userToken\":\"%s\",\"permissions\":[\"Job.READ\",\"Job.BUILD\",\"Job.CREATE\"],\"createdAt\":%d,\"expiresAt\":%d}",
                session.getSessionId(),
                session.getUserId(),
                session.getUserToken(),
                session.getCreatedAt(),
                expiresAt
            );
            
            rsp.getWriter().write(sessionResponse);
            LOGGER.info("ChatbotRootAction - Session created successfully for user: " + currentUser.getId());
            
        } catch (Exception e) {
            LOGGER.severe("ChatbotRootAction - Error creating session: " + e.getMessage());
            rsp.sendError(500, "Internal server error");
        }
    }
    
    /**
     * Handle chat message directly without complex routing
     */
    private void handleChatMessage(StaplerRequest req, StaplerResponse rsp) throws IOException {
        try {
            LOGGER.info("ChatbotRootAction - Processing chat message");
            
            hudson.model.User currentUser = hudson.model.User.current();
            if (currentUser == null) {
                rsp.sendError(401, "Authentication required");
                return;
            }
            
            // Parse request body to get chat message
            String requestBody = req.getReader().lines()
                .reduce("", (accumulator, actual) -> accumulator + actual);
            
            if (requestBody.isEmpty()) {
                rsp.sendError(400, "Request body is required");
                return;
            }
            
            // Parse JSON request
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            java.util.Map<String, Object> requestData = mapper.readValue(requestBody, java.util.Map.class);
            
            String message = (String) requestData.get("message");
            String sessionId = (String) requestData.get("session_id");
            String userToken = (String) requestData.get("user_token");
            
            if (message == null || message.trim().isEmpty()) {
                rsp.sendError(400, "Message is required");
                return;
            }
            
            // Get user permissions
            java.util.List<String> permissions = getUserPermissions(currentUser);
            
            // Create AI Agent request
            AIAgentRequest aiRequest = new AIAgentRequest();
            aiRequest.sessionId = sessionId != null ? sessionId : java.util.UUID.randomUUID().toString();
            aiRequest.userId = currentUser.getId();
            aiRequest.userToken = userToken != null ? userToken : generateUserToken(currentUser.getId(), aiRequest.sessionId);
            aiRequest.permissions = permissions;
            aiRequest.message = message;
            aiRequest.context = createUserContext(currentUser);
            
            // Send to AI Agent service
            AIAgentClient aiClient = new AIAgentClient();
            AIAgentResponse aiResponse;
            
            try {
                aiResponse = aiClient.sendMessage(aiRequest);
                LOGGER.info("ChatbotRootAction - AI Agent response received");
            } catch (AIAgentClient.AIAgentException e) {
                LOGGER.warning("ChatbotRootAction - AI Agent error: " + e.getMessage());
                // Fallback to local processing
                aiResponse = createLocalFallbackResponse(message, permissions);
            }
            
            // Convert AI response to JSON and send
            rsp.setContentType("application/json");
            rsp.setStatus(200);
            
            String responseJson = mapper.writeValueAsString(java.util.Map.of(
                "response", aiResponse.response,
                "actions", aiResponse.actions != null ? aiResponse.actions : java.util.Collections.emptyList(),
                "sessionState", aiResponse.sessionState != null ? aiResponse.sessionState : java.util.Collections.emptyMap(),
                "timestamp", System.currentTimeMillis()
            ));
            
            rsp.getWriter().write(responseJson);
            LOGGER.info("ChatbotRootAction - Chat message processed successfully");
            
        } catch (Exception e) {
            LOGGER.severe("ChatbotRootAction - Error processing chat message: " + e.getMessage());
            e.printStackTrace();
            
            String errorResponse = String.format(
                "{\"error\":\"internal_error\",\"message\":\"Failed to process your message. Please try again.\",\"code\":500,\"timestamp\":%d}",
                System.currentTimeMillis()
            );
            rsp.setStatus(500);
            rsp.setContentType("application/json");
            rsp.getWriter().write(errorResponse);
        }
    }
    
    /**
     * Get user permissions for Jenkins operations
     */
    private java.util.List<String> getUserPermissions(hudson.model.User user) {
        java.util.List<String> permissions = new java.util.ArrayList<>();
        
        try {
            // Check common Jenkins permissions
            if (Jenkins.get().hasPermission(hudson.model.Item.READ)) {
                permissions.add("Job.READ");
            }
            if (Jenkins.get().hasPermission(hudson.model.Item.BUILD)) {
                permissions.add("Job.BUILD");
            }
            if (Jenkins.get().hasPermission(hudson.model.Item.CREATE)) {
                permissions.add("Job.CREATE");
            }
            if (Jenkins.get().hasPermission(hudson.model.Item.DELETE)) {
                permissions.add("Job.DELETE");
            }
            if (Jenkins.get().hasPermission(hudson.model.Item.CONFIGURE)) {
                permissions.add("Job.CONFIGURE");
            }
            if (Jenkins.get().hasPermission(jenkins.model.Jenkins.ADMINISTER)) {
                permissions.add("Jenkins.ADMINISTER");
            }
            
        } catch (Exception e) {
            LOGGER.warning("Error checking user permissions: " + e.getMessage());
            // Fallback to basic read permission
            permissions.add("Job.READ");
        }
        
        return permissions;
    }
    
    /**
     * Generate user token for AI Agent authentication
     */
    private String generateUserToken(String userId, String sessionId) {
        long currentTime = System.currentTimeMillis();
        long expiryTime = currentTime + (15 * 60 * 1000); // 15 minutes
        
        return String.format("jenkins_token_%s_%s_%d", userId, sessionId, expiryTime);
    }
    
    /**
     * Create user context for AI Agent
     */
    private java.util.Map<String, Object> createUserContext(hudson.model.User user) {
        java.util.Map<String, Object> context = new java.util.HashMap<>();
        
        context.put("jenkins_url", Jenkins.get().getRootUrl());
        context.put("current_user", user.getId());
        context.put("user_display_name", user.getDisplayName());
        context.put("jenkins_version", Jenkins.VERSION);
        
        // Add current workspace info if available
        try {
            context.put("workspace", System.getProperty("JENKINS_HOME"));
        } catch (Exception e) {
            // Ignore if not available
        }
        
        return context;
    }
    
    /**
     * Create fallback response when AI Agent is unavailable
     */
    private AIAgentResponse createLocalFallbackResponse(String message, java.util.List<String> permissions) {
        AIAgentResponse response = new AIAgentResponse();
        response.actions = java.util.Collections.emptyList();
        response.sessionState = java.util.Collections.emptyMap();
        
        String lowerMessage = message.toLowerCase();
        
        // Simple pattern matching for fallback responses
        if (lowerMessage.contains("help") || lowerMessage.contains("what can")) {
            response.response = "I can help you with Jenkins tasks like:\n" +
                              "• Triggering builds\n" +
                              "• Checking build status\n" +
                              "• Viewing build logs\n" +
                              "• Listing accessible jobs\n\n" +
                              "Try asking me something like 'trigger the frontend build' or 'show me recent builds'.";
        } else if (lowerMessage.contains("trigger") || lowerMessage.contains("build") || lowerMessage.contains("start")) {
            if (permissions.contains("Job.BUILD")) {
                response.response = "I'd like to help trigger a build, but I'm having trouble connecting to my AI service. " +
                                  "You can manually trigger builds by going to your job page and clicking 'Build Now'.";
            } else {
                response.response = "I'd help you trigger builds, but you don't have the required permissions. " +
                                  "Please contact your Jenkins administrator if you need build permissions.";
            }
        } else if (lowerMessage.contains("status") || lowerMessage.contains("check")) {
            response.response = "I'd help you check build status, but I'm experiencing connectivity issues. " +
                              "You can check build status by visiting your job pages and looking at the build history.";
        } else if (lowerMessage.contains("log") || lowerMessage.contains("console")) {
            response.response = "I'd show you build logs, but I'm having service issues right now. " +
                              "You can access build logs by clicking on a build number and selecting 'Console Output'.";
        } else if (lowerMessage.contains("list") || lowerMessage.contains("jobs")) {
            response.response = "I'd list your accessible jobs, but my AI service is temporarily unavailable. " +
                              "You can see all your jobs on the Jenkins dashboard.";
        } else {
            response.response = "I'm sorry, I'm having trouble connecting to my AI service right now. " +
                              "Please try again later or use the Jenkins UI directly for immediate needs.";
        }
        
        return response;
    }
    
    /**
     * Check if chatbot is enabled and properly configured
     */
    public boolean isChatbotAvailable() {
        try {
            // Check if user has permission
            if (!Jenkins.get().hasPermission(ChatbotPlugin.USE_CHATBOT)) {
                return false;
            }
            
            // Check if plugin is properly initialized
            ChatbotPlugin plugin = ChatbotPlugin.getInstance();
            return plugin != null;
            
        } catch (Exception e) {
            LOGGER.warning("Error checking chatbot availability: " + e.getMessage());
            return false;
        }
    }
}