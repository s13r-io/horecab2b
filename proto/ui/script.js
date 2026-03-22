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

        // Handle order confirmation action
        if (data.action === 'order_confirmation' && data.data?.order_id) {
            addConfirmCancelButtons(data.data.order_id);
        }

        // Handle order queued action
        if (data.action === 'order_queued' && data.data?.order_id) {
            addQueuedOrderMessage(data.data.order_id, data.data.scheduled_send_time);
        }

        // Handle awaiting confirmation (multi-turn order flow)
        if (data.action === 'awaiting_confirmation') {
            addConfirmationButtons(data.data);
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

        // Add "Place Order" button if there are items to order
        if (data.forecasts && data.forecasts.length > 0) {
            addPlaceOrderButton();
        }

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

        if (data.status === 'queued') {
            addBubble('assistant', `✅ Order ${orderId} confirmed and queued!\n📅 Vendor messages will be sent at ${data.scheduled_send_time || 'scheduled time'}.`);
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
    btn.textContent = 'Confirm Order';
    btn.dataset.orderId = orderId;
    btn.onclick = () => approveOrder(orderId);

    actionDiv.appendChild(btn);
    lastBubble.appendChild(actionDiv);
}


/**
 * Add "Place Order" button to last assistant bubble (after forecast)
 */
function addPlaceOrderButton() {
    const lastBubble = chatContainer.lastElementChild?.querySelector('.bubble');
    if (!lastBubble) return;

    const actionDiv = document.createElement('div');
    actionDiv.className = 'action-buttons';

    const btn = document.createElement('button');
    btn.className = 'btn-action btn-confirm';
    btn.textContent = 'Place Order';
    btn.onclick = () => {
        messageInput.value = 'place order for today\'s forecast';
        sendMessage();
    };

    actionDiv.appendChild(btn);
    lastBubble.appendChild(actionDiv);
}


/**
 * Add confirm and cancel buttons to last assistant bubble
 */
function addConfirmCancelButtons(orderId) {
    const lastBubble = chatContainer.lastElementChild?.querySelector('.bubble');
    if (!lastBubble) return;

    const actionDiv = document.createElement('div');
    actionDiv.className = 'action-buttons';

    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'btn-action btn-confirm';
    confirmBtn.textContent = 'Confirm Order';
    confirmBtn.onclick = () => {
        messageInput.value = `confirm order ${orderId}`;
        sendMessage();
    };

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-action btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.onclick = () => cancelOrder(orderId);

    actionDiv.appendChild(confirmBtn);
    actionDiv.appendChild(cancelBtn);
    lastBubble.appendChild(actionDiv);
}


/**
 * Cancel an order
 */
async function cancelOrder(orderId) {
    try {
        const response = await fetch(`${API_BASE}/order/${orderId}/cancel?restaurant_id=${RESTAURANT_ID}`, {
            method: 'PUT'
        });

        if (response.ok) {
            addBubble('assistant', `✅ Order ${orderId} has been cancelled.`);
        } else {
            const error = await response.json();
            addBubble('assistant', `❌ Error: ${error.detail || 'Could not cancel order'}`);
        }
    } catch (error) {
        addBubble('assistant', `❌ Error: ${error.message}`);
    }
}


/**
 * Show queued order message with Place Now and Cancel buttons
 */
function addQueuedOrderMessage(orderId, scheduledSendTime) {
    const lastBubble = chatContainer.lastElementChild?.querySelector('.bubble');
    if (!lastBubble) return;

    const actionDiv = document.createElement('div');
    actionDiv.className = 'action-buttons';

    const placeNowBtn = document.createElement('button');
    placeNowBtn.className = 'btn-action btn-confirm';
    placeNowBtn.textContent = 'Place Now';
    placeNowBtn.onclick = () => placeOrderNow(orderId);

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-action btn-cancel';
    cancelBtn.textContent = 'Cancel Order';
    cancelBtn.onclick = () => cancelOrder(orderId);

    actionDiv.appendChild(placeNowBtn);
    actionDiv.appendChild(cancelBtn);
    lastBubble.appendChild(actionDiv);
}


/**
 * Manually place a queued order now
 */
async function placeOrderNow(orderId) {
    try {
        const response = await fetch(`${API_BASE}/order/${orderId}/place?restaurant_id=${RESTAURANT_ID}`, {
            method: 'PUT'
        });

        if (response.ok) {
            addBubble('assistant', `✅ Order ${orderId} has been placed! Vendor messages have been sent.`);
        } else {
            const error = await response.json();
            addBubble('assistant', `❌ Error: ${error.detail || 'Could not place order'}`);
        }
    } catch (error) {
        addBubble('assistant', `❌ Error: ${error.message}`);
    }
}


/**
 * Add confirmation buttons for multi-turn order flow
 */
function addConfirmationButtons(data) {
    const lastBubble = chatContainer.lastElementChild?.querySelector('.bubble');
    if (!lastBubble) return;

    const actionDiv = document.createElement('div');
    actionDiv.className = 'action-buttons';

    if (data && data.step === 'quantity_choice' && data.choices && data.choices.length === 2) {
        // Quantity choice: two buttons with the offered quantities
        const unit = data.unit || 'kg';
        data.choices.forEach(qty => {
            const btn = document.createElement('button');
            btn.className = 'btn-action btn-confirm';
            btn.textContent = `${qty} ${unit}`;
            btn.onclick = () => {
                messageInput.value = String(qty);
                sendMessage();
            };
            actionDiv.appendChild(btn);
        });
    } else {
        // Yes/No buttons for need_check, moq_check, etc.
        const yesBtn = document.createElement('button');
        yesBtn.className = 'btn-action btn-confirm';
        yesBtn.textContent = 'Yes';
        yesBtn.onclick = () => {
            messageInput.value = 'yes';
            sendMessage();
        };

        const noBtn = document.createElement('button');
        noBtn.className = 'btn-action btn-cancel';
        noBtn.textContent = 'No';
        noBtn.onclick = () => {
            messageInput.value = 'no';
            sendMessage();
        };

        actionDiv.appendChild(yesBtn);
        actionDiv.appendChild(noBtn);
    }

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
