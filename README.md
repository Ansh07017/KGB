# AI Knowledge Graph Builder for Enterprise Intelligence
Developed as part of Infosys Springboard Internship  
Author: Satwik Panchagnula

---

# 📖 Project Overview

This project builds an enterprise-level **AI-powered Knowledge Graph system** from structured and unstructured customer support data.

The system extracts entities and relationships from support tickets, constructs a **knowledge graph**, and enables **intelligent semantic search with a Retrieval-Augmented Generation (RAG) pipeline** to provide automated troubleshooting responses.

---

# 🎯 Objective

To transform enterprise support ticket data into a scalable knowledge graph that enables:

- Relationship-based analysis
- Intelligent troubleshooting
- Semantic search over support tickets
- AI-assisted IT support responses

---

# 🏗 Project Architecture

```
Raw Dataset  
      ↓
Data Cleaning (Pandas)
      ↓
Structured Triple Extraction
      ↓
LLM-based Entity Extraction (Ollama + Mistral)
      ↓
Merge Structured + LLM Triples
      ↓
Neo4j Graph Construction
      ↓
Graph Validation
      ↓
Embedding Generation (Sentence Transformers)
      ↓
Vector Database (FAISS)
      ↓
Semantic Search
      ↓
Retrieval-Augmented Generation (RAG)
```

---

# 🚀 Technologies Used

- Python
- Pandas
- Sentence Transformers
- FAISS (Vector Database)
- Ollama (Mistral LLM)
- Neo4j Graph Database
- Flask
- GitHub

---

# ✅ Milestone 1 – Data Ingestion & Preprocessing

### Tasks Completed

- Data cleaning using Pandas
- Removal of null values and duplicates
- Data normalization
- Feature enrichment
- Processed dataset generation

### Output

```
cleaned_tickets.xlsx
```

---

# ✅ Milestone 2 – Entity Extraction & Graph Construction

## Step 1: Structured Triple Extraction

Extracted **entity–relationship–entity triples** from structured columns.

Example triples:

```
Customer → RAISED → Ticket
Ticket → HAS_SEVERITY → Severity
Ticket → SUBMITTED_VIA → Channel
```

Output:

```
structured_triples.csv
```

---

## Step 2: LLM-Based NER (Ollama + Mistral)

Used the **Mistral LLM** to extract semantic relationships from ticket descriptions.

Example triples:

```
(Dell XPS, EXPERIENCING, Not turning on)
(Dell XPS, REQUIRED_ACTION, Troubleshoot power issues)
```

Output:

```
llm_triples.csv
```

---

## Step 3: Graph Construction (Neo4j)

- Combined structured and LLM-generated triples
- Inserted triples into Neo4j using the Python Neo4j driver
- Constructed graph nodes and relationships

### Graph Statistics

```
Graph Statistics (Sample Run – First 20 Rows)

Nodes: ~160+
Relationships: ~240+

Note: The above statistics correspond to a test run on the first 20 records.
Running the pipeline on the full dataset will generate a significantly larger knowledge graph.
```

---

## Step 4: Graph Validation

Validated graph integrity using Cypher queries.

### Count Nodes

```cypher
MATCH (n)
RETURN count(n);
```

### Count Relationships

```cypher
MATCH ()-[r]->()
RETURN count(r);
```

### Visualize Graph

```cypher
MATCH (n)-[r]->(m)
RETURN n,r,m
LIMIT 25;
```

---

# ⚙️ Installation & Setup

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/panchagnula-satwik/AI-Knowledge-Graph-Builder.git
cd AI-Knowledge-Graph-Builder
```

---

## 2️⃣ Create Virtual Environment

```bash
python -m venv .venv
```

Activate environment:

Windows

```bash
.venv\Scripts\activate
```

Mac/Linux

```bash
source .venv/bin/activate
```

---

## 3️⃣ Install Dependencies

```bash
pip install pandas ollama neo4j flask openpyxl sentence-transformers faiss-cpu
```

---

# 🤖 LLM Setup (Ollama)

Install Ollama and pull the Mistral model.

```bash
ollama pull mistral
```

Start Ollama server:

```bash
ollama serve
```

---

# 🧠 Neo4j Setup

1. Install **Neo4j Desktop**
2. Create a local database
3. Start the database

Connection details:

```
bolt://localhost:7687
username: neo4j
password: <your-password>
```

Insert triples into Neo4j:

```bash
python scripts/push_to_neo4j.py
```

---

# 📁 Project Structure

```
AI-Knowledge-Graph-Builder
│
├── app
│   └── app.py
│
├── data
│   ├── raw
│   │   └── tickets.xlsx
│   │
│   ├── processed
│   │   ├── cleaned_tickets.xlsx
│   │   ├── structured_triples.csv
│   │   ├── llm_triples.csv
│   │   └── final_triples.csv
│   │
│   ├── vector_index.faiss
│   └── ticket_texts.pkl
│
├── notebooks
│   └── milestone2_llm_extraction.ipynb
│
├── scripts
│   ├── push_to_neo4j.py
│   ├── build_vector_index.py
│   ├── semantic_search.py
│   └── rag_pipeline.py
│
└── README.md
```

---

# 📊 Current Status

```
Milestone 1 ✅ Completed
Milestone 2 ✅ Completed
Milestone 3 ✅ Completed
Milestone 4 ✅ Completed
```

---

# 📌 Future Work

- Advanced graph analytics
- Knowledge graph querying
- Graph visualization dashboards
- Integration with enterprise AI applications

---

# ✅ Milestone 3 – Semantic Search & RAG Pipeline

## Objective

Enable intelligent search and automated troubleshooting responses by integrating **semantic search** with a **Retrieval-Augmented Generation (RAG) pipeline**.

---

## Step 1: Embedding Generation

Ticket descriptions were converted into **vector embeddings** using:

```
all-MiniLM-L6-v2
```

This allows the system to understand **semantic similarity** between support tickets.

Example:

```
User Query: laptop not turning on
```

Even if a ticket says:

```
Device fails to power on
```

the system still retrieves it correctly.

---

## Step 2: Vector Database (FAISS)

Embeddings were stored in a **FAISS vector database** for fast similarity search.

Generated files:

```
vector_index.faiss
ticket_texts.pkl
```

Purpose:

| File | Description |
|-----|-------------|
| vector_index.faiss | Stores ticket embeddings |
| ticket_texts.pkl | Stores ticket descriptions mapped to vectors |

---

## Step 3: Semantic Search

User queries are converted into embeddings and matched against the FAISS index.

Example query:

```
my laptop battery drains quickly
```

Semantic search retrieves tickets discussing:

```
battery failure
power management issues
device overheating
```

even without exact keyword matches.

---

## Step 4: Retrieval-Augmented Generation (RAG)

The retrieved tickets are used as **context for the LLM**.

Pipeline:

```
User Query
      ↓
Query Embedding
      ↓
Semantic Search (FAISS)
      ↓
Retrieve Relevant Tickets
      ↓
Context Injection
      ↓
LLM Response (Ollama + Mistral)
```

---

## Example Interaction

User Query:

```
my laptop battery drains quickly
```

Generated Response:

```
1. Check battery health
2. Update power management drivers
3. Reduce background applications
4. Adjust power settings
5. Replace battery if necessary
```

---

## Final Outcome

The system now functions as an **AI-powered IT support assistant** capable of:

- Understanding natural language queries
- Performing semantic search over support tickets
- Retrieving relevant troubleshooting cases
- Generating intelligent repair recommendations using an LLM
