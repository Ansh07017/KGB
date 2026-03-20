from flask import Flask, jsonify, render_template, request
import os
from neo4j import GraphDatabase
import faiss
import pickle
import numpy as np
import ollama
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load environment variables (Make sure your .env is in the root folder)
load_dotenv()

app = Flask(__name__)

# --- 1. PATH RESOLUTION ---
# Since this file is inside the 'app/' folder, we need to point to the root 'data/' folder
base_dir = os.path.dirname(os.path.abspath(__file__)) 
project_root = os.path.dirname(base_dir) 

faiss_path = os.path.join(project_root, "data", "vector_index.faiss")
pkl_path = os.path.join(project_root, "data", "ticket_texts.pkl")

# --- 2. INITIALIZE NEO4J ---
URI = os.getenv("db_Url")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

# --- 3. INITIALIZE RAG ENGINES ---
print("Loading FAISS index and Sentence Transformer. This might take a few seconds...")
index = faiss.read_index(faiss_path)
with open(pkl_path, "rb") as f:
    texts = pickle.load(f)
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Engines loaded! Starting Flask server...")

# ==========================================
# ROUTES
# ==========================================

# 1. THE FRONTEND UI ROUTE
@app.route('/')
def home():
    # We will build this index.html file in Phase 2!
    return render_template('index.html')

# 2. THE KNOWLEDGE GRAPH API
@app.route('/api/graph', methods=['GET'])
def get_graph():
    def fetch_graph(tx):
        # Fetch up to 150 relationships to prevent the browser from lagging
        query = """
        MATCH (n)-[r]->(m) 
        RETURN id(n) AS source_id, labels(n)[0] AS source_label, n.name AS source_name, 
               type(r) AS rel_type, 
               id(m) AS target_id, labels(m)[0] AS target_label, m.name AS target_name 
        LIMIT 150
        """
        result = tx.run(query)
        nodes = {}
        edges = []
        
        for record in result:
            # Format nodes for Vis.js
            nodes[record["source_id"]] = {"id": record["source_id"], "label": record["source_name"], "group": record["source_label"]}
            nodes[record["target_id"]] = {"id": record["target_id"], "label": record["target_name"], "group": record["target_label"]}
            # Format edges for Vis.js
            edges.append({"from": record["source_id"], "to": record["target_id"], "label": record["rel_type"]})
            
        return {"nodes": list(nodes.values()), "edges": edges}

    with driver.session() as session:
        graph_data = session.execute_read(fetch_graph)
    
    return jsonify(graph_data)

# 3. THE RAG CHATBOT API
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get("query", "")
    
    if not query:
        return jsonify({"error": "No query provided"}), 400

    # Step 1: Semantic Search in FAISS
    query_vector = model.encode([query])
    query_vector = np.array(query_vector).astype("float32")
    distances, indices = index.search(query_vector, 5)
    
    context = [texts[idx] for idx in indices[0]]
    context_text = "\n".join(context)

    # Step 2: RAG Context Injection
    prompt = f"""
    You are an IT support assistant.
    Use the following support tickets as context to answer the user's question.
    
    Context:
    {context_text}
    
    User Question:
    {query}
    
    Provide a helpful troubleshooting answer. Do not mention the context directly.
    """

    # Step 3: Ask Mistral
    response = ollama.chat(
        model="mistral",
        messages=[{"role": "user", "content": prompt}]
    )

    return jsonify({"response": response["message"]["content"]})

if __name__ == '__main__':
    app.run(debug=True)