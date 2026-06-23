"""Domain-based model routing for Ollama expert delegation."""

import os
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class DomainConfig:
    """Configuration for a single domain expert."""
    domain: str
    model: str
    description: str
    temperature: float = 0.1
    top_p: float = 0.9
    num_predict: int = 4096


# Default domain descriptions
DOMAIN_DESCRIPTIONS = {
    "ospf": "OSPF protocol expert — area design, LSA types, SPF, FRR config generation (RFC 2328/5340)",
    "bgp": "BGP protocol expert — path selection, communities, policy, route reflection, extra_attributes placement (RFC 4271)",
    "mpls": "MPLS/SR expert — label distribution, traffic engineering, segment routing",
    "acl": "Access control list expert — filtering, CoPP, security policy generation",
    "rfc": "RFC design validator — validates network designs against IETF standards",
    "frr": "FRR config generation expert — generates complete vtysh commands from Nautobot GraphQL data for the NetClaw demo",
    "nautobot": "Nautobot API/GraphQL expert — BGP Models plugin hierarchy, OSPF IGP models, job execution patterns",
    "general": "General network config generation — multi-protocol, multi-platform",
    "graphql": "Nautobot GraphQL query builder — constructs valid queries from natural language intent",
    "state": "Protocol state summarizer — compresses show command output into pass/fail JSON signals",
    "compress": "Context compressor — reduces raw GraphQL responses to minimal config-relevant JSON",
}


@dataclass
class DomainRouter:
    """Routes domain requests to appropriate Ollama models based on env config."""

    _registry: Dict[str, DomainConfig] = field(default_factory=dict)
    _fallback_model: str = "deepseek-coder-v2:16b"

    def __post_init__(self):
        self._load_from_env()

    def _load_from_env(self):
        """Load domain → model mappings from environment variables.

        Expected env vars:
            OLLAMA_MODEL_OSPF=netclaw-ospf:latest
            OLLAMA_MODEL_BGP=netclaw-bgp:latest
            OLLAMA_MODEL_RFC=netclaw-rfc-design:latest
            OLLAMA_MODEL_MPLS=netclaw-mpls:latest
            OLLAMA_MODEL_ACL=netclaw-acl:latest
            OLLAMA_MODEL_GENERAL=deepseek-coder-v2:16b
            OLLAMA_MODEL_FALLBACK=deepseek-coder-v2:16b

            # Optional per-domain temperature overrides
            OLLAMA_TEMP_OSPF=0.1
            OLLAMA_TEMP_BGP=0.1
            OLLAMA_TEMP_RFC=0.2
        """
        self._fallback_model = os.environ.get("OLLAMA_MODEL_FALLBACK", "deepseek-coder-v2:16b")

        for domain in ["ospf", "bgp", "mpls", "acl", "rfc", "frr", "nautobot", "general", "graphql", "state", "compress"]:
            env_key = f"OLLAMA_MODEL_{domain.upper()}"
            model = os.environ.get(env_key)

            if model:
                temp_key = f"OLLAMA_TEMP_{domain.upper()}"
                temperature = float(os.environ.get(temp_key, "0.1"))

                self._registry[domain] = DomainConfig(
                    domain=domain,
                    model=model,
                    description=DOMAIN_DESCRIPTIONS.get(domain, f"{domain} domain expert"),
                    temperature=temperature,
                )

    def get_model(self, domain: str) -> str:
        """Get the Ollama model name for a given domain.

        Falls back to the general model, then to the fallback model.
        """
        if domain in self._registry:
            return self._registry[domain].model

        # Try "general" domain as intermediate fallback
        if "general" in self._registry:
            return self._registry["general"].model

        return self._fallback_model

    def get_config(self, domain: str) -> DomainConfig:
        """Get full domain configuration including generation parameters."""
        if domain in self._registry:
            return self._registry[domain]

        # Return fallback config
        return DomainConfig(
            domain=domain,
            model=self.get_model(domain),
            description=f"Fallback model handling {domain} domain",
            temperature=0.1,
        )

    def get_generation_options(self, domain: str) -> Dict[str, float]:
        """Get Ollama generation options for a domain."""
        config = self.get_config(domain)
        return {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "num_predict": config.num_predict,
        }

    def list_configured_domains(self) -> Dict[str, DomainConfig]:
        """List all configured domain experts."""
        return dict(self._registry)

    @property
    def fallback_model(self) -> str:
        return self._fallback_model

    def is_domain_configured(self, domain: str) -> bool:
        """Check if a specific domain has an explicit model configured."""
        return domain in self._registry
