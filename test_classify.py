import asyncio
from hr_agent.core.config import get_settings
from hr_agent.core.deps import get_domain_classification_service

def test_classify():
    domain_svc = get_domain_classification_service()
    try:
        classification = domain_svc.classify_job(
            title="Software Engineer",
            normalized_role="Backend Developer",
            seniority_level="Senior",
            department="Engineering",
            industry="Technology",
            skills=["Python", "FastAPI", "SQLAlchemy"],
            tools=["Git", "Docker"],
            responsibilities=["Develop API", "Optimize DB"],
            education=["BS Computer Science"],
            summary="Senior backend developer needed."
        )
        print("Classification Success:", classification.model_dump())
    except Exception as e:
        print("Classification Error:", e)

test_classify()
