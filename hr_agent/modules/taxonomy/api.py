"""Taxonomy API — list domains and subdomains for UI pickers."""
from fastapi import APIRouter, Depends

from hr_agent.core.deps import get_current_user
from hr_agent.modules.taxonomy.schemas import TaxonomyDomainResponse, TaxonomyResponse, TaxonomySubdomainResponse
import hr_agent.modules.taxonomy.taxonomy_service as taxonomy_service

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=TaxonomyResponse)
def get_taxonomy() -> TaxonomyResponse:
    """Return the full domain/subdomain taxonomy for Mobavenue."""
    domains = [
        TaxonomyDomainResponse(
            code=d["code"],
            label=d["label"],
            description=d.get("description", ""),
            subdomains=[
                TaxonomySubdomainResponse(
                    code=s["code"],
                    label=s["label"],
                    adjacent=s.get("adjacent", []),
                )
                for s in d.get("subdomains", [])
            ],
        )
        for d in taxonomy_service.list_domains()
    ]
    return TaxonomyResponse(version=taxonomy_service.taxonomy_version(), domains=domains)
