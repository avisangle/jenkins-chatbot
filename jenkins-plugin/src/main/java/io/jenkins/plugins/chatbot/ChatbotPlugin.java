package io.jenkins.plugins.chatbot;

import hudson.Plugin;
import hudson.model.User;
import hudson.security.Permission;
import hudson.security.PermissionGroup;
import hudson.security.PermissionScope;
import jenkins.model.Jenkins;
import org.kohsuke.stapler.StaplerRequest;
import org.kohsuke.stapler.StaplerResponse;

import javax.servlet.ServletException;
import java.io.IOException;
import java.util.logging.Logger;

/**
 * Main plugin class for Jenkins AI Chatbot
 * Provides AI-powered natural language interface to Jenkins operations
 */
public class ChatbotPlugin extends Plugin {
    
    private static final Logger LOGGER = Logger.getLogger(ChatbotPlugin.class.getName());
    
    public static final PermissionGroup CHATBOT_PERMISSIONS = new PermissionGroup(ChatbotPlugin.class, Messages._ChatbotPlugin_PermissionGroup_Title());
    public static final Permission USE_CHATBOT = new Permission(CHATBOT_PERMISSIONS, "Use", Messages._ChatbotPlugin_UsePermission_Description(), Permission.READ, PermissionScope.JENKINS);
    
    @Override
    public void start() throws Exception {
        super.start();
        LOGGER.info("Jenkins AI Chatbot Plugin started");
        
        // Initialize plugin components
        ChatSessionManager.getInstance().initialize();
        SecurityManager.getInstance().initialize();
    }
    
    @Override
    public void stop() throws Exception {
        LOGGER.info("Jenkins AI Chatbot Plugin stopping");
        
        // Cleanup resources
        ChatSessionManager.getInstance().shutdown();
        
        super.stop();
    }
    
    /**
     * Handles chat interface requests
     */
    public void doChatInterface(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        // Check if user has permission to use chatbot
        Jenkins.get().checkPermission(USE_CHATBOT);
        
        User currentUser = User.current();
        if (currentUser == null) {
            rsp.sendError(401, "Authentication required");
            return;
        }
        
        // Forward to chat interface page
        req.getView(this, "chat-interface.jelly").forward(req, rsp);
    }
    
    /**
     * WebSocket endpoint for real-time chat
     */
    public void doChatWebSocket(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        Jenkins.get().checkPermission(USE_CHATBOT);
        
        // Upgrade HTTP connection to WebSocket
        ChatWebSocketHandler handler = new ChatWebSocketHandler();
        handler.handleWebSocketUpgrade(req, rsp);
    }
    
    /**
     * REST API endpoint for chat messages
     */
    public void doApi(StaplerRequest req, StaplerResponse rsp) throws IOException, ServletException {
        LOGGER.info("ChatbotPlugin - doApi called: method=" + req.getMethod() + ", pathInfo='" + req.getPathInfo() + "', requestURI='" + req.getRequestURI() + "'");
        
        Jenkins.get().checkPermission(USE_CHATBOT);
        
        ChatApiHandler apiHandler = new ChatApiHandler();
        LOGGER.info("ChatbotPlugin - Delegating to ChatApiHandler");
        apiHandler.handleRequest(req, rsp);
    }
    
    /**
     * Health check endpoint
     */
    public void doHealth(StaplerRequest req, StaplerResponse rsp) throws IOException {
        rsp.setContentType("application/json");
        rsp.setStatus(200);
        rsp.getWriter().write("{\"status\":\"ok\",\"version\":\"1.0.2\"}");
    }
    
    public static ChatbotPlugin getInstance() {
        return Jenkins.get().getPlugin(ChatbotPlugin.class);
    }
}