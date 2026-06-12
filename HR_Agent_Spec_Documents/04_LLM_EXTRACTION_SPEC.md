# LLM Extraction Specification

## JD Output Schema
Return strict JSON.

Fields:
- title
- normalized_role
- experience_min
- experience_max
- must_have_skills
- good_to_have_skills
- department
- industry
- summary

## Candidate Output Schema
- candidate_name
- normalized_role
- years_experience
- skills
- education
- industries
- summary

Validation:
- No hallucinations
- Empty list when missing
