/**
 * AI Agent Arena — Frontend Logic
 * Handles chat panels, mode switching, broadcasting, and API communication.
 */

// ===== State =====
const API_BASE = '';
let currentLayout = 'single'; // 'single' | 'dual' | 'triple'
const panelStates = [
    { mode: 'agent_v2', messages: [], loading: false },
    { mode: 'agent_v1', messages: [], loading: false },
    { mode: 'chatbot', messages: [], loading: false },
];

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    autoResizeAllInputs();
    switchLayout('single');
});

// ===== Health Check =====
async function checkHealth() {
    const indicator = document.getElementById('statusIndicator');
    const dot = indicator.querySelector('.status-dot');
    const text = indicator.querySelector('.status-text');

    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
            const data = await res.json();
            dot.className = 'status-dot connected';
            text.textContent = `Online • ${data.provider || 'openai'}`;
        } else {
            dot.className = 'status-dot error';
            text.textContent = 'Server error';
        }
    } catch (e) {
        dot.className = 'status-dot error';
        text.textContent = 'Offline';
    }
}

// ===== Layout Switching =====
function switchLayout(layout) {
    currentLayout = layout;
    const container = document.getElementById('panelsContainer');
    const broadcast = document.getElementById('broadcastSection');

    // Update tabs
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.mode === layout);
    });

    // Remove old layout classes
    container.className = 'panels-container ' + layout;

    // Show/hide panels based on layout
    const panels = [
        document.getElementById('panel-0'),
        document.getElementById('panel-1'),
        document.getElementById('panel-2'),
    ];

    if (layout === 'single') {
        panels[0].classList.remove('hidden');
        panels[1].classList.add('hidden');
        panels[2].classList.add('hidden');
        broadcast.classList.add('hidden');
    } else if (layout === 'dual') {
        panels[0].classList.remove('hidden');
        panels[1].classList.remove('hidden');
        panels[2].classList.add('hidden');
        broadcast.classList.remove('hidden');
    } else if (layout === 'triple') {
        panels[0].classList.remove('hidden');
        panels[1].classList.remove('hidden');
        panels[2].classList.remove('hidden');
        broadcast.classList.remove('hidden');

        // Set default modes for triple view
        const s0 = document.getElementById('select-0');
        const s1 = document.getElementById('select-1');
        const s2 = document.getElementById('select-2');
        if (s0.value === s1.value || s0.value === s2.value || s1.value === s2.value) {
            s0.value = 'agent_v2';
            s1.value = 'agent_v1';
            s2.value = 'chatbot';
            updatePanelMode(0);
            updatePanelMode(1);
            updatePanelMode(2);
        }
    }

    // Update data-mode attributes
    updateAllPanelModes();
}

function updatePanelMode(index) {
    const select = document.getElementById(`select-${index}`);
    panelStates[index].mode = select.value;
    const panel = document.getElementById(`panel-${index}`);
    panel.setAttribute('data-mode', select.value);
}

function updateAllPanelModes() {
    for (let i = 0; i < 3; i++) {
        updatePanelMode(i);
    }
}

// ===== Message Handling =====
function getActiveIndices() {
    if (currentLayout === 'single') return [0];
    if (currentLayout === 'dual') return [0, 1];
    return [0, 1, 2];
}

function fillSuggestion(text) {
    const indices = getActiveIndices();
    if (currentLayout === 'single') {
        const input = document.getElementById(`input-0`);
        input.value = text;
        autoResize(input);
        input.focus();
    } else {
        const broadcastInput = document.getElementById('broadcastInput');
        broadcastInput.value = text;
        autoResize(broadcastInput);
        broadcastInput.focus();
    }
}

function handleKeyDown(event, panelIndex) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage(panelIndex);
    }
}

function handleBroadcastKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        broadcastMessage();
    }
}

async function sendMessage(panelIndex) {
    const input = document.getElementById(`input-${panelIndex}`);
    const message = input.value.trim();
    if (!message || panelStates[panelIndex].loading) return;

    input.value = '';
    autoResize(input);

    await processMessage(panelIndex, message);
}

async function broadcastMessage() {
    const input = document.getElementById('broadcastInput');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    autoResize(input);

    const indices = getActiveIndices();
    const promises = indices.map(i => processMessage(i, message));
    await Promise.allSettled(promises);
}

