package io.jenkins.plugins.chatbot;

import com.fasterxml.jackson.databind.ObjectMapper;
import hudson.model.User;
import org.kohsuke.stapler.StaplerRequest;
import org.kohsuke.stapler.StaplerResponse;
import org.kohsuke.stapler.verb.POST;

import javax.servlet.ServletException;
import java.io.IOException;
import java.util.logging.Logger;

/**
 * REST API handler for chat operations
 * Provides HTTP endpoints for chat functionality alongside WebSocket interface
 */
public class ChatApiHandler {
    
    private static final Logger LOGGER = Logger.getLogger(ChatApiHandler.class.getName());
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    /**
     * Handles incoming API requests
     */
    public void handleRequest(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        String method = req.getMethod();
        String pathInfo = req.getPathInfo();
        
        // Debug logging to understand path routing
        LOGGER.info("ChatApiHandler - API request: method=" + method + ", pathInfo='" + pathInfo + "', requestURI='" + req.getRequestURI() + "', requestURL='" + req.getRequestURL() + "'");
        
        rsp.setContentType("application/json");
        
        try {
            switch (method.toUpperCase()) {
                case "POST":
                    handlePostRequest(req, rsp, pathInfo);
                    break;
                case "GET":
                    handleGetRequest(req, rsp, pathInfo);
                    break;
                default:
                    sendError(rsp, 405, "Method not allowed");
            }
        } catch (Exception e) {
            LOGGER.severe("API request handling error: " + e.getMessage());
            sendError(rsp, 500, "Internal server error");
        }
    }
    
    private void handlePostRequest(StaplerRequest req, StaplerResponse rsp, String pathInfo) throws IOException {
        LOGGER.info("ChatApiHandler - POST request pathInfo: '" + pathInfo + "', checking endpoints...");
        
        if (pathInfo == null || pathInfo.equals("/") || pathInfo.equals("/ai-assistant/api/") || pathInfo.endsWith("/api/")) {
            // POST /api - Send chat message
            LOGGER.info("ChatApiHandler - Routing to handleChatMessage");
            handleChatMessage(req, rsp);
        } else if (pathInfo.equals("/session")) {
            // POST /api/session - Create new session
            LOGGER.info("ChatApiHandler - Routing to handleCreateSession");
            handleCreateSession(req, rsp);
        } else {
            LOGGER.warning("ChatApiHandler - No endpoint found for pathInfo: '" + pathInfo + "'");
            sendError(rsp, 404, "Endpoint not found");
        }
    }
    
    private void handleGetRequest(StaplerRequest req, StaplerResponse rsp, String pathInfo) throws IOException {
        if (pathInfo != null && pathInfo.startsWith("/session/")) {
            // GET /api/session/{sessionId} - Get session state
            String sessionId = pathInfo.substring("/session/".length());
            handleGetSession(req, rsp, sessionId);
        } else if (pathInfo != null && pathInfo.equals("/health")) {
            // GET /api/health - Health check
            handleHealthCheck(req, rsp);
        } else {
            sendError(rsp, 404, "Endpoint not found");
        }
    }
    
