from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
import os
import re 
from neo4j import GraphDatabase
import faiss
import pickle
import numpy as np
import requests
from app.agents import run_resolution_workflow
from groq import Groq
import gc
import uuid
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Load environment variables
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "kgb-secret-key-change-in-production")

# --- 1. HYBRID ARCHITECTURE DETECTION ---
IS_CLOUD = os.environ.get('RENDER') is not None

if not IS_CLOUD:
    print("Detected Local Environment: Initializing High-Speed PyTorch Model...")
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
else:
    print("Detected Cloud Environment: Initializing Serverless Hugging Face API...")
    HF_API_KEY = os.getenv("HF_API_KEY")
    HF_API_URL = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

# --- 2. PATH RESOLUTION ---
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

hitl_queue_db = []

# --- 4. MONGODB SETUP ---
try:
    import certifi
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_client = MongoClient(
        MONGO_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000
    )
    # Force a real connection check immediately
    mongo_client.admin.command("ping")
    mongo_db = mongo_client["kgb_enterprise"]
    users_collection = mongo_db["users"]
    tickets_collection = mongo_db["tickets"]

    # Auto-create default admin if none exists
    if users_collection.count_documents({"role": "admin"}) == 0:
        default_email = os.getenv("ADMIN_EMAIL", "admin@kgb.local")
        default_password = os.getenv("ADMIN_PASSWORD", "admin123")
        users_collection.insert_one({
            "email": default_email,
            "password": generate_password_hash(default_password),
            "role": "admin",
            "name": "System Admin"
        })
        print(f"Default admin created: {default_email}")
    # Auto-create default user if none exists
    if users_collection.count_documents({"role": "user"}) == 0:
        default_user_email = os.getenv("USER_EMAIL", "user@kgb.com")
        default_user_password = os.getenv("USER_PASSWORD", "user_secure_2026")
        users_collection.insert_one({
            "email": default_user_email,
            "password": generate_password_hash(default_user_password),
            "role": "user",
            "name": "Default User"
        })
        print(f"Default user created: {default_user_email}")
    print("MongoDB Connected.")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")
    mongo_db = None
    users_collection = None
    tickets_collection = None
    MONGO_CRASH_REASON = str(e)
# ==========================================
# AUTH HELPERS
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def user_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_logged_in"):
            return redirect(url_for("user_login"))
        return f(*args, **kwargs)
    return decorated

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def landing():
    """The gateway landing page — routes users to /support or admins to /admin-login."""
    return render_template('landing.html')

@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    """Customer login form."""
    error = None
    if request.method == 'POST':
        action = request.form.get('action', 'login')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()

        if action == 'register':
            if not email or not password or not name:
                error = "All fields are required to register."
            elif users_collection is None:
                error = "Database unavailable."
            elif users_collection.find_one({"email": email}):
                error = "An account with this email already exists."
            else:
                users_collection.insert_one({
                    "email": email,
                    "password": generate_password_hash(password),
                    "role": "user",
                    "name": name
                })
                session["user_logged_in"] = True
                session["user_email"] = email
                session["user_name"] = name
                return redirect(url_for("support"))
        else:
            if users_collection is None:
                error = "Database unavailable."
            else:
                user = users_collection.find_one({"email": email, "role": "user"})
                if user and check_password_hash(user["password"], password):
                    session["user_logged_in"] = True
                    session["user_email"] = email
                    session["user_name"] = user.get("name", "User")
                    return redirect(url_for("support"))
                else:
                    global MONGO_CRASH_REASON
                    error = f"Database Crash: {MONGO_CRASH_REASON}"

    return render_template('user_login.html', error=error)

@app.route('/user-logout')
def user_logout():
    session.pop("user_logged_in", None)
    session.pop("user_email", None)
    session.pop("user_name", None)
    return redirect(url_for("user_login"))

