package io.jenkins.plugins.chatbot;

import com.fasterxml.jackson.databind.ObjectMapper;
import hudson.model.User;
import org.eclipse.jetty.websocket.api.Session;
import org.eclipse.jetty.websocket.api.WebSocketAdapter;
import org.eclipse.jetty.websocket.servlet.WebSocketServlet;
import org.eclipse.jetty.websocket.servlet.WebSocketServletFactory;
import org.kohsuke.stapler.StaplerRequest;
import org.kohsuke.stapler.StaplerResponse;

import javax.servlet.ServletException;
import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;
import java.util.Map;
import java.util.List;

/**
 * WebSocket handler for real-time chat communication
 * Manages WebSocket connections and message routing to AI Agent
 */
public class ChatWebSocketHandler extends WebSocketServlet {
    
    private static final Logger LOGGER = Logger.getLogger(ChatWebSocketHandler.class.getName());
    private static final ConcurrentHashMap<String, ChatWebSocket> activeConnections = new ConcurrentHashMap<>();
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    @Override
    public void configure(WebSocketServletFactory factory) {
        factory.register(ChatWebSocket.class);
    }
    
    public void handleWebSocketUpgrade(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        // Validate user authentication
        User currentUser = User.current();
        if (currentUser == null) {
            rsp.sendError(401, "Authentication required");
            return;
        }
        
        // Create or get existing chat session
        ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().createSession(currentUser);
        
        // Store session ID in request attributes for WebSocket connection
        req.setAttribute("chatSessionId", session.getSessionId());
        req.setAttribute("userId", currentUser.getId());
        
        // Let Jetty handle the WebSocket upgrade
        this.service(req, rsp);
    }
    
    /**
     * WebSocket connection handler
     */
    public static class ChatWebSocket extends WebSocketAdapter {
        
        private String sessionId;
        private String userId;
        private AIAgentClient aiClient;
        
        @Override
        public void onWebSocketConnect(Session session) {
            super.onWebSocketConnect(session);
            
            try {
                // Extract session information from upgrade request parameters
                Map<String, List<String>> params = session.getUpgradeRequest().getParameterMap();
                this.sessionId = params.containsKey("chatSessionId") && !params.get("chatSessionId").isEmpty() 
                    ? params.get("chatSessionId").get(0) : null;
                this.userId = params.containsKey("userId") && !params.get("userId").isEmpty() 
                    ? params.get("userId").get(0) : null;
                
                if (sessionId == null || userId == null) {
                    session.close(1008, "Missing session information");
                    return;
                }
                
                // Initialize AI client for this connection
                this.aiClient = new AIAgentClient();
                
                // Register this connection
                activeConnections.put(sessionId, this);
                
                LOGGER.info("WebSocket connected for user " + userId + " with session " + sessionId);
                
                // Send welcome message
                sendWelcomeMessage();
                
            } catch (Exception e) {
                LOGGER.severe("Error establishing WebSocket connection: " + e.getMessage());
                session.close(1011, "Server error");
            }
        }
        
        @Override
        public void onWebSocketText(String message) {
            try {
                LOGGER.info("Received message from user " + userId + ": " + message);
                
                // Parse incoming message
                ChatMessage chatMessage = objectMapper.readValue(message, ChatMessage.class);
                
                // Validate session is still active
                ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().getSession(sessionId);
                if (session == null) {
                    sendErrorMessage("Session expired. Please refresh the page.");
                    getSession().close(1008, "Session expired");
                    return;
                }
                
                // Process message through AI Agent
                processMessageAsync(chatMessage);
                
            } catch (Exception e) {
                LOGGER.severe("Error processing WebSocket message: " + e.getMessage());
                sendErrorMessage("Sorry, I encountered an error processing your message. Please try again.");
            }
        }
        
        @Override
        public void onWebSocketClose(int statusCode, String reason) {
            super.onWebSocketClose(statusCode, reason);
            
            // Remove from active connections
            activeConnections.remove(sessionId);
            
            LOGGER.info("WebSocket closed for session " + sessionId + " (code: " + statusCode + ", reason: " + reason + ")");
        }
        
        @Override
        public void onWebSocketError(Throwable cause) {
            super.onWebSocketError(cause);
            LOGGER.severe("WebSocket error for session " + sessionId + ": " + cause.getMessage());
        }
        
