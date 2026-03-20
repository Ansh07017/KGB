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

# Load environment variables
load_dotenv()
app = Flask(__name__)

# --- 1. PATH RESOLUTION ---
base_dir = os.path.dirname(os.path.abspath(__file__)) 
project_root = os.path.dirname(base_dir) 

faiss_path = os.path.join(project_root, "data", "vector_index.faiss")
pkl_path = os.path.join(project_root, "data", "ticket_texts.pkl")

# --- 2. INITIALIZE ENGINES ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Neo4j Connection
URI = os.getenv("db_Url")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

# FAISS & Sentence Transformers
print("Loading Knowledge Base...")
index = faiss.read_index(faiss_path)
with open(pkl_path, "rb") as f:
    texts = pickle.load(f)
model = SentenceTransformer("all-MiniLM-L6-v2")
print("KGB System Online.")

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/graph', methods=['GET'])
def get_graph():
    def fetch_graph(tx):
        # elementId() is used to maintain compatibility with Neo4j 5.x+
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
            # Nodes include a 'group' property to enable color-coding in the frontend
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

    # Step 1: Semantic Search in FAISS
    query_vector = model.encode([query]).astype("float32")
    distances, indices = index.search(np.array(query_vector), 5)
    
    context_text = "\n".join([texts[idx] for idx in indices[0]])

    # Step 2: Prompt Construction
    prompt = f"""
    You are an Enterprise IT support assistant. 
    Analyze the following support tickets to answer the query.
    
    Context: {context_text}
    User Question: {query}
    """

    # Step 3: Groq Inference using Llama 3.1
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 
        )
        
        ai_response = completion.choices[0].message.content
        
        # We extract specific entity patterns so the frontend can zoom to them
        # This matches 'Ticket_X' or words starting with capital letters (potential entities)
        focus_nodes = list(set(re.findall(r'Ticket_\d+|[A-Z][a-z]+', context_text)))
        
        return jsonify({
            "response": ai_response,
            "focus_nodes": focus_nodes
        })
        
    except Exception as e:
        print(f"Groq API Error: {e}")
        return jsonify({"error": "LLM Inference failed."}), 500
    
if __name__ == '__main__':
    app.run(debug=True)