    /**
     * Handles chat message submission via REST API
     */
    private void handleChatMessage(StaplerRequest req, StaplerResponse rsp) throws IOException {
        try {
            // Parse request body
            ChatRequest chatRequest = objectMapper.readValue(req.getInputStream(), ChatRequest.class);
            
            LOGGER.info("ChatApiHandler - Parsed chat request: sessionId=" + chatRequest.sessionId + 
                       ", userId=" + chatRequest.userId + ", message length=" + 
                       (chatRequest.message != null ? chatRequest.message.length() : "null"));
            
            // Validate required fields
            if (chatRequest.sessionId == null || chatRequest.message == null) {
                sendError(rsp, 400, "Missing required fields: sessionId, message");
                return;
            }
            
            // Get current user
            User currentUser = User.current();
            if (currentUser == null) {
                sendError(rsp, 401, "Authentication required");
                return;
            }
            
            // For MVP, process message using simple pattern matching
            LOGGER.info("ChatApiHandler - Processing message: '" + chatRequest.message + "' for user: " + currentUser.getId());
            
            // Process the message and generate appropriate response
            ChatResponse response = processUserMessage(chatRequest.message, currentUser);
            response.timestamp = System.currentTimeMillis();
            
            // Send response
            rsp.setStatus(200);
            objectMapper.writeValue(rsp.getWriter(), response);
            
            LOGGER.info("ChatApiHandler - Successfully processed chat message for user: " + currentUser.getId());
            
        } catch (Exception e) {
            LOGGER.severe("Error processing chat message: " + e.getMessage());
            e.printStackTrace();
            sendError(rsp, 500, "Internal server error: " + e.getMessage());
        }
    }
    
    /**
     * Process user message - tries AI Agent Service first, falls back to MVP pattern matching
     */
    private ChatResponse processUserMessage(String message, User currentUser) {
        ChatResponse response = new ChatResponse();
        response.actions = new java.util.ArrayList<>();
        response.sessionState = new java.util.HashMap<>();
        
        try {
            // Phase 3: Try AI Agent Service first
            LOGGER.info("Attempting to use AI Agent Service for user: " + currentUser.getId());
            
            // Create session if needed
            ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().getOrCreateSession(currentUser);
            
            // Build AI Agent request
            AIAgentRequest aiRequest = new AIAgentRequest();
            aiRequest.sessionId = session.getSessionId();
            aiRequest.userId = currentUser.getId();
            aiRequest.userToken = session.getUserToken();
            aiRequest.permissions = session.getPermissions();
            aiRequest.message = message;
            
            // Build context for AI Agent
            java.util.Map<String, Object> context = new java.util.HashMap<>();
            context.put("jenkins_url", jenkins.model.Jenkins.get().getRootUrl());
            context.put("user_display_name", currentUser.getDisplayName());
            
            // Add recent jobs context
            try {
                java.util.List<hudson.model.Job> userJobs = jenkins.model.Jenkins.get().getAllItems(hudson.model.Job.class);
                java.util.List<String> accessibleJobs = new java.util.ArrayList<>();
                for (hudson.model.Job job : userJobs) {
                    if (job.hasPermission(hudson.model.Item.READ) && accessibleJobs.size() < 10) {
                        accessibleJobs.add(job.getName());
                    }
                }
                context.put("accessible_jobs", accessibleJobs);
            } catch (Exception e) {
                LOGGER.warning("Failed to get accessible jobs for context: " + e.getMessage());
            }
            
            aiRequest.context = context;
            
            // Send to AI Agent Service
            AIAgentClient aiClient = new AIAgentClient();
            AIAgentResponse aiResponse = aiClient.sendMessage(aiRequest);
            
            // Convert AI Agent response to Jenkins plugin response
            response.response = aiResponse.response;
            response.actions = aiResponse.actions != null ? aiResponse.actions : new java.util.ArrayList<>();
            response.sessionState = aiResponse.sessionState != null ? aiResponse.sessionState : new java.util.HashMap<>();
            
            LOGGER.info("Successfully received response from AI Agent Service");
            return response;
            
        } catch (Exception e) {
            LOGGER.warning("AI Agent Service unavailable, falling back to MVP pattern matching: " + e.getMessage());
            
            // FALLBACK: Use existing MVP pattern matching when AI Agent is unavailable
            return processUserMessageFallback(message, currentUser);
        }
    }
    
