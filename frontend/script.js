// API base URL - use backend API endpoints
// Supports configuration via window.VITOS_CONFIG.BACKEND_API_URL (set by config.js)
// Falls back to dynamically constructing URL based on current hostname
const getApiUrl = () => {
    // Check if configuration is available (from config.js)
    if (window.VITOS_CONFIG && window.VITOS_CONFIG.BACKEND_API_URL) {
        const backendUrl = window.VITOS_CONFIG.BACKEND_API_URL;
        // Remove trailing slash if present
        const cleanUrl = backendUrl.endsWith('/') ? backendUrl.slice(0, -1) : backendUrl;
        return `${cleanUrl}/api/v1`;
    }

    // Fallback: dynamically construct based on current page location
    const hostname = window.location.hostname;
    const protocol = window.location.protocol; // http: or https:
    return `${protocol}//${hostname}:8000/api/v1`;
};
const API_URL = getApiUrl();
const REQUEST_TIMEOUT = 120000; // 120 seconds for MCP tool calls

// Global state
// Note: This will be set to a unique ID when createNewConversation() is called on page load
let currentConversationId = null;
let useStreamingMode = false;  // Default to blocking mode

// Fetch with timeout helper
async function fetchWithTimeout(url, options = {}, timeout = REQUEST_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out. The server is taking too long to respond.');
        }
        throw error;
    }
}

// DOM elements
let chatMessages, chatInput, sendButton, newConversationBtn;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    newConversationBtn = document.getElementById('newConversationBtn');

    setupEventListeners();
    createNewConversation();
    
    // Display app version if available
    displayAppVersion();
});

// Event Listeners
function setupEventListeners() {
    // Chat functionality
    sendButton.addEventListener('click', () => {
        if (useStreamingMode) {
            sendMessageStream();
        } else {
            sendMessage();
        }
    });
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            if (useStreamingMode) {
                sendMessageStream();
            } else {
                sendMessage();
            }
        }
    });

    // Streaming mode toggle
    const streamingToggle = document.getElementById('streamingToggle');
    streamingToggle.addEventListener('change', (e) => {
        useStreamingMode = e.target.checked;
        document.querySelector('.toggle-text').textContent =
            useStreamingMode ? 'Streaming Mode' : 'Blocking Mode';
    });

    // New conversation functionality
    newConversationBtn.addEventListener('click', createNewConversation);

    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            if (useStreamingMode) {
                sendMessageStream();
            } else {
                sendMessage();
            }
        });
    });

    // Hacking/security testing questions
    document.querySelectorAll('.hacking-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            if (useStreamingMode) {
                sendMessageStream();
            } else {
                sendMessage();
            }
        });
    });
}

