# Data Model

## Job
- job_id
- title
- normalized_role
- experience_min
- experience_max
- must_have_skills
- good_to_have_skills
- department
- industry
- embedding

## Candidate
- candidate_id
- name
- normalized_role
- years_experience
- skills
- education
- industries
- embedding

## Match Result
- job_id
- candidate_id
- final_score
- rule_score
- vector_score
- llm_score