    /**
     * Fallback message processing using MVP pattern matching (original implementation)
     */
    private ChatResponse processUserMessageFallback(String message, User currentUser) {
        ChatResponse response = new ChatResponse();
        response.actions = new java.util.ArrayList<>();
        response.sessionState = new java.util.HashMap<>();
        
        String lowerMessage = message.toLowerCase().trim();
        
        try {
            // MVP Story 5: Help and Discovery
            if (isHelpQuery(lowerMessage)) {
                response.response = generateHelpResponse(currentUser);
            }
            // MVP Story 2: Build Status Query  
            else if (isBuildStatusQuery(lowerMessage)) {
                response.response = getBuildStatus(currentUser);
            }
            // MVP Story 3: Job Listing
            else if (isJobListQuery(lowerMessage)) {
                response.response = getJobList(currentUser);
            }
            // MVP Story 1: Trigger Build
            else if (isBuildTriggerQuery(lowerMessage)) {
                response.response = triggerBuild(lowerMessage, currentUser);
            }
            // MVP Story 4: Build Log Access
            else if (isBuildLogQuery(lowerMessage)) {
                response.response = getBuildLog(lowerMessage, currentUser);
            }
            // Default response
            else {
                response.response = "I didn't understand that request. Try asking:\n" +
                                  "• \"list my jobs\" - to see available jobs\n" +
                                  "• \"what's the status of my latest build?\" - for build status\n" +
                                  "• \"trigger a build for [job-name]\" - to start a build\n" +
                                  "• \"what can you do?\" - for help\n" +
                                  "• \"show me the log for build #123\" - for build logs";
            }
        } catch (Exception e) {
            LOGGER.severe("Error processing user message in fallback mode: " + e.getMessage());
            response.response = "Sorry, I encountered an error processing your request. Please try again.";
        }
        
        return response;
    }
    
    /**
     * MVP Story 5: Help and Discovery
     */
    private boolean isHelpQuery(String message) {
        return message.contains("help") || message.contains("what can you do") || 
               message.contains("commands") || message.contains("how to");
    }
    
    private String generateHelpResponse(User user) {
        StringBuilder help = new StringBuilder();
        help.append("Hi ").append(user.getDisplayName()).append("! I can help you with Jenkins tasks:\n\n");
        help.append("**Build Operations:**\n");
        help.append("• \"trigger a build for [job-name]\" - Start a new build\n");
        help.append("• \"build the frontend\" - Trigger specific job builds\n\n");
        help.append("**Status & Information:**\n");
        help.append("• \"what's the status of my latest build?\" - Check recent builds\n");
        help.append("• \"list my jobs\" - Show available jobs\n");
        help.append("• \"show me the log for build #123\" - View build logs\n\n");
        help.append("**Tips:**\n");
        help.append("• I understand natural language - just ask normally!\n");
        help.append("• I only show jobs you have permission to access\n");
        help.append("• Try being specific with job names for better results");
        return help.toString();
    }
    
    /**
     * MVP Story 2: Build Status Query
     */
    private boolean isBuildStatusQuery(String message) {
        return (message.contains("status") || message.contains("build")) && 
               (message.contains("latest") || message.contains("last") || message.contains("recent") || 
                message.contains("my build") || message.contains("how") || message.contains("check"));
    }
    
    private String getBuildStatus(User user) {
        try {
            jenkins.model.Jenkins jenkinsInstance = jenkins.model.Jenkins.get();
            java.util.List<hudson.model.Job> jobs = jenkinsInstance.getAllItems(hudson.model.Job.class);
            
            StringBuilder status = new StringBuilder();
            status.append("**Recent Build Status for ").append(user.getDisplayName()).append(":**\n\n");
            
            int count = 0;
            for (hudson.model.Job job : jobs) {
                if (job.hasPermission(hudson.model.Item.READ) && count < 5) {
                    hudson.model.Run lastBuild = job.getLastBuild();
                    if (lastBuild != null) {
                        String buildStatus = lastBuild.getResult() != null ? lastBuild.getResult().toString() : "RUNNING";
                        String duration = hudson.Util.getTimeSpanString(lastBuild.getDuration());
                        
                        status.append("• **").append(job.getDisplayName()).append("** - Build #").append(lastBuild.getNumber());
                        status.append(" - ").append(buildStatus);
                        if (!"RUNNING".equals(buildStatus)) {
                            status.append(" (").append(duration).append(")");
                        }
                        status.append("\n");
                        count++;
                    }
                }
            }
            
            if (count == 0) {
                status.append("No recent builds found. You may not have access to any jobs or no builds have been run yet.");
            }
            
            return status.toString();
        } catch (Exception e) {
            return "Error retrieving build status: " + e.getMessage();
        }
    }
    