@app.route('/support')
@user_login_required
def support():
    """Customer Desk — protected, users must be logged in."""
    return render_template('support.html', user_name=session.get("user_name", "User"), user_email=session.get("user_email", ""))

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login form backed by MongoDB credential check."""
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if users_collection is not None:
            user = users_collection.find_one({"email": email, "role": "admin"})
            if user and check_password_hash(user["password"], password):
                session["admin_logged_in"] = True
                session["admin_email"] = email
                session["admin_name"] = user.get("name", "Admin")
                return redirect(url_for("admin_dashboard"))
            else:
                error = "Invalid email or password."
        else:
            # THIS IS WHERE IT NEEDS TO BE!
            global MONGO_CRASH_REASON
            error = f"Database Crash: {MONGO_CRASH_REASON}"
            
    return render_template('admin_login.html', error=error)

@app.route('/admin-logout')
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route('/admin')
@login_required
def admin_dashboard():
    """Main dashboard — the existing graph + agent console. Protected by login."""
    return render_template('index.html')

@app.route('/queue')
@login_required
def hitl_queue():
    return render_template('queue.html', queue=hitl_queue_db)

# ==========================================
# API ROUTES
# ==========================================

@app.route('/health', methods=['GET'])
def health_check():
    try:
        with driver.session() as session_neo:
            session_neo.run("RETURN 1")
        return jsonify({"status": "healthy", "server": "awake", "neo4j_auradb": "connected and active"}), 200
    except Exception as e:
        return jsonify({"status": "degraded", "error": "Database connection failed", "details": str(e)}), 503

@app.route('/api/graph', methods=['GET'])
@login_required
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
            nodes[record["source_id"]] = {"id": record["source_id"], "label": record["source_name"], "group": record["source_label"]}
            nodes[record["target_id"]] = {"id": record["target_id"], "label": record["target_name"], "group": record["target_label"]}
            edges.append({"from": record["source_id"], "to": record["target_id"], "label": record["rel_type"]})
        return {"nodes": list(nodes.values()), "edges": edges}
    with driver.session() as session_neo:
        graph_data = session_neo.execute_read(fetch_graph)
    return jsonify(graph_data)

@app.route('/api/ingest', methods=['POST'])
def ingest_ticket():
    """Receives a support ticket from the /support page and stores it in MongoDB."""
    data = request.json
    device = data.get("device", "").strip()
    issue = data.get("issue", "").strip()
    if not device or not issue:
        return jsonify({"error": "Device and issue are required."}), 400

    ticket_text = f"Device: {device}. Issue: {issue}"
    ticket_id = str(uuid.uuid4())[:8].upper()

    ticket_doc = {
        "id": ticket_id,
        "device": device,
        "issue": issue,
        "text": ticket_text,
        "status": "AI Analyzing",
        "resolution": None,
        "session_id": data.get("session_id", "unknown"),
        "user_email": session.get("user_email", data.get("user_email", "unknown"))
    }

    if tickets_collection is not None:
        tickets_collection.insert_one(ticket_doc)

    return jsonify({"ticket_id": ticket_id, "status": "AI Analyzing"})

@app.route('/api/tickets', methods=['GET'])
def get_tickets():
    """Returns all tickets for the logged-in user (permanent, cross-session)."""
    user_email = session.get("user_email")
    session_id = request.args.get("session_id", "unknown")
    if tickets_collection is None:
        return jsonify([])
    # Prefer user_email (permanent) over session_id (ephemeral)
    if user_email and user_email != "unknown":
        tickets = list(tickets_collection.find({"user_email": user_email}, {"_id": 0}))
    else:
        tickets = list(tickets_collection.find({"session_id": session_id}, {"_id": 0}))
    # Sort newest first
    tickets = sorted(tickets, key=lambda t: t.get("id", ""), reverse=True)
    return jsonify(tickets)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get("query", "")
    ticket_id = data.get("ticket_id", None)

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        gc.collect()

        def faiss_search_tool(search_query):
            if IS_CLOUD:
                response = requests.post(HF_API_URL, headers=headers, json={"inputs": search_query})
                if response.status_code != 200:
                    return "Error: Cloud Engine Timeout."
                query_vector = np.array(response.json()).astype("float32")
            else:
                query_vector = model.encode([search_query]).astype("float32")
            distances, indices = index.search(query_vector.reshape(1, -1), 5)
            return "\n".join([texts[idx] for idx in indices[0]])

        def neo4j_search_tool(search_query):
            return "Graph database active. Entity relations available."

        agent_payload = run_resolution_workflow(
            ticket_text=query,
            faiss_search_fn=faiss_search_tool,
            neo4j_search_fn=neo4j_search_tool
        )

        focus_nodes = list(set(re.findall(r'Ticket_\d+|[A-Z][a-z]+', agent_payload['resolution'])))
        new_ticket_id = ticket_id or str(uuid.uuid4())[:8]

        if agent_payload['status'] == "Pending_Human_Review":
            hitl_queue_db.append({
                "id": new_ticket_id,
                "query": query,
                "draft": agent_payload["resolution"],
                "flag": agent_payload["safety_report"]["flag_reason"]
            })
            # Update MongoDB status
            if tickets_collection is not None and ticket_id:
                tickets_collection.update_one({"id": ticket_id}, {"$set": {"status": "Pending Admin Review"}})
        else:
            # Auto-approved: update ticket status and store resolution
            if tickets_collection is not None and ticket_id:
                tickets_collection.update_one(
                    {"id": ticket_id},
                    {"$set": {"status": "Resolved", "resolution": agent_payload["resolution"]}}
                )

        return jsonify({
            "response": agent_payload["resolution"],
            "logs": agent_payload["logs"],
            "status": agent_payload["status"],
            "classification": agent_payload["classification"],
            "safety_report": agent_payload["safety_report"],
            "focus_nodes": focus_nodes
        })

    except Exception as e:
        print(f"Backend Crash Caught: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/queue/action/<ticket_id>', methods=['POST'])
@login_required
def process_queue_action(ticket_id):
    global hitl_queue_db
    action = request.json.get('action')
    edited_resolution = request.json.get('resolution', None)
    hitl_ticket = next((t for t in hitl_queue_db if t['id'] == ticket_id), None)
    hitl_queue_db = [t for t in hitl_queue_db if t['id'] != ticket_id]
    if tickets_collection is not None:
        if action == 'approve':
            resolution_text = edited_resolution or (hitl_ticket['draft'] if hitl_ticket else 'Reviewed and approved by admin.')
            tickets_collection.update_one(
                {'id': ticket_id},
                {'$set': {'status': 'Resolved', 'resolution': resolution_text}}
            )
        else:
            tickets_collection.update_one(
                {'id': ticket_id},
                {'$set': {'status': 'Rejected', 'resolution': 'This request was reviewed and rejected. Please contact IT support directly.'}}
            )
    return jsonify({'status': 'success', 'message': f'Ticket {action}d successfully.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
