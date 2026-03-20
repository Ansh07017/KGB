// 1. Chatbot API Call
async function sendMessage() {
    const inputField = document.getElementById('userInput');
    const message = inputField.value.trim();
    if (!message) return;

    appendMessage(message, 'user-message');
    inputField.value = '';
    document.getElementById('loadingIndicator').style.display = 'block';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: message })
        });
        const data = await response.json();
        
        document.getElementById('loadingIndicator').style.display = 'none';
        if(data.error) {
            appendMessage("Error: " + data.error, 'bot-message');
        } else {
            appendMessage(data.response, 'bot-message');
        }
    } catch (error) {
        document.getElementById('loadingIndicator').style.display = 'none';
        appendMessage("Failed to connect to the LLM backend.", 'bot-message');
    }
}

function appendMessage(text, className) {
    const messagesDiv = document.getElementById('chatMessages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${className}`;
    msgDiv.innerText = text;
    messagesDiv.appendChild(msgDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight; // Auto-scroll to bottom
}

function handleKeyPress(event) {
    if (event.key === 'Enter') sendMessage();
}

// 2. Knowledge Graph API Call & Vis.js Setup
async function loadGraph() {
    try {
        const response = await fetch('/api/graph');
        const data = await response.json();

        const container = document.getElementById('mynetwork');
        const graphData = {
            nodes: new vis.DataSet(data.nodes),
            edges: new vis.DataSet(data.edges)
        };
        
        const options = {
            nodes: {
                shape: 'dot',
                size: 15,
                font: { size: 14, color: '#ffffff' },
                borderWidth: 2,
                color: { background: '#007acc', border: '#005f9e' }
            },
            edges: {
                width: 1,
                color: { color: '#555', highlight: '#007acc' },
                font: { size: 11, align: 'middle', color: '#aaaaaa' },
                arrows: { to: { enabled: true, scaleFactor: 0.5 } }
            },
            physics: {
                barnesHut: { gravitationalConstant: -2000, centralGravity: 0.3, springLength: 150 },
                stabilization: { iterations: 150 }
            }
        };

        new vis.Network(container, graphData, options);
    } catch (error) {
        console.error("Failed to load graph:", error);
        document.getElementById('mynetwork').innerHTML = `<p style="padding: 20px; color: red;">Failed to load graph data. Make sure Neo4j is running.</p>`;
    }
}

// Load graph as soon as the page opens
window.onload = loadGraph;