        private void sendWelcomeMessage() {
            try {
                ChatMessage welcome = new ChatMessage();
                welcome.type = "assistant";
                welcome.content = "Hello! I'm your Jenkins AI assistant. I can help you with building, deploying, and managing your Jenkins jobs. What would you like to do?";
                welcome.timestamp = System.currentTimeMillis();
                
                String json = objectMapper.writeValueAsString(welcome);
                getSession().getRemote().sendString(json);
                
            } catch (Exception e) {
                LOGGER.severe("Error sending welcome message: " + e.getMessage());
            }
        }
        
        private void sendErrorMessage(String error) {
            try {
                ChatMessage errorMsg = new ChatMessage();
                errorMsg.type = "error";
                errorMsg.content = error;
                errorMsg.timestamp = System.currentTimeMillis();
                
                String json = objectMapper.writeValueAsString(errorMsg);
                getSession().getRemote().sendString(json);
                
            } catch (Exception e) {
                LOGGER.severe("Error sending error message: " + e.getMessage());
            }
        }
        
        private void processMessageAsync(ChatMessage message) {
            // Process in separate thread to avoid blocking WebSocket
            new Thread(() -> {
                try {
                    // Send typing indicator
                    sendTypingIndicator(true);
                    
                    // Get user session context
                    ChatSessionManager.ChatSession session = ChatSessionManager.getInstance().getSession(sessionId);
                    
                    // Prepare AI request
                    AIAgentRequest request = new AIAgentRequest();
                    request.sessionId = sessionId;
                    request.userId = userId;
                    request.message = message.content;
                    request.userToken = session.getUserToken();
                    request.permissions = session.getPermissions();
                    
                    // Send to AI Agent
                    AIAgentResponse response = aiClient.sendMessage(request);
                    
                    // Stop typing indicator
                    sendTypingIndicator(false);
                    
                    // Send AI response back to user
                    sendAIResponse(response);
                    
                } catch (Exception e) {
                    LOGGER.severe("Error processing message through AI Agent: " + e.getMessage());
                    sendTypingIndicator(false);
                    sendErrorMessage("Sorry, I'm having trouble connecting to my AI brain. Please try again later.");
                }
            }).start();
        }
        
        private void sendTypingIndicator(boolean isTyping) {
            try {
                ChatMessage typing = new ChatMessage();
                typing.type = "typing";
                typing.content = isTyping ? "true" : "false";
                typing.timestamp = System.currentTimeMillis();
                
                String json = objectMapper.writeValueAsString(typing);
                getSession().getRemote().sendString(json);
                
            } catch (Exception e) {
                LOGGER.warning("Error sending typing indicator: " + e.getMessage());
            }
        }
        
        private void sendAIResponse(AIAgentResponse response) {
            try {
                ChatMessage aiMessage = new ChatMessage();
                aiMessage.type = "assistant";
                aiMessage.content = response.response;
                aiMessage.timestamp = System.currentTimeMillis();
                aiMessage.actions = response.actions;
                
                String json = objectMapper.writeValueAsString(aiMessage);
                getSession().getRemote().sendString(json);
                
            } catch (Exception e) {
                LOGGER.severe("Error sending AI response: " + e.getMessage());
                sendErrorMessage("I processed your request but had trouble sending the response. Please try again.");
            }
        }
    }
    
    /**
     * Message data structure for WebSocket communication
     */
    public static class ChatMessage {
        public String type; // "user", "assistant", "error", "typing"
        public String content;
        public long timestamp;
        public Object actions; // Optional actions from AI response
    }
    
    /**
     * Broadcasts a message to all active WebSocket connections for a user
     */
    public static void broadcastToUser(String userId, ChatMessage message) {
        for (ChatWebSocket connection : activeConnections.values()) {
            if (userId.equals(connection.userId)) {
                try {
                    String json = objectMapper.writeValueAsString(message);
                    connection.getSession().getRemote().sendString(json);
                } catch (Exception e) {
                    LOGGER.warning("Error broadcasting to user " + userId + ": " + e.getMessage());
                }
            }
        }
    }
    
    public static int getActiveConnectionCount() {
        return activeConnections.size();
    }
}