package io.jenkins.plugins.chatbot;

import hudson.Extension;
import hudson.util.FormValidation;
import jenkins.model.GlobalConfiguration;
import net.sf.json.JSONObject;
import org.kohsuke.stapler.QueryParameter;
import org.kohsuke.stapler.StaplerRequest;
import org.kohsuke.stapler.verb.POST;

import javax.servlet.ServletException;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.logging.Logger;

/**
 * Global configuration for Jenkins AI Chatbot Plugin
 * Provides system-wide settings accessible from Manage Jenkins → Configure System
 */
@Extension
public class ChatbotGlobalConfiguration extends GlobalConfiguration {
    
    private static final Logger LOGGER = Logger.getLogger(ChatbotGlobalConfiguration.class.getName());
    
    private String aiAgentUrl = "http://localhost:8000";
    private boolean enableChatbot = true;
    private int sessionTimeoutMinutes = 30;
    private String webhookSecret = "";
    private boolean debugMode = false;
    
    public ChatbotGlobalConfiguration() {
        load();
    }
    
    public static ChatbotGlobalConfiguration get() {
        return GlobalConfiguration.all().get(ChatbotGlobalConfiguration.class);
    }
    
    @Override
    public boolean configure(StaplerRequest req, JSONObject json) throws FormException {
        aiAgentUrl = json.optString("aiAgentUrl", "http://localhost:8000");
        enableChatbot = json.optBoolean("enableChatbot", true);
        sessionTimeoutMinutes = json.optInt("sessionTimeoutMinutes", 30);
        webhookSecret = json.optString("webhookSecret", "");
        debugMode = json.optBoolean("debugMode", false);
        
        save();
        
        LOGGER.info("AI Chatbot configuration updated - URL: " + aiAgentUrl + ", Enabled: " + enableChatbot);
        return true;
    }
    
    // Getters and setters
    public String getAiAgentUrl() {
        return aiAgentUrl;
    }
    
    public void setAiAgentUrl(String aiAgentUrl) {
        this.aiAgentUrl = aiAgentUrl;
    }
    
    public boolean isEnableChatbot() {
        return enableChatbot;
    }
    
    public void setEnableChatbot(boolean enableChatbot) {
        this.enableChatbot = enableChatbot;
    }
    
    public int getSessionTimeoutMinutes() {
        return sessionTimeoutMinutes;
    }
    
    public void setSessionTimeoutMinutes(int sessionTimeoutMinutes) {
        this.sessionTimeoutMinutes = sessionTimeoutMinutes;
    }
    
    public String getWebhookSecret() {
        return webhookSecret;
    }
    
    public void setWebhookSecret(String webhookSecret) {
        this.webhookSecret = webhookSecret;
    }
    
    public boolean isDebugMode() {
        return debugMode;
    }
    
    public void setDebugMode(boolean debugMode) {
        this.debugMode = debugMode;
    }
    
    /**
     * Form validation for AI Agent URL
     */
    @POST
    public FormValidation doCheckAiAgentUrl(@QueryParameter String value) {
        if (value == null || value.trim().isEmpty()) {
            return FormValidation.error("AI Agent URL is required");
        }
        
        try {
            URL url = new URL(value);
            if (!url.getProtocol().equals("http") && !url.getProtocol().equals("https")) {
                return FormValidation.error("URL must use HTTP or HTTPS protocol");
            }
            
            // Test connection to health endpoint
            String healthUrl = value.endsWith("/") ? value + "health" : value + "/health";
            HttpURLConnection connection = (HttpURLConnection) new URL(healthUrl).openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            
            try {
                int responseCode = connection.getResponseCode();
                if (responseCode == 200) {
                    return FormValidation.ok("Connection successful");
                } else {
                    return FormValidation.warning("Server responded with code: " + responseCode);
                }
            } catch (IOException e) {
                return FormValidation.warning("Cannot connect to server: " + e.getMessage());
            } finally {
                connection.disconnect();
            }
            
        } catch (Exception e) {
            return FormValidation.error("Invalid URL: " + e.getMessage());
        }
    }
    
    /**
     * Form validation for session timeout
     */
    public FormValidation doCheckSessionTimeoutMinutes(@QueryParameter String value) {
        try {
            int timeout = Integer.parseInt(value);
            if (timeout < 1) {
                return FormValidation.error("Session timeout must be at least 1 minute");
            }
            if (timeout > 1440) {
                return FormValidation.warning("Session timeout longer than 24 hours may impact performance");
            }
            return FormValidation.ok();
        } catch (NumberFormatException e) {
            return FormValidation.error("Please enter a valid number");
        }
    }
    
    @Override
    public String getDisplayName() {
        return "AI Chatbot Configuration";
    }
}