    /**
     * MVP Story 3: Permission-Aware Job Listing
     */
    private boolean isJobListQuery(String message) {
        return (message.contains("list") || message.contains("show")) && 
               (message.contains("job") || message.contains("all"));
    }
    
    private String getJobList(User user) {
        try {
            jenkins.model.Jenkins jenkinsInstance = jenkins.model.Jenkins.get();
            java.util.List<hudson.model.Job> jobs = jenkinsInstance.getAllItems(hudson.model.Job.class);
            
            StringBuilder jobList = new StringBuilder();
            jobList.append("**Jobs accessible to ").append(user.getDisplayName()).append(":**\n\n");
            
            int count = 0;
            for (hudson.model.Job job : jobs) {
                if (job.hasPermission(hudson.model.Item.READ)) {
                    hudson.model.Run lastBuild = job.getLastBuild();
                    String lastStatus = "Never built";
                    if (lastBuild != null) {
                        lastStatus = lastBuild.getResult() != null ? lastBuild.getResult().toString() : "RUNNING";
                        lastStatus += " (#" + lastBuild.getNumber() + ")";
                    }
                    
                    jobList.append("• **").append(job.getDisplayName()).append("**");
                    jobList.append(" - Last: ").append(lastStatus);
                    if (job.hasPermission(hudson.model.Item.BUILD)) {
                        jobList.append(" ✓ Can build");
                    }
                    jobList.append("\n");
                    count++;
                }
            }
            
            if (count == 0) {
                jobList.append("No jobs found. You may not have permission to view any jobs.");
            } else {
                jobList.append("\n*Tip: Say 'trigger a build for [job-name]' to start a build*");
            }
            
            return jobList.toString();
        } catch (Exception e) {
            return "Error retrieving job list: " + e.getMessage();
        }
    }
    
    /**
     * MVP Story 1: Trigger Build
     */
    private boolean isBuildTriggerQuery(String message) {
        return (message.contains("trigger") || message.contains("start") || message.contains("run") || 
                message.contains("build")) && 
               !message.contains("status") && !message.contains("log");
    }
    
    private String triggerBuild(String message, User user) {
        try {
            // Extract job name from message
            String jobName = extractJobName(message);
            if (jobName == null) {
                return "Please specify which job you'd like to build. For example: \"trigger a build for my-job-name\"";
            }
            
            jenkins.model.Jenkins jenkinsInstance = jenkins.model.Jenkins.get();
            hudson.model.Job job = jenkinsInstance.getItemByFullName(jobName, hudson.model.Job.class);
            
            if (job == null) {
                // Try to find job by partial name match
                java.util.List<hudson.model.Job> allJobs = jenkinsInstance.getAllItems(hudson.model.Job.class);
                for (hudson.model.Job j : allJobs) {
                    if (j.getName().toLowerCase().contains(jobName.toLowerCase()) && 
                        j.hasPermission(hudson.model.Item.READ)) {
                        job = j;
                        break;
                    }
                }
            }
            
            if (job == null) {
                return "Job '" + jobName + "' not found. Use 'list my jobs' to see available jobs.";
            }
            
            if (!job.hasPermission(hudson.model.Item.BUILD)) {
                return "You don't have permission to build '" + job.getDisplayName() + "'.";
            }
            
            if (!job.isBuildable()) {
                return "Job '" + job.getDisplayName() + "' is not buildable (may be disabled).";
            }
            
            // For MVP, return a placeholder response - build triggering will be implemented in next phase
            return "🔧 **Build trigger found for '" + job.getDisplayName() + "'**\n\n" +
                   "Build triggering functionality is being implemented. For now, you can:\n" +
                   "• Use the Jenkins UI to trigger builds manually\n" +
                   "• Check build status with 'what's the status of my latest build?'\n" +
                   "• View build logs with 'show me the log for build #123'\n\n" +
                   "*Build triggering via chat will be available in the next update.*";
            
        } catch (Exception e) {
            return "Error triggering build: " + e.getMessage();
        }
    }
    
