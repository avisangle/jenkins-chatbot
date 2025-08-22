package io.jenkins.plugins.chatbot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;

import java.util.List;
import java.util.logging.Logger;

/**
 * Client for communicating with AI Agent service
 * Handles HTTP requests to AI Agent and response processing
 */
public class AIAgentClient {
    
    private static final Logger LOGGER = Logger.getLogger(AIAgentClient.class.getName());
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    // Configuration endpoints
    private static final String CHAT_ENDPOINT = "/api/v1/chat";
    private static final int REQUEST_TIMEOUT_MS = 35000; // 35 seconds (slightly longer than AI service timeout)
    private static final int CONNECTION_TIMEOUT_MS = 10000; // 10 seconds for connection
    private static final int SOCKET_TIMEOUT_MS = 35000; // 35 seconds for socket operations
    
    private final CloseableHttpClient httpClient;
    
    public AIAgentClient() {
        org.apache.http.client.config.RequestConfig requestConfig = org.apache.http.client.config.RequestConfig.custom()
            .setConnectTimeout(CONNECTION_TIMEOUT_MS)
            .setSocketTimeout(SOCKET_TIMEOUT_MS)
            .setConnectionRequestTimeout(REQUEST_TIMEOUT_MS)
            .build();
            
        this.httpClient = HttpClients.custom()
            .setDefaultRequestConfig(requestConfig)
            .setMaxConnTotal(50)
            .setMaxConnPerRoute(10)
            .build();
    }
    
    /**
     * Sends a chat message to the AI Agent service
     */
    public AIAgentResponse sendMessage(AIAgentRequest request) throws Exception {
        ChatbotGlobalConfiguration config = ChatbotGlobalConfiguration.get();
        String baseUrl = config != null ? config.getAiAgentUrl() : "http://localhost:8000";
        String url = baseUrl + CHAT_ENDPOINT;
        
        HttpPost httpPost = new HttpPost(url);
        httpPost.setHeader("Content-Type", "application/json");
        httpPost.setHeader("Authorization", "Bearer " + request.userToken);
        httpPost.setHeader("X-Session-ID", request.sessionId);
        httpPost.setHeader("X-User-ID", request.userId);
        
        // Convert request to JSON
        String requestJson = objectMapper.writeValueAsString(request);
        httpPost.setEntity(new StringEntity(requestJson));
        
        LOGGER.info("Sending request to AI Agent: " + url);
        
        try (CloseableHttpResponse response = httpClient.execute(httpPost)) {
            int statusCode = response.getStatusLine().getStatusCode();
            String responseBody = EntityUtils.toString(response.getEntity());
            
            if (statusCode == 200) {
                LOGGER.info("Received successful response from AI Agent");
                return objectMapper.readValue(responseBody, AIAgentResponse.class);
            } else {
                LOGGER.warning("AI Agent returned error status " + statusCode + ": " + responseBody);
                
                // Try to parse error response
                try {
                    ErrorResponse errorResponse = objectMapper.readValue(responseBody, ErrorResponse.class);
                    throw new AIAgentException("AI Agent error: " + errorResponse.message);
                } catch (Exception e) {
                    throw new AIAgentException("AI Agent request failed with status " + statusCode);
                }
            }
        } catch (Exception e) {
            LOGGER.severe("Error communicating with AI Agent: " + e.getMessage());
            
            // Return fallback response for better user experience
            return createFallbackResponse(request.message);
        }
    }
    
    /**
     * Creates a fallback response when AI Agent is unavailable
     */
    private AIAgentResponse createFallbackResponse(String userMessage) {
        AIAgentResponse response = new AIAgentResponse();
        response.response = "I'm sorry, but I'm having trouble connecting to my AI brain right now. " +
                          "You can try again later or use the Jenkins UI directly for immediate needs.";
        response.actions = null;
        response.sessionState = null;
        
        // Add some simple pattern matching for common requests
        String lowerMessage = userMessage.toLowerCase();
        if (lowerMessage.contains("build") || lowerMessage.contains("trigger")) {
            response.response += "\n\nTo trigger a build manually, go to your job page and click 'Build Now'.";
        } else if (lowerMessage.contains("status") || lowerMessage.contains("log")) {
            response.response += "\n\nTo check build status, visit the job page and look at the build history.";
        }
        
        return response;
    }
    
    /**
     * Validates AI Agent service health
     */
    public boolean isHealthy() {
        try {
            ChatbotGlobalConfiguration config = ChatbotGlobalConfiguration.get();
            String baseUrl = config != null ? config.getAiAgentUrl() : "http://localhost:8000";
            String url = baseUrl + "/health";
            
            org.apache.http.client.methods.HttpGet httpGet = new org.apache.http.client.methods.HttpGet(url);
            
            try (CloseableHttpResponse response = httpClient.execute(httpGet)) {
                return response.getStatusLine().getStatusCode() == 200;
            }
        } catch (Exception e) {
            LOGGER.warning("AI Agent health check failed: " + e.getMessage());
            return false;
        }
    }
    
    /**
     * Custom exception for AI Agent communication errors
     */
    public static class AIAgentException extends Exception {
        public AIAgentException(String message) {
            super(message);
        }
        
        public AIAgentException(String message, Throwable cause) {
            super(message, cause);
        }
    }
    
    /**
     * Error response structure
     */
    public static class ErrorResponse {
        public String error;
        public String message;
        public int code;
    }
}

/**
 * Request structure for AI Agent communication
 */
class AIAgentRequest {
    @com.fasterxml.jackson.annotation.JsonProperty("session_id")
    public String sessionId;
    @com.fasterxml.jackson.annotation.JsonProperty("user_id")
    public String userId;
    @com.fasterxml.jackson.annotation.JsonProperty("user_token")
    public String userToken;
    public List<String> permissions;
    public String message;
    public Object context; // Additional context like current job, workspace info, etc.
}

/**
 * Response structure from AI Agent
 */
class AIAgentResponse {
    public String response;
    public List<Object> actions; // Planned Jenkins API calls or other actions
    @com.fasterxml.jackson.annotation.JsonProperty("session_state")
    public Object sessionState; // Updated session state
    @com.fasterxml.jackson.annotation.JsonProperty("intent_detected")
    public String intentDetected; // Detected user intent
    @com.fasterxml.jackson.annotation.JsonProperty("confidence_score")
    public Float confidenceScore; // Response confidence (0.0-1.0)
    @com.fasterxml.jackson.annotation.JsonProperty("response_time_ms")
    public Integer responseTimeMs; // Processing time in milliseconds
    @com.fasterxml.jackson.annotation.JsonProperty("tool_results")
    public List<Object> toolResults; // Tool execution results for context memory
}