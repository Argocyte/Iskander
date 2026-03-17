"""
Boundary Agent / Embassy --- Federation hardening module (Fix 7).

Single point of contact for all foreign SDC data entering Iskander.
Implements: trust quarantine, ontology translation, governance verification,
causal ordering, and Glass Box wrapping at federation boundaries.
"""
from backend.boundary.boundary_agent import BoundaryAgent, BoundaryVerdict
from backend.boundary.trust_quarantine import TrustQuarantine, ForeignIdentityProfile
from backend.boundary.ontology_translator import OntologyTranslator, TranslationResult
from backend.boundary.governance_verifier import GovernanceVerifier, GovernanceCapabilities
from backend.boundary.causal_buffer import CausalBuffer

__all__ = [
    "BoundaryAgent", "BoundaryVerdict",
    "TrustQuarantine", "ForeignIdentityProfile",
    "OntologyTranslator", "TranslationResult",
    "GovernanceVerifier", "GovernanceCapabilities",
    "CausalBuffer",
]
