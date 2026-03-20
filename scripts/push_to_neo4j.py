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

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def create_relationship(tx, subject, predicate, obj):

    predicate = predicate.replace(" ", "_")

    query = f"""
    MERGE (a:Entity {{name:$subject}})
    MERGE (b:Entity {{name:$object}})
    MERGE (a)-[:{predicate}]->(b)
    """

    tx.run(query, subject=subject, object=obj)

print(f"Successfully loaded {len(df)} triples. Starting injection...")

with driver.session() as session:
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