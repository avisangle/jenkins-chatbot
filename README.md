# Jenkins AI Chatbot

**Intelligent Conversational Interface for Jenkins Automation**

Transform your Jenkins experience with AI-powered natural language interactions. This project provides a complete solution combining a Jenkins plugin with an intelligent AI service to enable conversational Jenkins management.

[![Jenkins Plugin](https://img.shields.io/badge/Jenkins-Plugin-blue.svg)](https://plugins.jenkins.io/)
[![AI Service](https://img.shields.io/badge/AI-Gemini--Powered-green.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Java](https://img.shields.io/badge/Java-11+-red.svg)](https://openjdk.java.net/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org/)

## 🚀 What is Jenkins AI Chatbot?

Instead of navigating through Jenkins UI, simply ask:
- *"Trigger the frontend build with staging environment"*
- *"What's the status of my latest deployment?"*
- *"Show me the logs for the failed build"*
- *"List all jobs I have access to"*

The AI understands your intent, validates your permissions, and executes Jenkins operations on your behalf.

## ✨ Key Features

### 🤖 **LLM-First Intelligence**
- **Google Gemini Integration**: Advanced natural language understanding
- **21 Specialized Tools**: Complete Jenkins API coverage through MCP tools
- **Multi-Step Operations**: Handle complex workflows automatically
- **Context Awareness**: Remember conversation history and user preferences

### 🔐 **Security & Permissions**
- **Delegated Authorization**: AI acts with your exact Jenkins permissions
- **Session Management**: Secure 15-minute sessions with automatic cleanup
- **Audit Trail**: Complete logging of all AI interactions
- **CSRF Protection**: Full Jenkins security compliance

### 🎯 **User Experience**
- **Natural Language**: No learning command syntax or complex UIs
- **Modern Chat Interface**: Clean, responsive design integrated with Jenkins
- **Real-time Feedback**: Instant responses with visual status indicators
- **Mobile Friendly**: Works seamlessly on all devices

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Jenkins UI    │    │  Jenkins Plugin  │    │   AI Agent Service  │
│                 │───▶│                  │───▶│                     │
│ • Chat Interface│    │ • Session Mgmt   │    │ • Google Gemini     │
│ • Sidebar Link  │    │ • Security       │    │ • 21 MCP Tools      │
│ • Permissions   │    │ • REST API       │    │ • Redis + PostgreSQL│
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

### Components

- **[Jenkins Plugin](jenkins-plugin/)** - Java-based plugin providing UI integration and session management
- **[AI Agent Service](ai-agent/)** - Python FastAPI service with Google Gemini and 21 MCP tools
- **Infrastructure** - Redis for sessions, PostgreSQL for audit logging

## 📦 Quick Start

### Prerequisites
- **Jenkins**: 2.462.3+ 
- **Java**: 11+
- **Docker & Docker Compose**: For AI service
- **Google Gemini API Key**: For AI functionality

### 1. Install Jenkins Plugin

```bash
# Option A: Build from source
cd jenkins-plugin
mvn clean package
# Upload target/jenkins-chatbot.hpi to Jenkins → Manage Plugins → Advanced

# Option B: Download from Jenkins Update Center (coming soon)
```

### 2. Deploy AI Agent Service

```bash
# Configure environment
cp ai-agent/.env.example ai-agent/.env
# Edit .env with your GEMINI_API_KEY

# Start services
docker-compose up -d

# Verify services are running
curl http://localhost:8000/health
```

### 3. Configure Jenkins

1. **Go to Manage Jenkins → Configure System**
2. **Find "AI Chatbot Configuration" section**
3. **Set AI Agent URL**: `http://localhost:8000`
4. **Test connection** (should show "Connection successful")
5. **Grant permissions**: AI Chatbot → Use (to appropriate users)

### 4. Start Chatting!

1. **Look for "AI Assistant"** in Jenkins sidebar
2. **Click to open** the chat interface
3. **Try asking**: *"What jobs do I have access to?"*

## 💬 Example Conversations

### Build Management
```
👤 User: "Trigger the frontend build"
🤖 AI: "I'll trigger the frontend build for you. Starting build #47 now."
   [✅ Build #47 started successfully]

👤 User: "What's the status?"
🤖 AI: "Build #47 is currently running. Started 2 minutes ago, estimated completion in 3 minutes."
```

### Status Monitoring
```
👤 User: "Show me recent failed builds"
🤖 AI: "Here are your recent failed builds:
   • backend-service #23 - Failed 2 hours ago (test failures)
   • integration-tests #15 - Failed yesterday (timeout)
   
   Would you like me to show the logs for any of these?"
```

### Log Analysis
```
👤 User: "Show me the log for backend-service #23"
🤖 AI: "Here are the key log entries from build #23:
   [ERROR] Tests failed: 3 out of 127 test cases
   [ERROR] DatabaseConnectionTest.testConnection - Connection timeout
   
   The build failed due to database connectivity issues during testing."
```

## 🔧 Configuration

### AI Agent Service Configuration

```bash
# ai-agent/.env
GEMINI_API_KEY=your-google-gemini-api-key
JENKINS_URL=http://your-jenkins-instance:8080
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
SECRET_KEY=your-secret-key-change-in-production
```

### Jenkins Plugin Configuration

**Global Settings** (Manage Jenkins → Configure System):
- **AI Agent URL**: URL of the AI service (default: http://localhost:8000)
- **Session Timeout**: How long sessions remain active (default: 15 minutes)
- **Enable Chatbot**: Master on/off switch for the entire system

**User Permissions**:
- **AI Chatbot/Use**: Basic access to chat interface
- **Standard Jenkins permissions**: Required for actual operations (Job/Build, Job/Read, etc.)

## 🛠️ Development

### Building from Source

**Jenkins Plugin**:
```bash
cd jenkins-plugin
mvn clean package
# Creates: target/jenkins-chatbot.hpi
```

**AI Agent Service**:
```bash
cd ai-agent
docker build -t jenkins-chatbot-ai-agent .
```

**Full Development Environment**:
```bash
# Start infrastructure
docker-compose up -d redis postgres

# Start AI service in development mode
cd ai-agent && ./scripts/start_dev.sh

# Start Jenkins with plugin
cd jenkins-plugin && mvn hpi:run
```

### Testing

```bash
# Test AI Agent Service
python ai-agent/scripts/test_api.py

# Test Jenkins Plugin
cd jenkins-plugin && mvn test

# Test end-to-end integration
JENKINS_API_TOKEN="your-token" ./scripts/test_end_to_end.sh
```

## 🛡️ Security

### Permission Model
- **Principle of Least Privilege**: AI only has permissions you grant it
- **Session-Based Security**: 15-minute secure sessions with automatic cleanup
- **Audit Logging**: All interactions logged with user context and actions taken
- **No Elevated Access**: AI cannot perform actions you don't have permission for

### Best Practices
- **Secure API Keys**: Keep Google Gemini API key secure and rotated
- **Network Security**: Run AI service in trusted network environment
- **User Training**: Educate users on appropriate AI assistant usage
- **Regular Audits**: Review AI interaction logs for unusual patterns

## 📊 Monitoring

### Health Checks
```bash
# AI Agent Service
curl http://localhost:8000/health

# Jenkins Plugin
http://your-jenkins/ai-assistant/health
```

### Logging
- **Jenkins Plugin**: Standard Jenkins logs (`$JENKINS_HOME/logs/`)
- **AI Agent Service**: Structured JSON logs via Docker Compose
- **Audit Trail**: PostgreSQL database with full interaction history

### Metrics (Optional)
```bash
# Enable monitoring stack
docker-compose --profile monitoring up -d

# Access dashboards
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

## 🔍 Troubleshooting

### Common Issues

**1. "AI Assistant" not visible in sidebar**
- Check user has "AI Chatbot/Use" permission
- Verify plugin is installed and enabled
- Confirm user has "Overall/Read" permission

**2. Connection failed to AI service**
- Verify AI service is running: `curl http://localhost:8000/health`
- Check firewall and network connectivity
- Validate AI Agent URL in Jenkins configuration

**3. Permission denied errors**
- User lacks required Jenkins permissions for the requested action
- Check Jenkins security matrix for appropriate permissions
- Review audit logs for specific permission failures

**4. AI responses seem incorrect**
- Check Google Gemini API key and quotas
- Verify MCP tools are functioning: `curl http://localhost:8010/health`
- Review conversation context and session state

For detailed troubleshooting guides, see:
- [Jenkins Plugin Troubleshooting](jenkins-plugin/README.md#troubleshooting)
- [AI Agent Service Troubleshooting](ai-agent/README.md#troubleshooting)

## 📚 Documentation

### Core Documentation
- **[Jenkins Plugin Guide](jenkins-plugin/README.md)** - Installation, configuration, and usage
- **[AI Agent Service Guide](ai-agent/README.md)** - Service setup, API reference, and architecture
- **[Development Guide](docs/)** - Technical implementation details and contribution guidelines

### API References
- **[Plugin REST API](jenkins-plugin/README.md#api-reference)** - Endpoints for chat operations
- **[AI Service API](ai-agent/README.md#api-reference)** - AI processing and tool execution
- **[MCP Tools Documentation](docs/MCP_TESTING_RESULTS.md)** - All 21 available tools and their capabilities

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Getting Started
1. **Fork the repository**
2. **Set up development environment** (see Development section above)
3. **Create feature branch**: `git checkout -b feature/amazing-feature`
4. **Make your changes** with tests
5. **Submit pull request** with detailed description

### Development Areas
- **Jenkins Plugin**: Java development, UI improvements, security enhancements
- **AI Agent**: Python/FastAPI, LLM integration, tool development
- **Documentation**: User guides, API docs, troubleshooting
- **Testing**: Unit tests, integration tests, user acceptance testing

### Code Standards
- Follow existing code style and patterns
- Include comprehensive tests for new functionality
- Update documentation for user-facing changes
- Ensure security best practices are followed

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🌟 Acknowledgments

- **Jenkins Community** - For the amazing automation platform
- **Google AI** - For Gemini API and language model capabilities
- **MCP Protocol** - For standardized tool integration
- **FastAPI Community** - For the excellent async web framework

## 📞 Support

- **🐛 Bug Reports**: [GitHub Issues](https://github.com/avisangle/jenkins-chatbot/issues)
- **💡 Feature Requests**: [GitHub Discussions](https://github.com/avisangle/jenkins-chatbot/discussions)
- **📖 Documentation**: Check the `docs/` directory for detailed guides
- **💬 Community**: Join discussions in GitHub Issues and Discussions

---

**Transform your Jenkins workflow with AI** • **Natural Language Operations** • **Secure & Permission-Aware** • **Production Ready**

Made with ❤️ for the Jenkins community