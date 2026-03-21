from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import os
import re 
from neo4j import GraphDatabase
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from groq import Groq
import torch

# Load environment variables
load_dotenv()
app = Flask(__name__)

# CRITICAL: Prevent PyTorch from spawning multiple threads and causing an OOM kill on Render
torch.set_num_threads(1)

# --- 1. PATH RESOLUTION (Cloud-Optimized) ---
# This ensures data is found whether running locally or on Render's file system
base_dir = os.path.dirname(os.path.abspath(__file__)) 
project_root = os.path.dirname(base_dir) 

# Check if data exists in the project root (Standard Architecture)
data_dir = os.path.join(project_root, "data")
if not os.path.exists(data_dir):
    # Fallback for alternative directory structures
    data_dir = os.path.join(base_dir, "data")

faiss_path = os.path.join(data_dir, "vector_index.faiss")
pkl_path = os.path.join(data_dir, "ticket_texts.pkl")

# --- 2. INITIALIZE ENGINES ---
# Groq Client for High-Speed Inference
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Neo4j Cloud Connection (AuraDB)
URI = os.getenv("db_Url")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

# Use max_connection_lifetime to prevent 'Broken Pipe' errors on Aura Cloud
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD), max_connection_lifetime=200)

# FAISS & Sentence Transformers (Memory-Optimized for 512MB)
print("Initializing KGB Neural Engine...")
try:
    index = faiss.read_index(faiss_path)
    with open(pkl_path, "rb") as f:
        texts = pickle.load(f)
    
    # CRITICAL: Force CPU and small model usage to prevent OOM (Out of Memory) crashes
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu") 
    print("KGB System Online.")
except Exception as e:
    print(f"Deployment Critical Error: {e}")

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/graph', methods=['GET'])
def get_graph():
    def fetch_graph(tx):
        # elementId() maintains compatibility with Neo4j 5.x Aura instances
        query = """
        MATCH (n)-[r]->(m) 
        RETURN elementId(n) AS source_id, labels(n)[0] AS source_label, n.name AS source_name, 
               type(r) AS rel_type, 
               elementId(m) AS target_id, labels(m)[0] AS target_label, m.name AS target_name 
        LIMIT 200
        """
        result = tx.run(query)
        nodes = {}
        edges = []
        
        for record in result:
            nodes[record["source_id"]] = {
                "id": record["source_id"], 
                "label": record["source_name"], 
                "group": record["source_label"]
            }
            nodes[record["target_id"]] = {
                "id": record["target_id"], 
                "label": record["target_name"], 
                "group": record["target_label"]
            }
            edges.append({
                "from": record["source_id"], 
                "to": record["target_id"], 
                "label": record["rel_type"]
            })
            
        return {"nodes": list(nodes.values()), "edges": edges}

    with driver.session() as session:
        graph_data = session.execute_read(fetch_graph)
    
    return jsonify(graph_data)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get("query", "")
    
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Step 1: Semantic Search in FAISS (Now protected!)
        query_vector = model.encode([query]).astype("float32")
        distances, indices = index.search(np.array(query_vector).reshape(1, -1), 5)
        
        context_text = "\n".join([texts[idx] for idx in indices[0]])

        # Step 2: Prompt Construction for Llama 3.1
        prompt = f"""
        You are an Enterprise IT support assistant. 
        Analyze the following support tickets to answer the query.
        
        Context: {context_text}
        User Question: {query}
        """

        # Step 3: Groq Inference using Llama-3.1-8b-instant
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 
        )
        
        ai_response = completion.choices[0].message.content
        
        # Entity extraction for frontend auto-zoom
        focus_nodes = list(set(re.findall(r'Ticket_\d+|[A-Z][a-z]+', context_text)))
        
        return jsonify({
            "response": ai_response,
            "focus_nodes": focus_nodes
        })
        
    except Exception as e:
        print(f"Backend Crash Caught: {e}")
        return jsonify({"error": str(e)}), 500
    
# Render uses Gunicorn, but this allows for local testing
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)