    /**
     * MVP Story 4: Build Log Access
     */
    private boolean isBuildLogQuery(String message) {
        return message.contains("log") && (message.contains("build") || message.contains("#"));
    }
    
    private String getBuildLog(String message, User user) {
        try {
            // Extract build number and job name
            String buildNumber = extractBuildNumber(message);
            if (buildNumber == null) {
                return "Please specify a build number. For example: \"show me the log for build #123\"";
            }
            
            // For MVP, show logs from the most recent job with that build number
            jenkins.model.Jenkins jenkinsInstance = jenkins.model.Jenkins.get();
            java.util.List<hudson.model.Job> jobs = jenkinsInstance.getAllItems(hudson.model.Job.class);
            
            for (hudson.model.Job job : jobs) {
                if (job.hasPermission(hudson.model.Item.READ)) {
                    hudson.model.Run build = job.getBuildByNumber(Integer.parseInt(buildNumber));
                    if (build != null) {
                        try {
                            java.util.List<String> logLines = build.getLog(50); // Last 50 lines
                            String log = String.join("\n", logLines);
                            return "**Build Log for " + job.getDisplayName() + " #" + buildNumber + ":**\n\n" +
                                   "```\n" + log + "\n```\n\n" +
                                   "*[View full log in Jenkins UI]*";
                        } catch (Exception e) {
                            return "Found build #" + buildNumber + " for " + job.getDisplayName() + 
                                   " but couldn't retrieve log: " + e.getMessage();
                        }
                    }
                }
            }
            
            return "Build #" + buildNumber + " not found in any accessible jobs.";
            
        } catch (Exception e) {
            return "Error retrieving build log: " + e.getMessage();
        }
    }
    
    /**
     * Extract job name from natural language message
     */
    private String extractJobName(String message) {
        // Simple pattern matching for "build [job-name]" or "trigger [job-name]"
        String[] patterns = {
            "build\\s+(?:the\\s+)?([\\w-]+)",
            "trigger\\s+(?:a\\s+build\\s+for\\s+)?([\\w-]+)",
            "start\\s+(?:the\\s+)?([\\w-]+)",
            "run\\s+(?:the\\s+)?([\\w-]+)"
        };
        
        for (String pattern : patterns) {
            java.util.regex.Pattern p = java.util.regex.Pattern.compile(pattern, java.util.regex.Pattern.CASE_INSENSITIVE);
            java.util.regex.Matcher m = p.matcher(message);
            if (m.find()) {
                return m.group(1);
            }
        }
        return null;
    }
    
    /**
     * Extract build number from message
     */
    private String extractBuildNumber(String message) {
        java.util.regex.Pattern pattern = java.util.regex.Pattern.compile("#(\\d+)");
        java.util.regex.Matcher matcher = pattern.matcher(message);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return null;
    }
    
    /**
     * Handles session creation
     */
    private void handleCreateSession(StaplerRequest req, StaplerResponse rsp) throws IOException {
        try {
            User currentUser = User.current();
            if (currentUser == null) {
                sendError(rsp, 401, "Authentication required");
                return;
            }
            
            // Create new session
            ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().createSession(currentUser);
            
            // Prepare response
            SessionResponse response = new SessionResponse();
            response.sessionId = session.getSessionId();
            response.userId = session.getUserId();
            response.permissions = session.getPermissions();
            response.createdAt = session.getCreatedAt();
            response.expiresAt = session.getLastActivity() + (15 * 60 * 1000); // 15 minutes from last activity
            
            rsp.setStatus(201);
            objectMapper.writeValue(rsp.getWriter(), response);
            
        } catch (Exception e) {
            LOGGER.severe("Error creating session: " + e.getMessage());
            sendError(rsp, 500, "Internal server error");
        }
    }
    
