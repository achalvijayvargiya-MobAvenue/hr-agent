# System Architecture

JD PDF -> Text Extraction -> LLM Structuring -> DB + Embeddings

CV PDF -> Text Extraction -> LLM Structuring -> DB + Embeddings

Matching Flow:
1. Hard Filters
2. Rule Based Scoring
3. Vector Retrieval
4. LLM Re-ranking
5. Final Ranking

Core Services:
- Ingestion Service
- Extraction Service
- Embedding Service
- Matching Service
- Ranking Service
- API Service
