# Matching Engine

Stage 1:
Hard filters
- Experience
- Location
- Mandatory skills

Stage 2:
Rule score

Example:
Skill Match 40%
Experience 20%
Role Match 20%
Industry Match 20%

Stage 3:
Vector similarity

Stage 4:
LLM reranking

Final Score:
0.4 * Rule
+0.2 * Vector
+0.4 * LLM
