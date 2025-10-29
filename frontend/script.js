// API base URL - use backend API endpoints
// Dynamically construct the backend URL based on current hostname
// This allows the frontend to work both locally and on remote servers
const getApiUrl = () => {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol; // http: or https:
    return `${protocol}//${hostname}:8000/api/v1`;
};
const API_URL = getApiUrl();
const REQUEST_TIMEOUT = 120000; // 120 seconds for MCP tool calls

// Global state
// Note: This will be set to a unique ID when createNewConversation() is called on page load
let currentConversationId = null;

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
});

// Event Listeners
function setupEventListeners() {
    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // New conversation functionality
    newConversationBtn.addEventListener('click', createNewConversation);

    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            sendMessage();
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
            throw new Error(errorData.detail || `Server error: ${response.status}`);
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
        addMessage(`Sorry, I encountered an error: ${error.message}. Please try again.`, 'assistant');
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