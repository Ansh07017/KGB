// Global variables for the Enterprise Neural Engine
let network = null;
let nodesDataSet = null;
let edgesDataSet = null;

// --- 1. SMART CHATBOT LOGIC (RAG + SYNC) ---
async function sendMessage() {
    const inputField = document.getElementById('userInput');
    const message = inputField.value.trim();
    if (!message) return;

    appendMessage(message, 'user-message');
    inputField.value = '';
    
    const chatBox = document.getElementById('chatMessages');
    const thinkingMsg = document.createElement('div');
    thinkingMsg.className = 'message bot-message';
    thinkingMsg.id = 'thinking-msg';
    thinkingMsg.innerHTML = '<span class="glow-text">QUERYING NEURAL DATABASE...</span>';
    chatBox.appendChild(thinkingMsg);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: message })
        });
        const data = await response.json();
        
        const loader = document.getElementById('thinking-msg');
        if (loader) loader.remove();
        
        if(data.error) {
            appendMessage("Error: " + data.error, 'bot-message');
        } else {
            appendMessage(data.response, 'bot-message');
            
            // --- BI-DIRECTIONAL SYNC: SMART ZOOM ---
            if (data.focus_nodes && data.focus_nodes.length > 0 && network) {
                let targetNodeIds = [];
                nodesDataSet.forEach(node => {
                    // Match either the label or part of the name
                    if (data.focus_nodes.some(fn => node.label.includes(fn))) {
                        targetNodeIds.push(node.id);
                    }
                });
                
                if (targetNodeIds.length > 0) {
                    network.fit({ 
                        nodes: targetNodeIds, 
                        animation: { duration: 1500, easingFunction: "easeInOutQuart" } 
                    });
                }
            }
        }
    } catch (error) {
        if (document.getElementById('thinking-msg')) document.getElementById('thinking-msg').remove();
        appendMessage("SYSTEM OFFLINE. CHECK BACKEND.", 'bot-message');
    }
}

// Formats AI response with bolding and line breaks
function appendMessage(text, className) {
    const messagesDiv = document.getElementById('chatMessages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${className}`;
    const formattedText = text.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    msgDiv.innerHTML = formattedText;
    messagesDiv.appendChild(msgDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function handleKeyPress(event) { if (event.key === 'Enter') sendMessage(); }

// --- 2. GRAPH SEARCH UTILITY ---
function searchNode() {
    const searchTerm = document.getElementById('graphSearch').value.toLowerCase();
    if (!searchTerm) return;

    const foundNode = nodesDataSet.get({
        filter: (item) => item.label.toLowerCase().includes(searchTerm)
    });

    if (foundNode.length > 0) {
        network.focus(foundNode[0].id, {
            scale: 1.2,
            animation: { duration: 1000, easingFunction: "easeInOutQuad" }
        });
        network.selectNodes([foundNode[0].id]);
    }
}

// --- 3. GRAPH ENGINE (STYLING & PHYSICS) ---
async function loadGraph() {
    try {
        const response = await fetch('/api/graph');
        const data = await response.json();

        // DYNAMIC SCALING & COLOR-CODING LOGIC
        const styledNodes = data.nodes.map(node => {
            const connections = data.edges.filter(e => e.from === node.id || e.to === node.id).length;
            
            // Set dynamic size based on importance
            const baseSize = 15;
            const dynamicSize = baseSize + (connections * 2.5);

            // Assign colors based on node group/label
            const COLORS = {
    ticket: '#ff3333',
    server: '#3388ff',
    user: '#33ff88',
    issue: '#f4f02a',
    device: '#fff',
    other: '#a76161'
};
let group = node.group?.toLowerCase();

let bg = COLORS[group] || COLORS['other'];

let colorSettings = {
    background: bg,
    border: bg   // 🔥 SAME COLOR → no mismatch
};
            return {
                ...node,
                size: dynamicSize,
                color: { 
                    ...colorSettings, 
                    highlight: { background: '#fff', border: '#ff3333' } 
                },
                font: {
    color: '#cccccc'
                }
            };
        });

        const container = document.getElementById('mynetwork');
        nodesDataSet = new vis.DataSet(styledNodes);
        edgesDataSet = new vis.DataSet(data.edges);
        
        const options = {
            nodes: {
                shape: 'dot',
                borderWidth: 2,
                shadow: false
            },
            edges: {
                width: 1.2,
                color: { color: 'rgba(255, 51, 51, 0.2)', highlight: '#ff3333', hover: '#ff3333' },
                arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                smooth: { type: 'continuous', roundness: 0.5 }
            },
            physics: {
    enabled: true,
    forceAtlas2Based: {
        gravitationalConstant: -500,   // 🔥 stronger repulsion
        centralGravity: 0.003,
        springLength: 180,             // 🔥 more spacing
        springConstant: 0.04,
        damping: 0.6
    },
    solver: 'forceAtlas2Based',
    stabilization: { iterations: 300 }
},
            interaction: { hover: true, tooltipDelay: 200, hideEdgesOnDrag: true }
        };

        network = new vis.Network(container, { nodes: nodesDataSet, edges: edgesDataSet }, options);

        // HIDE LOADER ONLY AFTER PHYSICS STABILIZE
        network.once("stabilizationIterationsDone", function () {
            document.getElementById('loader-overlay').style.opacity = '0';
            setTimeout(() => {
                document.getElementById('loader-overlay').style.display = 'none';
                network.fit({ animation: { duration: 2000 } });
            }, 500);
        });

        // MINIMALIST CLICK INTERACTION
        network.on("click", function (params) {
            const box = document.getElementById('mini-intel-box');
            if (params.nodes.length > 0) {
                const node = nodesDataSet.get(params.nodes[0]);
                document.getElementById('entity-name-display').innerText = node.label;
                box.classList.remove('hidden');
                
                document.getElementById('userInput').value = `Explain context for: ${node.label}`;
                sendMessage();
            } else {
                box.classList.add('hidden');
            }
        });

    } catch (error) {
        console.error("GRAPH SYNC FAILED:", error);
    }
}

window.onload = loadGraph;