    /**
     * Handles session state retrieval
     */
    private void handleGetSession(StaplerRequest req, StaplerResponse rsp, String sessionId) throws IOException {
        try {
            User currentUser = User.current();
            if (currentUser == null) {
                sendError(rsp, 401, "Authentication required");
                return;
            }
            
            ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().getSession(sessionId);
            if (session == null) {
                sendError(rsp, 404, "Session not found or expired");
                return;
            }
            
            // Verify session belongs to current user
            if (!session.getUserId().equals(currentUser.getId())) {
                sendError(rsp, 403, "Session does not belong to current user");
                return;
            }
            
            // Prepare response
            SessionResponse response = new SessionResponse();
            response.sessionId = session.getSessionId();
            response.userId = session.getUserId();
            response.permissions = session.getPermissions();
            response.createdAt = session.getCreatedAt();
            response.lastActivity = session.getLastActivity();
            response.expiresAt = session.getLastActivity() + (15 * 60 * 1000);
            
            rsp.setStatus(200);
            objectMapper.writeValue(rsp.getWriter(), response);
            
        } catch (Exception e) {
            LOGGER.severe("Error retrieving session: " + e.getMessage());
            sendError(rsp, 500, "Internal server error");
        }
    }
    
    /**
     * Handles health check requests
     */
    private void handleHealthCheck(StaplerRequest req, StaplerResponse rsp) throws IOException {
        try {
            // Check AI Agent health
            AIAgentClient aiClient = new AIAgentClient();
            boolean aiHealthy = aiClient.isHealthy();
            
            // Check session manager health
            int activeSessions = ChatSessionManager.getInstance().getActiveSessionCount();
            
            HealthResponse response = new HealthResponse();
            response.status = "ok";
            response.aiAgentHealthy = aiHealthy;
            response.activeSessions = activeSessions;
            response.timestamp = System.currentTimeMillis();
            
            rsp.setStatus(200);
            objectMapper.writeValue(rsp.getWriter(), response);
            
        } catch (Exception e) {
            LOGGER.severe("Error in health check: " + e.getMessage());
            sendError(rsp, 500, "Internal server error");
        }
    }
    
    private void sendError(StaplerResponse rsp, int statusCode, String message) throws IOException {
        ErrorResponse error = new ErrorResponse();
        error.error = "error";
        error.message = message;
        error.code = statusCode;
        error.timestamp = System.currentTimeMillis();
        
        rsp.setStatus(statusCode);
        objectMapper.writeValue(rsp.getWriter(), error);
    }
    
    // Request/Response data structures
    
    public static class ChatRequest {
        @com.fasterxml.jackson.annotation.JsonProperty("session_id")
        public String sessionId;
        @com.fasterxml.jackson.annotation.JsonProperty("user_id")
        public String userId;
        @com.fasterxml.jackson.annotation.JsonProperty("user_token")
        public String userToken;
        public String message;
        public Object context;
        public java.util.List<String> permissions;
    }
    
    public static class ChatResponse {
        public String response;
        public Object actions;
        public Object sessionState;
        public long timestamp;
    }
    
    public static class SessionResponse {
        public String sessionId;
        public String userId;
        public java.util.List<String> permissions;
        public long createdAt;
        public long lastActivity;
        public long expiresAt;
    }
    
    public static class HealthResponse {
        public String status;
        public boolean aiAgentHealthy;
        public int activeSessions;
        public long timestamp;
    }
    
    public static class ErrorResponse {
        public String error;
        public String message;
        public int code;
        public long timestamp;
    }
}