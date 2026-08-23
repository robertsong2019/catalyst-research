"""Minimal validation: amg -> GraphRAG-Bench adapter skeleton.

Simulates the GraphRAG-Bench Novel pipeline: ingest corpus docs ->
extract_from_text -> graphrag_query -> prediction JSON in official schema.
"""
import json
import sys

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
from memory_graph import MemoryGraph

# --- 1. GraphRAG-Bench corpus/questions schema (mini fixtures) ---
corpus = [
    {"corpus_name": "Novel-0001", "context": (
        "Cornwall is a region in the southwest of England. John Curgenven is a Cornish boatman. "
        "John Curgenven ferries visitors to Mont St. Michel. Mont St. Michel is located in Normandy. "
        "Erica vagans is a plant known as Cornish heath. King Arthur compared himself to John Curgenven."
    )},
]
questions = [
    {"id": "Novel-aaa1", "source": "Novel-0001",
     "question": "Which region of France is Mont St. Michel located?",
     "answer": "Normandy", "question_type": "Fact Retrieval",
     "evidence": "Mont St. Michel is located in Normandy.", "evidence_relations": ""},
    {"id": "Novel-aaa2", "source": "Novel-0001",
     "question": "What plant known as Erica vagans is also called Cornish heath?",
     "answer": "Erica vagans", "question_type": "Fact Retrieval",
     "evidence": "Erica vagans is a plant known as Cornish heath.", "evidence_relations": ""},
]

# --- 2. Index: rule-based KG construction (zero API cost) ---
mg = MemoryGraph()
index_stats = []
for doc in corpus:
    stats = mg.extract_from_text(doc["context"], tags=[doc["corpus_name"]])
    index_stats.append(stats)
print(f"[index] nodes={sum(s['nodes_created'] for s in index_stats)} "
      f"edges={sum(s['edges_created'] for s in index_stats)}")

# --- 3. Retrieval-only answer (no LLM: use top answer node as extractive answer) ---
results = []
for q in questions:
    r = mg.graphrag_query(q["question"], max_hops=2, top_k=5, include_context=True)
    top = r["answer_nodes"][0] if r.get("answer_nodes") else {"label": ""}
    context = r.get("context", "")
    results.append({
        "id": q["id"],
        "question": q["question"],
        "source": q["source"],
        "context": context,
        "evidence": q["evidence"],
        "question_type": q["question_type"],
        "generated_answer": top["label"],   # extractive baseline; LLM would go here
        "ground_truth": q.get("answer"),
    })

# --- 4. Emit official prediction schema ---
print(json.dumps(results, indent=2, ensure_ascii=False))
with open("/tmp/amg_predictions.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("[ok] saved /tmp/amg_predictions.json")

# --- 5. Optional diagnostic: graphrag_explain for failed retrieval ---
exp = mg.graphrag_explain(questions[0]["question"])
hit = questions[0]["answer"].lower() in results[0]["generated_answer"].lower()
print(f"[explain] query0 keyword coverage={exp['coverage']}% extractive_hit={hit}")