// Chat Functions
async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(message, 'user');

    // Add loading message
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetchWithTimeout(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            // Handle error detail - convert to string if it's an object
            let errorDetail = errorData.detail;
            if (typeof errorDetail === 'object' && errorDetail !== null) {
                errorDetail = JSON.stringify(errorDetail, null, 2);
            }
            const error = new Error(errorDetail || `Server error: ${response.status}`);
            error.status = response.status; // Preserve status for content policy detection
            throw error;
        }

        const data = await response.json();

        // Update conversation ID if new
        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.response, 'assistant');

    } catch (error) {
        console.error('Chat error:', error);
        // Replace loading message with error
        loadingMessage.remove();

        // Handle error message - ensure it's always a string
        let errorMsg = error.message || 'Unknown error occurred';
        if (typeof errorMsg === 'object') {
            errorMsg = JSON.stringify(errorMsg, null, 2);
        }

        // Content policy errors (403) are already complete messages - display as-is
        // Other errors need context wrapper
        const isContentPolicyError = error.status === 403;
        const displayMessage = isContentPolicyError
            ? errorMsg
            : `Sorry, I encountered an error: ${errorMsg}. Please try again.`;

        addMessage(displayMessage, 'assistant');
    } finally {
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

async function sendMessageStream() {
    const message = chatInput.value.trim();
    if (!message) return;

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(message, 'user');

    // Create assistant message placeholder
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = '<div class="message-content"></div>';
    chatMessages.appendChild(messageDiv);
    const contentDiv = messageDiv.querySelector('.message-content');

    let accumulatedContent = "";
    let toolCallsHtml = "";  // Accumulate tool call displays

    try {
        const response = await fetch(`${API_URL}/chat/stream`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId
            })
        });

        if (!response.ok) {
            // Extract error detail from response body
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            let errorDetail = errorData.detail;
            if (typeof errorDetail === 'object' && errorDetail !== null) {
                errorDetail = JSON.stringify(errorDetail, null, 2);
            }
            const error = new Error(errorDetail || `Server error: ${response.status}`);
            error.status = response.status;
            throw error;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const messages = buffer.split('\n\n');
            buffer = messages.pop(); // Keep incomplete message in buffer

            for (const msg of messages) {
                if (msg.startsWith('data: ')) {
                    const data = JSON.parse(msg.substring(6));

                    if (data.type === 'start') {
                        if (data.conversation_id) {
                            currentConversationId = data.conversation_id;
                        }
                    }
                    else if (data.type === 'kb_search') {
                        // Knowledge base search - show progress indicator
                        const message = data.message || 'Searching knowledge base...';
                        toolCallsHtml += `
                            <div class="tool-progress">
                                <small>🔍 ${escapeHtml(message)}</small>
                            </div>
                        `;
                        contentDiv.innerHTML = toolCallsHtml + marked.parse(accumulatedContent);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'token') {
                        // Agent text response - accumulate and render
                        accumulatedContent += data.content;
                        const fullHtml = toolCallsHtml + marked.parse(accumulatedContent);
                        contentDiv.innerHTML = fullHtml;
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'tool_call') {
                        // Tool invocation - show simple tool name
                        const toolName = data.tool || 'unknown';
                        toolCallsHtml += `
                            <div class="tool-progress">
                                <small>🔧 Calling the tool: ${escapeHtml(toolName)} ...</small>
                            </div>
                        `;
                        contentDiv.innerHTML = toolCallsHtml + marked.parse(accumulatedContent);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'tool_result') {
                        // Tool result - show simple result
                        const result = data.result || '';
                        const truncatedResult = result.length > 200 ? result.substring(0, 200) + '...' : result;
                        toolCallsHtml += `
                            <div class="tool-progress">
                                <small>✅ The tool call returns: ${escapeHtml(truncatedResult)}</small>
                            </div>
                        `;
                        contentDiv.innerHTML = toolCallsHtml + marked.parse(accumulatedContent);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'security_violation') {
                        // Clear accumulated content
                        accumulatedContent = "";
                        toolCallsHtml = "";

                        // Retract all displayed content and show error
                        contentDiv.innerHTML = `
                            <div class="security-error">
                                <span class="error-icon">⚠️</span>
                                <p><strong>Response Blocked</strong></p>
                                <p>The response couldn't be displayed due to our content policy.</p>
                                <p>Please try rephrasing your question.</p>
                            </div>
                        `;
                        chatMessages.scrollTop = chatMessages.scrollHeight;

                        // Stop processing further events
                        break;
                    }
                    else if (data.type === 'done') {
                        console.log('Streaming complete');
                    }
                    else if (data.type === 'error') {
                        throw new Error(data.error);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Streaming error:', error);
        contentDiv.innerHTML = `<p>Sorry, I encountered an error: ${escapeHtml(error.message)}. Please try again.</p>`;
    } finally {
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function createLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, isWelcome = false) {
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;

    // Convert markdown to HTML for assistant messages
    const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);

    let html = `<div class="message-content">${displayContent}</div>`;

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function createNewConversation() {
    // Delete previous conversation from backend to prevent memory leak
    if (currentConversationId) {
        try {
            const response = await fetchWithTimeout(`${API_URL}/conversations/${currentConversationId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                console.log(`Deleted previous conversation: ${currentConversationId}`);
            } else {
                console.warn(`Failed to delete conversation ${currentConversationId}: ${response.status}`);
            }
        } catch (error) {
            console.warn('Failed to delete previous conversation:', error);
            // Continue anyway - don't block new conversation creation
        }
    }

    // Generate a new conversation ID
    currentConversationId = `conversation_${Date.now()}`;

    // Clear chat messages
    chatMessages.innerHTML = '';

    // Add welcome message
    addMessage('🍕 Welcome to Vito\'s Pizza Cafe! I\'m here to help you with our menu, orders, delivery information, and more. What can I help you with today?', 'assistant', true);

    // Focus input
    if (chatInput) {
        chatInput.focus();
    }
}

// Health check function to verify backend connectivity
async function checkBackendHealth() {
    try {
        const response = await fetchWithTimeout(`${API_URL}/health`, {}, 10000); // 10s timeout for health check
        if (!response.ok) throw new Error('Health check failed');
        const data = await response.json();
        console.log('Backend health:', data);
        return true;
    } catch (error) {
        console.error('Backend health check failed:', error);
        return false;
    }
}

// Check backend health on load (optional)
document.addEventListener('DOMContentLoaded', () => {
    checkBackendHealth().then(healthy => {
        if (!healthy) {
            console.warn('Backend may not be running. Make sure to start the backend server.');
        }
    });
});

// Add this new function before the health check function
function displayAppVersion() {
    const versionElement = document.getElementById('appVersion');
    if (versionElement && window.VITOS_CONFIG && window.VITOS_CONFIG.APP_VERSION) {
        versionElement.textContent = `Version: ${window.VITOS_CONFIG.APP_VERSION}`;
    }
}