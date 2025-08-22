/**
 * Jenkins AI Chatbot - Client-side JavaScript
 * Handles REST API communication and UI interactions
 */

// Prevent duplicate class declaration - TEMPORARY FIX
// TODO: Investigate root cause of multiple script loading in Jenkins plugin
if (typeof window.JenkinsChatbot !== 'undefined') {
    console.log('⚠️ JenkinsChatbot already exists, skipping redeclaration');
} else {

window.JenkinsChatbot = class JenkinsChatbot {
    constructor() {
        console.log('🚀 Initializing Jenkins Chatbot...');
        
        this.sessionId = null;
        this.userId = null;
        this.userToken = null;
        this.tokenExpiry = null;
        this.permissions = null;
        this.isConnected = false;
        this.crumbData = null;
        
        console.log('🔧 Setting up chatbot components...');
        this.initializeElements();
        this.bindEvents();
        this.initializeAndCreateSession();
    }
    
    initializeElements() {
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');
        this.connectionStatus = document.getElementById('connection-status');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.clearButton = document.getElementById('clear-chat');
        this.helpButton = document.getElementById('help-button');
        this.errorNotification = document.getElementById('error-notification');
        this.errorMessage = document.getElementById('error-message');
        this.closeErrorButton = document.getElementById('close-error');
    }
    
    bindEvents() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter key in input
        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Input changes
        this.chatInput.addEventListener('input', () => this.onInputChange());
        
        // Auto-resize textarea
        this.chatInput.addEventListener('input', () => this.autoResizeTextarea());
        
        // Clear chat
        this.clearButton.addEventListener('click', () => this.clearChat());
        
        // Help button
        this.helpButton.addEventListener('click', () => this.showHelp());
        
        // Close error notification
        this.closeErrorButton.addEventListener('click', () => this.hideError());
        
        // Window beforeunload
        window.addEventListener('beforeunload', () => this.disconnect());
    }
    
    /**
     * Fetch CSRF protection token (crumb) from Jenkins
     */
    async fetchCrumb() {
        try {
            const response = await fetch('/crumbIssuer/api/json', {
                method: 'GET',
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const crumbData = await response.json();
                this.crumbData = {
                    [crumbData.crumbRequestField]: crumbData.crumb
                };
                return this.crumbData;
            } else {
                console.warn('Failed to fetch CSRF crumb, proceeding without it');
                return {};
            }
        } catch (error) {
            console.warn('Error fetching CSRF crumb:', error);
            return {};
        }
    }
    
    /**
     * Initialize crumb and create session
     */
    async initializeAndCreateSession() {
        console.log('🔐 Starting initialization sequence...');
        
        // Fetch CSRF token first
        console.log('🎫 Fetching CSRF token...');
        await this.fetchCrumb();
        
        // Then create session
        console.log('📝 Creating chat session...');
        await this.createSession();
    }
    
    /**
     * Make authenticated API request with CSRF token
     */
    async makeApiRequest(url, options = {}) {
        // Ensure we have crumb data for POST requests
        if (options.method === 'POST') {
            const crumb = this.crumbData || await this.fetchCrumb();
            options.headers = {
                ...options.headers,
                ...crumb
            };
        }
        
        // Always include credentials
        options.credentials = 'same-origin';
        
        return fetch(url, options);
    }
    
    async createSession() {
        console.log('🔄 Starting session creation...');
        this.updateConnectionStatus('Connecting...', 'status-connecting');
        
        try {
            console.log('📡 Making API request to /ai-assistant/apiSession');
            const response = await this.makeApiRequest('/ai-assistant/apiSession', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            console.log('📊 Response status:', response.status, response.statusText);
            
            if (response.ok) {
                const sessionData = await response.json();
                console.log('✅ Session data received:', {
                    sessionId: sessionData.sessionId ? 'present' : 'missing',
                    userId: sessionData.userId ? 'present' : 'missing',
                    userToken: sessionData.userToken ? 'present' : 'missing',
                    permissions: sessionData.permissions
                });
                
                this.sessionId = sessionData.sessionId;
                this.userId = sessionData.userId;
                this.userToken = sessionData.userToken;
                this.tokenExpiry = sessionData.expiresAt || (Date.now() + 15 * 60 * 1000); // Default 15 mins
                this.permissions = sessionData.permissions || ['Job.READ', 'Job.BUILD', 'Job.CREATE'];
                
                // Connect using REST API instead of WebSocket
                this.isConnected = true;
                this.updateConnectionStatus('Connected', 'status-connected');
                this.onInputChange(); // Enable send button
                console.log('🎉 Session created successfully!');
            } else {
                const errorText = await response.text().catch(() => 'Unknown error');
                console.error('❌ Session creation failed:', response.status, response.statusText, errorText);
                this.updateConnectionStatus('Connection Failed', 'status-error');
                this.showError(`Failed to create chat session (${response.status}): ${response.statusText}`);
            }
        } catch (error) {
            console.error('💥 Session creation error:', error);
            this.updateConnectionStatus('Connection Error', 'status-error');
            this.showError(`Failed to initialize chat session: ${error.message}`);
        }
    }
    
    // WebSocket functionality removed - using REST API instead
    
    /**
     * Check if token is expired or will expire soon, refresh if needed
     */
    async ensureValidToken() {
        const currentTime = Date.now();
        const timeUntilExpiry = this.tokenExpiry - currentTime;
        
        // Refresh if token expires within 2 minutes or is already expired
        if (timeUntilExpiry <= 2 * 60 * 1000) {
            console.log('🔄 Token expired or expiring soon, refreshing session...');
            await this.createSession();
        }
    }

    async sendMessage() {
        const content = this.chatInput.value.trim();
        if (!content || !this.isConnected) {
            return;
        }
        
        // Ensure we have a valid token before sending
        try {
            await this.ensureValidToken();
        } catch (error) {
            console.error('💥 Failed to refresh token:', error);
            this.addMessage('Failed to refresh session. Please reload the page.', 'error', Date.now());
            return;
        }
        
        // Add user message to chat
        this.addMessage(content, 'user', Date.now());
        
        // Clear input and show typing indicator
        this.chatInput.value = '';
        this.onInputChange();
        this.autoResizeTextarea();
        this.showTypingIndicator();
        
        try {
            // Send to AI Agent via REST API
            const chatRequest = {
                session_id: this.sessionId,
                user_id: this.userId,
                user_token: this.userToken,
                message: content,
                permissions: this.permissions,
                context: {
                    jenkins_url: window.location.origin,
                    current_user: this.userId
                }
            };
            
            console.log('💬 Sending chat message:', {
                session_id: this.sessionId,
                user_id: this.userId,
                message_length: content.length,
                permissions: this.permissions
            });
            
            const response = await this.makeApiRequest('/ai-assistant/api/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + this.userToken
                },
                body: JSON.stringify(chatRequest)
            });
            
            this.hideTypingIndicator();
            console.log('📨 Chat response status:', response.status, response.statusText);
            
            if (response.ok) {
                const aiResponse = await response.json();
                console.log('🤖 AI response received, length:', aiResponse.response?.length || 0);
                this.addMessage(aiResponse.response, 'assistant', Date.now());
                
                if (aiResponse.actions && aiResponse.actions.length > 0) {
                    console.log('⚡ Actions received:', aiResponse.actions.length);
                    this.handleActions(aiResponse.actions);
                }
            } else if (response.status === 401) {
                console.warn('🔑 Token expired, attempting to refresh and retry...');
                try {
                    await this.createSession();
                    // Retry the request with the new token
                    const retryRequest = {
                        ...chatRequest,
                        user_token: this.userToken
                    };
                    
                    const retryResponse = await this.makeApiRequest('/ai-assistant/api/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer ' + this.userToken
                        },
                        body: JSON.stringify(retryRequest)
                    });
                    
                    if (retryResponse.ok) {
                        const aiResponse = await retryResponse.json();
                        console.log('🤖 AI response received after token refresh');
                        this.addMessage(aiResponse.response, 'assistant', Date.now());
                        
                        if (aiResponse.actions && aiResponse.actions.length > 0) {
                            this.handleActions(aiResponse.actions);
                        }
                    } else {
                        const errorData = await retryResponse.json().catch(() => ({}));
                        console.error('❌ Chat API error after retry:', retryResponse.status, retryResponse.statusText, errorData);
                        this.addMessage(`Sorry, I encountered an authentication error. Please reload the page.`, 'error', Date.now());
                    }
                } catch (refreshError) {
                    console.error('💥 Failed to refresh token and retry:', refreshError);
                    this.addMessage('Session expired. Please reload the page to continue.', 'error', Date.now());
                }
            } else {
                const errorData = await response.json().catch(() => ({}));
                console.error('❌ Chat API error:', response.status, response.statusText, errorData);
                this.addMessage(`Sorry, I encountered an error processing your request (${response.status}).`, 'error', Date.now());
            }
            
        } catch (error) {
            this.hideTypingIndicator();
            console.error('💥 Chat error:', error);
            this.addMessage(`Sorry, I could not connect to the AI service: ${error.message}`, 'error', Date.now());
        }
    }
    
    addMessage(content, type, timestamp) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Handle markdown-like formatting
        const formattedContent = this.formatMessageContent(content);
        messageContent.innerHTML = formattedContent;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-timestamp';
        messageTime.textContent = this.formatTimestamp(timestamp);
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    formatMessageContent(content) {
        // Simple markdown-like formatting
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }
    
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false 
        });
    }
    
    handleActions(actions) {
        // Handle specific actions from AI response
        if (Array.isArray(actions)) {
            actions.forEach(action => {
                if (action.type === 'jenkins_api_call') {
                    console.log('AI suggested Jenkins API call:', action);
                    // Could show confirmation dialog or execute automatically
                }
            });
        }
    }
    
    onInputChange() {
        const hasContent = this.chatInput.value.trim().length > 0;
        this.sendButton.disabled = !hasContent || !this.isConnected;
    }
    
    autoResizeTextarea() {
        this.chatInput.style.height = 'auto';
        this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 100) + 'px';
    }
    
    showTypingIndicator() {
        this.typingIndicator.style.display = 'block';
    }
    
    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }
    
    updateConnectionStatus(status, className) {
        this.connectionStatus.textContent = status;
        this.connectionStatus.className = className;
    }
    
    clearChat() {
        if (confirm('Are you sure you want to clear the conversation?')) {
            // Remove all messages except welcome message
            const messages = this.chatMessages.querySelectorAll('.message:not(.welcome-message .message)');
            messages.forEach(message => message.remove());
        }
    }
    
    showHelp() {
        const helpContent = `I can help you with Jenkins tasks using natural language. Try asking:

• **Build Operations**: "Trigger the frontend build", "Start the deployment job"
• **Status Checks**: "What's the status of my last build?", "Show me recent builds" 
• **Build Logs**: "Show me the log for build #123", "Why did my build fail?"
• **Job Management**: "List all my jobs", "What jobs can I access?"
• **General Help**: "What can you do?", "Help me with deployments"

Just type your request naturally and I'll help you get it done!`;
        
        this.addMessage(helpContent, 'assistant', Date.now());
    }
    
    showError(message) {
        this.errorMessage.textContent = message;
        this.errorNotification.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => this.hideError(), 5000);
    }
    
    hideError() {
        this.errorNotification.style.display = 'none';
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    disconnect() {
        this.isConnected = false;
        this.updateConnectionStatus('Disconnected', 'status-disconnected');
    }
}

// Close the else block
}

// Initialize chatbot when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM loaded, initializing Jenkins Chatbot...');
    console.log('🌐 Current URL:', window.location.href);
    console.log('👤 User agent:', navigator.userAgent);
    
    // Only initialize if not already initialized
    if (!window.jenkinsChatbot && window.JenkinsChatbot) {
        const chatbot = new window.JenkinsChatbot();
        window.jenkinsChatbot = chatbot; // Make available globally for debugging
        console.log('✅ Jenkins Chatbot instance created and available as window.jenkinsChatbot');
    } else if (window.jenkinsChatbot) {
        console.log('⚠️ Jenkins Chatbot already initialized, skipping');
    } else {
        console.error('❌ JenkinsChatbot class not available');
    }
});