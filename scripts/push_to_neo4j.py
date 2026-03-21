from neo4j import GraphDatabase
import pandas as pd
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Load triples
df = pd.read_csv("data/processed/structured_triples.csv")

# Remove rows with missing values
df = df.dropna(subset=["Subject", "Predicate", "Object"])

URI = os.getenv("db_Url")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD),encrypted=True)

def get_label(name):
    name = name.lower()

    if "ticket" in name:
        return "Ticket"
    elif "server" in name:
        return "Server"
    elif "user" in name:
        return "User"
    elif "issue" in name or "error" in name:
        return "Issue"
    elif "laptop" in name or "printer" in name or "tv" in name or "phone" in name or "camera" in name or "switch" in name or "dell" in name or "monitor" in name or "controller" in name:
        return "Device"
    else:
        return "Entity"

def create_relationship(tx, subject, predicate, obj):

    predicate = predicate.replace(" ", "_")

    label_a = get_label(subject)
    label_b = get_label(obj)

    query = f"""
    MERGE (a:{label_a} {{name:$subject}})
    MERGE (b:{label_b} {{name:$object}})
    MERGE (a)-[:{predicate}]->(b)
    """

    tx.run(query, subject=subject, object=obj)

print(f"Successfully loaded {len(df)} triples. Starting injection...")

with driver.session(database="neo4j") as session:
    for index, row in df.iterrows():
        subject = str(row["Subject"]).strip()
        predicate = str(row["Predicate"]).strip()
        obj = str(row["Object"]).strip()

        # Skip empty values
        if subject == "" or predicate == "" or obj == "":
            continue

        session.execute_write(
            create_relationship,
            subject,
            predicate,
            obj
        )
        
        # Print progress every 50 rows so you know it's not frozen
        if index % 50 == 0 and index > 0:
            print(f"Inserted {index} relationships...")

driver.close()
print("Graph successfully stored in Neo4j! 🚀")