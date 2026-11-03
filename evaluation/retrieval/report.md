# Retrieval Evaluation

Thirty manually reviewed queries use relevant document IDs from `retrieval_queries.json`. Chunk rankings are deduplicated by document ID before all metrics are computed; Recall@K and MRR therefore use the same document ranking. Recall is macro-averaged per query as retrieved relevant documents divided by the query's relevant document count. MRR is macro-averaged reciprocal rank of the first relevant document. Because some queries have multiple relevant documents, MRR=1.0 can coexist with Recall@1 below 1.0 when each top-ranked document is relevant but not every relevant document is retrieved. Each configuration is run with both fixed and structure-aware chunking.

Transformer evaluations run only when local model directories are provided. No model downloads are performed.

| Config | Embedding | Chunking | Status | Recall@1 | Recall@3 | Recall@5 | MRR | Mean latency (ms) | Index time (s) | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| E1 | local-hash-v1 | structure | completed | 0.8 | 0.9666666666666667 | 1.0 | 1.0 | 0.6618600338697433 | 0.4562701997347176 |  |
| E2 | sentence-transformers/all-MiniLM-L6-v2 | structure | completed | 0.8 | 0.9833333333333333 | 0.9833333333333333 | 1.0 | 22.365980098644894 | 9.727535800077021 |  |
| E3 | BAAI/bge-small-en-v1.5 | structure | completed | 0.7833333333333333 | 0.9666666666666667 | 0.9666666666666667 | 0.9833333333333333 | 29.512936668470502 | 2.518734300043434 |  |
| E4 | sentence-transformers/all-MiniLM-L6-v2 | structure | completed | 0.8 | 1.0 | 1.0 | 1.0 | 21.581893305604655 | 1.499327199999243 |  |
| E5 | BAAI/bge-small-en-v1.5 | structure | completed | 0.7833333333333333 | 1.0 | 1.0 | 0.9833333333333333 | 29.570866640036304 | 2.539360099937767 |  |
| E1 | local-hash-v1 | fixed | completed | 0.7666666666666667 | 1.0 | 1.0 | 0.9833333333333333 | 0.45001002339025337 | 0.15553800016641617 |  |
| E2 | sentence-transformers/all-MiniLM-L6-v2 | fixed | completed | 0.7833333333333333 | 0.9833333333333333 | 1.0 | 0.9833333333333333 | 13.738839995736877 | 1.4043503999710083 |  |
| E3 | BAAI/bge-small-en-v1.5 | fixed | completed | 0.8 | 0.9666666666666667 | 0.9833333333333333 | 1.0 | 21.2578267014275 | 3.0553268999792635 |  |
| E4 | sentence-transformers/all-MiniLM-L6-v2 | fixed | completed | 0.8 | 1.0 | 1.0 | 1.0 | 17.468963330611587 | 1.4053003997541964 |  |
| E5 | BAAI/bge-small-en-v1.5 | fixed | completed | 0.8 | 0.9833333333333333 | 0.9833333333333333 | 1.0 | 21.337716669465106 | 3.030129900202155 |  |