async function processMessage(panelIndex, message) {
    const state = panelStates[panelIndex];
    if (state.loading) return;

    state.loading = true;
    const sendBtn = document.getElementById(`send-${panelIndex}`);
    sendBtn.disabled = true;

    // Clear welcome message if first message
    const messagesEl = document.getElementById(`messages-${panelIndex}`);
    const welcome = messagesEl.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // Add user message
    appendMessage(panelIndex, 'user', message);

    // Show typing indicator
    showTyping(panelIndex);

    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                mode: state.mode,
            }),
        });

        hideTyping(panelIndex);

        if (res.ok) {
            const data = await res.json();
            appendMessage(panelIndex, 'bot', data.response, state.mode);
            updateMetrics(panelIndex, data.metrics, data.elapsed_ms);
        } else {
            const err = await res.json().catch(() => ({ error: 'Unknown error' }));
            appendMessage(panelIndex, 'bot', `❌ Error: ${err.error}`, 'error');
        }
    } catch (e) {
        hideTyping(panelIndex);
        appendMessage(panelIndex, 'bot', `❌ Network error: ${e.message}`, 'error');
    }

    state.loading = false;
    sendBtn.disabled = false;
}

function appendMessage(panelIndex, role, text, mode) {
    const messagesEl = document.getElementById(`messages-${panelIndex}`);

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';

    if (role === 'user') {
        avatar.textContent = '👤';
    } else {
        const modeMap = {
            chatbot: '💬',
            agent_v1: '🤖',
            agent_v2: '🧠',
            error: '⚠️',
        };
        avatar.textContent = modeMap[mode] || '🤖';
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    if (mode === 'error') bubble.classList.add('error-bubble');
    bubble.textContent = text;

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    messagesEl.appendChild(msgDiv);

    // Save to state
    panelStates[panelIndex].messages.push({ role, text, mode });

    // Scroll to bottom
    requestAnimationFrame(() => {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    });
}

function showTyping(panelIndex) {
    const messagesEl = document.getElementById(`messages-${panelIndex}`);

    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.id = `typing-${panelIndex}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    const modeMap = { chatbot: '💬', agent_v1: '🤖', agent_v2: '🧠' };
    avatar.textContent = modeMap[panelStates[panelIndex].mode] || '🤖';
    avatar.style.background = 'rgba(255,255,255,0.06)';
    avatar.style.border = '1px solid rgba(255,255,255,0.06)';

    const dots = document.createElement('div');
    dots.className = 'typing-dots';
    dots.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

    typingDiv.appendChild(avatar);
    typingDiv.appendChild(dots);
    messagesEl.appendChild(typingDiv);

    requestAnimationFrame(() => {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    });
}

function hideTyping(panelIndex) {
    const el = document.getElementById(`typing-${panelIndex}`);
    if (el) el.remove();
}

// ===== Metrics Display =====
function updateMetrics(panelIndex, metrics, elapsedMs) {
    const container = document.getElementById(`metrics-${panelIndex}`);
    if (!metrics || metrics.requests === 0) {
        container.innerHTML = '';
        return;
    }

    const badges = [];

    if (metrics.requests !== undefined) {
        badges.push(`<span class="metric-badge requests"><span class="metric-icon">📡</span>${metrics.requests} req</span>`);
    }

    if (metrics.total_tokens !== undefined) {
        badges.push(`<span class="metric-badge tokens"><span class="metric-icon">🔤</span>${metrics.total_tokens.toLocaleString()} tok</span>`);
    }

    if (metrics.total_cost_estimate_usd !== undefined) {
        const cost = metrics.total_cost_estimate_usd;
        badges.push(`<span class="metric-badge cost"><span class="metric-icon">💰</span>$${cost.toFixed(4)}</span>`);
    }

    if (elapsedMs !== undefined) {
        const sec = (elapsedMs / 1000).toFixed(1);
        badges.push(`<span class="metric-badge time"><span class="metric-icon">⏱️</span>${sec}s</span>`);
    }

    container.innerHTML = badges.join('');
}

// ===== Auto Resize Textareas =====
function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function autoResizeAllInputs() {
    document.querySelectorAll('.chat-input, .broadcast-textarea').forEach(input => {
        input.addEventListener('input', () => autoResize(input));
    });
}
