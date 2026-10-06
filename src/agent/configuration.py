import os
from pathlib import Path

from azure.ai.agentserver.optimization import OptimizationConfig, load_config
from azure.core.credentials import TokenCredential

CONFIG_DIR = Path(__file__).parent / ".agent_configs"


def read_config(*, credential: TokenCredential | None = None) -> OptimizationConfig:
    directory = Path(os.environ.get("OPTIMIZATION_LOCAL_DIR", CONFIG_DIR)).resolve()
    candidate = os.environ.get("OPTIMIZATION_CANDIDATE_ID", "").strip()
    inline = os.environ.get("OPTIMIZATION_CONFIG", "").strip()
    remote = os.environ.get("OPTIMIZATION_RESOLVE_ENDPOINT", "").strip()
    if candidate and not inline and not remote:
        if not (directory / candidate / "metadata.yaml").is_file():
            raise ValueError(f"Requested candidate {candidate!r} is not present in {directory}")
    config = load_config(config_dir=directory, credential=credential)
    if config is None or not config.instructions or not config.model:
        raise ValueError("Agent configuration must contain nonempty instructions and a model")
    if candidate and remote and not inline and config.source != f"api:candidate:{candidate}":
        raise ValueError(f"Could not resolve candidate {candidate!r}; refusing baseline fallback")
    if config.skills:
        raise ValueError(
            "This minimal agent supports instruction/tool/model optimisation, not skills"
        )
    return config
