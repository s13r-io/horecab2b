/**
 * NAM Procurement Platform - Chat UI Script
 * Handles user interactions and API communication
 */

const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const forecastBtn = document.getElementById('forecastBtn');

const RESTAURANT_ID = 'R001';
const API_BASE = '';  // Relative URLs (no localhost)


/**
 * Send message to /chat endpoint
 */
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // Add user message to UI
    addBubble('user', message);
    messageInput.value = '';

    // Show typing indicator
    showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, restaurant_id: RESTAURANT_ID })
        });

        if (!response.ok) {
            const error = await response.json();
            addBubble('assistant', `Error: ${error.detail || 'Unknown error'}`);
            return;
        }

        const data = await response.json();

        // Remove typing indicator
        removeTypingIndicator();

        // Add assistant response
        addBubble('assistant', data.response_text);

        // Handle suggestion action (order created)
        if (data.action === 'suggestion' && data.data?.order_id) {
            addApproveButton(data.data.order_id);
        }

    } catch (error) {
        removeTypingIndicator();
        addBubble('assistant', `Error: ${error.message}`);
    }
}


/**
 * Handle forecast button click
 */
async function runForecast() {
    forecastBtn.disabled = true;
    forecastBtn.textContent = 'Loading...';

    addBubble('assistant', 'Generating forecast...');

    try {
        const response = await fetch(`${API_BASE}/forecast-today?restaurant_id=${RESTAURANT_ID}`);

        if (!response.ok) {
            const error = await response.json();
            addBubble('assistant', `Error: ${error.detail || 'Could not generate forecast'}`);
            return;
        }

        const data = await response.json();

        // Format forecast response
        let forecastText = '**Today\'s Demand Forecast**\n\n';
        for (const forecast of data.forecasts) {
            forecastText += `* ${forecast.ingredient_name}: ${forecast.forecast_quantity} ${forecast.unit}\n`;
        }
        forecastText += `\n**Estimated Cost:** Rs.${data.estimated_total_cost.toFixed(2)}`;

        addBubble('assistant', forecastText);

    } catch (error) {
        addBubble('assistant', `Error: ${error.message}`);
    } finally {
        forecastBtn.disabled = false;
        forecastBtn.textContent = 'Run Morning Forecast';
    }
}


/**
 * Approve order
 */
async function approveOrder(orderId) {
    const approveBtn = document.querySelector(`[data-order-id="${orderId}"]`);
    if (approveBtn) {
        approveBtn.disabled = true;
        approveBtn.textContent = 'Approving...';
    }

    try {
        const response = await fetch(`${API_BASE}/approve-order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, restaurant_id: RESTAURANT_ID })
        });

        if (!response.ok) {
            const error = await response.json();
            addBubble('assistant', `Error: ${error.detail || 'Could not approve order'}`);
            return;
        }

        const data = await response.json();

        if (data.status === 'dispatched') {
            addBubble('assistant', `Order ${orderId} approved and dispatched!\n\nMessages sent to vendors.`);
        } else if (data.error) {
            addBubble('assistant', `Error: ${data.error}`);
        }

    } catch (error) {
        addBubble('assistant', `Error: ${error.message}`);
    }
}


/**
 * Add message bubble to UI
 */
function addBubble(role, text) {
    const message = document.createElement('div');
    message.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    // Convert \n to <br> for line breaks
    const htmlText = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');

    bubble.innerHTML = htmlText;

    message.appendChild(bubble);
    chatContainer.appendChild(message);

    // Auto-scroll
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


/**
 * Add approve button to last assistant bubble
 */
function addApproveButton(orderId) {
    const lastBubble = chatContainer.lastElementChild?.querySelector('.bubble');
    if (!lastBubble) return;

    const actionDiv = document.createElement('div');
    actionDiv.className = 'action-buttons';

    const btn = document.createElement('button');
    btn.className = 'btn-action';
    btn.textContent = 'Approve Order';
    btn.dataset.orderId = orderId;
    btn.onclick = () => approveOrder(orderId);

    actionDiv.appendChild(btn);
    lastBubble.appendChild(actionDiv);
}


/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const message = document.createElement('div');
    message.className = 'message assistant';
    message.id = 'typing-indicator';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = '<span>...</span>';

    message.appendChild(bubble);
    chatContainer.appendChild(message);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


/**
 * Remove typing indicator
 */
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}


/**
 * Event listeners
 */
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

forecastBtn.addEventListener('click', runForecast);


/**
 * Initialize
 */
window.addEventListener('load', () => {
    addBubble('assistant', 'Welcome to NAM Procurement Platform!\n\nI\'m your AI procurement assistant. You can:\n* Report low stock (e.g., "We\'re out of chicken")\n* Check prices (e.g., "What\'s the price of tomato?")\n* Run the morning forecast\n* Ask any procurement questions');
    messageInput.focus();
});
