import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
# Initialize Groq client (ensure GROQ_API_KEY is in your .env)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ---------------------------------------------------------
# AGENT 1: TICKET CLASSIFIER
# ---------------------------------------------------------
def agent_classify_ticket(ticket_text):
    """Analyzes the user's issue and categorizes it."""
    prompt = f"""
    You are an expert IT Support Triage Agent. 
    Analyze the following user query and categorize the issue.
    
    Categories: Hardware, Software, Network, Access, Unknown.
    
    User Query: "{ticket_text}"
    
    You must return ONLY a valid JSON object with two keys:
    - "category": (The chosen category)
    - "urgency": (Low, Medium, High, or Critical)
    """
    
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant", # Fast model for simple classification
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    return json.loads(response.choices[0].message.content)

# ---------------------------------------------------------
# AGENT 2: GRAPH EXPLORER (TOOL AGENT)
# ---------------------------------------------------------
# We pass your existing FAISS and Neo4j functions as "Tools" to this agent.
def agent_explore_knowledge(ticket_text, category, faiss_search_fn, neo4j_search_fn):
    """Executes search tools based on the classification."""
    
    # Tool 1: Vector Search (FAISS)
    vector_context = faiss_search_fn(ticket_text)
    
    # Tool 2: Graph Search (Neo4j) 
    # (If your Neo4j search takes specific entities, you'd extract them here. 
    # For now, we will assume you have a basic text-to-graph search function)
    graph_context = neo4j_search_fn(ticket_text) if neo4j_search_fn else "Graph context unavailable."
    
    # Combine the context from our tools
    combined_context = f"--- VECTOR DATABASE RESULTS ---\n{vector_context}\n\n--- GRAPH DATABASE RESULTS ---\n{graph_context}"
    return combined_context

# ---------------------------------------------------------
# AGENT 3: RESOLUTION WRITER
# ---------------------------------------------------------
def agent_write_resolution(ticket_text, category, context):
    """Drafts the final IT support response."""
    prompt = f"""
    You are a Senior IT Support Engineer.
    Write a clear, step-by-step resolution for the user's issue.
    
    Issue Category: {category}
    User Query: "{ticket_text}"
    
    Knowledge Base Context (Use this to formulate your answer):
    {context}
    
    Provide a professional, easy-to-follow troubleshooting guide. Do not invent steps not supported by the context.
    """
    
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.3
    )
    
    return response.choices[0].message.content

# ---------------------------------------------------------
# AGENT 4: RISK & COMPLIANCE VALIDATOR
# ---------------------------------------------------------
def agent_validate_risk(draft_resolution):
    """Reviews the drafted response for dangerous IT commands."""
    prompt = f"""
    You are a strictly enforced IT Security & Compliance Agent.
    Review the following drafted IT support resolution.
    
    Drafted Resolution:
    {draft_resolution}
    
    Determine if this resolution suggests any high-risk, destructive, or unauthorized actions (e.g., formatting drives, sharing passwords, modifying registry keys, dropping database tables).
    
    You must return ONLY a valid JSON object with two keys:
    - "is_safe": (boolean true or false)
    - "flag_reason": (string explaining why it is unsafe, or "None" if safe)
    """
    
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    return json.loads(response.choices[0].message.content)
# ---------------------------------------------------------
# THE ORCHESTRATOR
# ---------------------------------------------------------
def run_resolution_workflow(ticket_text, faiss_search_fn, neo4j_search_fn=None):
    """Runs the 4-agent pipeline and returns the final payload."""
    workflow_logs = []
    
    # 1. Classification
    workflow_logs.append("[Classifier Agent] Analyzing ticket...")
    classification = agent_classify_ticket(ticket_text)
    workflow_logs.append(f"[Classifier Agent] Categorized as: {classification['category']} (Urgency: {classification['urgency']})")
    
    # 2. Knowledge Retrieval (Tool Usage)
    workflow_logs.append("[Graph Explorer Agent] Querying FAISS and Neo4j tools...")
    context = agent_explore_knowledge(ticket_text, classification['category'], faiss_search_fn, neo4j_search_fn)
    workflow_logs.append("[Graph Explorer Agent] Knowledge context successfully retrieved.")
    
    # 3. Resolution Drafting
    workflow_logs.append("[Resolution Writer Agent] Drafting step-by-step response...")
    draft = agent_write_resolution(ticket_text, classification['category'], context)
    
    # 4. Risk Validation
    workflow_logs.append("[Validator Agent] Scanning draft for security compliance...")
    validation = agent_validate_risk(draft)
    
    if validation['is_safe']:
        workflow_logs.append("[Validator Agent] ✅ Resolution approved for user delivery.")
        final_status = "Approved"
    else:
        workflow_logs.append(f"[Validator Agent] ❌ SECURITY FLAG: {validation['flag_reason']}. Routing to Human Queue.")
        final_status = "Pending_Human_Review"
        
    return {
        "status": final_status,
        "classification": classification,
        "logs": workflow_logs,
        "resolution": draft,
        "safety_report": validation
    }