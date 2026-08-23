"""GraphRAG-Bench Novel retrieval_eval 首跑冒烟 — Research #065
已验证: 2026-08-15, 3 novels / 123,520 words → 2946 nodes / 153 edges (2.2s, rule 零API)
        10 questions → 官方 8-key schema (0.6s), non-empty context 10/10
"""
import json, os, sys, time, urllib.request

sys.path.insert(0, "/root/.openclaw/workspace/projects/agent-memory-graph")
from run_amg import load_bench_data, index_corpus, answer_question
from memory_graph import MemoryGraph

BASE = "https://raw.githubusercontent.com/GraphRAG-Bench/GraphRAG-Benchmark/main/Datasets"
DATA = "/tmp/grb_smoke"
os.makedirs(DATA, exist_ok=True)

# 1) 官方数据直连 GitHub raw（免 HF CLI）
for name in ["Corpus/novel.json", "Questions/novel_questions.json"]:
    dst = os.path.join(DATA, name.split("/")[-1])
    if not os.path.exists(dst):
        urllib.request.urlretrieve(f"{BASE}/{name}", dst)
        print("downloaded", dst)

# 2) 冒烟子集：3 部小说 + 其全部问题（首跑改为 sample=100 全量）
corpus_all = json.load(open(f"{DATA}/novel.json"))
questions_all = json.load(open(f"{DATA}/novel_questions.json"))
smoke = {c["corpus_name"] for c in corpus_all[:3]}
sub_corpus = [c for c in corpus_all if c["corpus_name"] in smoke]
sub_q = [q for q in questions_all if q["source"] in smoke]
json.dump(sub_corpus, open(f"{DATA}/corpus_sub.json", "w"))
json.dump(sub_q, open(f"{DATA}/questions_sub.json", "w"))

# 3) 索引 + 检索 → 官方 schema
corpus, questions = load_bench_data(DATA, corpus_file="corpus_sub.json",
                                    questions_file="questions_sub.json", sample=10)
t0 = time.time()
mg = MemoryGraph()
stats = index_corpus(mg, corpus, chunk_size=512)
print(f"index: {stats['chunks']} chunks, {stats['nodes_created']} nodes, "
      f"{stats['edges_created']} edges in {time.time()-t0:.1f}s")

t1 = time.time()
rows = [answer_question(mg, q) for q in questions]
print(f"answer 10 q in {time.time()-t1:.1f}s | non-empty ctx: "
      f"{sum(1 for r in rows if r['context'].strip())}/10")

json.dump(rows, open(f"{DATA}/amg_predictions.json", "w"), indent=2, ensure_ascii=False)
print("wrote", f"{DATA}/amg_predictions.json", "| keys:", sorted(rows[0].keys()))

# ── 首跑收尾（本机缺 ollama 时执行）────────────────────────────
# curl -fsSL https://ollama.com/install.sh | sh && ollama pull qwen2.5:7b
# git clone https://github.com/GraphRAG-Bench/GraphRAG-Benchmark /tmp/grb-eval
# cd /tmp/grb-eval && pip install -r requirements.txt
# python -m Evaluation.retrieval_eval --mode ollama --model qwen2.5:7b \
#   --base_url http://localhost:11434 --embedding_model bge-m3 \
#   --data_file /tmp/grb_smoke/amg_predictions.json \
#   --output_file /tmp/grb_smoke/retrieval_eval.json --detailed_output
