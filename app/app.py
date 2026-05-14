from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import os
import re 
from neo4j import GraphDatabase
import faiss
import pickle
import numpy as np
import requests
from groq import Groq
import gc

# Load environment variables
load_dotenv()
app = Flask(__name__)

# --- 1. HYBRID ARCHITECTURE DETECTION ---
# Render automatically sets the 'RENDER' environment variable to 'true'
IS_CLOUD = os.environ.get('RENDER') is not None

if not IS_CLOUD:
    print("Detected Local Environment: Initializing High-Speed PyTorch Model...")
    from sentence_transformers import SentenceTransformer
    import torch
    # Keep local memory flat just in case
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
else:
    print("Detected Cloud Environment: Initializing Serverless Hugging Face API...")
    HF_API_KEY = os.getenv("HF_API_KEY")
    HF_API_URL = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

# --- 2. PATH RESOLUTION (Cloud-Optimized) ---
base_dir = os.path.dirname(os.path.abspath(__file__)) 
project_root = os.path.dirname(base_dir) 

data_dir = os.path.join(project_root, "data")
if not os.path.exists(data_dir):
    data_dir = os.path.join(base_dir, "data")

faiss_path = os.path.join(data_dir, "vector_index.faiss")
pkl_path = os.path.join(data_dir, "ticket_texts.pkl")

# --- 3. INITIALIZE ENGINES ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

URI = os.getenv("db_Url")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD), max_connection_lifetime=200)

try:
    index = faiss.read_index(faiss_path)
    with open(pkl_path, "rb") as f:
        texts = pickle.load(f)
    print("KGB Database Connected.")
except Exception as e:
    print(f"Data Load Error: {e}")

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

from flask import jsonify

@app.route('/health', methods=['GET'])
def health_check():
    """
    Uptime route to prevent Render from sleeping AND keep Neo4j AuraDB awake.
    """
    try:
        with driver.session() as session:
            session.run("RETURN 1") 
            
        return jsonify({
            "status": "healthy", 
            "server": "awake",
            "neo4j_auradb": "connected and active"
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "degraded", 
            "error": "Database connection failed", 
            "details": str(e)
        }), 503

@app.route('/api/graph', methods=['GET'])
def get_graph():
    def fetch_graph(tx):
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
                "id": record["source_id"], "label": record["source_name"], "group": record["source_label"]
            }
            nodes[record["target_id"]] = {
                "id": record["target_id"], "label": record["target_name"], "group": record["target_label"]
            }
            edges.append({
                "from": record["source_id"], "to": record["target_id"], "label": record["rel_type"]
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
        gc.collect() 
        
        # Step 1: Hybrid Semantic Embedding
        if IS_CLOUD:
            # Cloud: Use API to save RAM
            response = requests.post(HF_API_URL, headers=headers, json={"inputs": query})
            if response.status_code != 200:
                return jsonify({"error": f"Cloud Embedding Engine Timeout: {response.text}"}), 502
            query_vector = np.array(response.json()).astype("float32")
        else:
            # Local: Use PyTorch for speed
            query_vector = model.encode([query]).astype("float32")
        
        # Step 2: Semantic Search in FAISS
        distances, indices = index.search(query_vector.reshape(1, -1), 5)
        context_text = "\n".join([texts[idx] for idx in indices[0]])

        # Step 3: Prompt Construction
        prompt = f"""
        You are an Enterprise IT support assistant. 
        Analyze the following support tickets to answer the query.
        Context: {context_text}
        User Question: {query}
        """

        # Step 4: Groq Inference
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 
        )
        ai_response = completion.choices[0].message.content
        
        focus_nodes = list(set(re.findall(r'Ticket_\d+|[A-Z][a-z]+', context_text)))
        
        return jsonify({
            "response": ai_response,
            "focus_nodes": focus_nodes
        })
        
    except Exception as e:
        print(f"Backend Crash Caught: {e}")
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)