"""Configuration loader for LocalPrometheOS."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import yaml


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234/v1"
    model: str = "qwen2.5"
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout: int = 60


@dataclass
class SchedulerConfig:
    timezone: str = "UTC"
    max_workers: int = 4


@dataclass
class StorageConfig:
    db_path: str = "data/prometheos.db"
    results_dir: str = "data/results"


@dataclass
class MCPServerConfig:
    name: str
    transport: str
    command: Optional[List[str]] = None
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30


@dataclass
class MCPConfig:
    servers: List[MCPServerConfig] = field(default_factory=list)


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "data/prometheos.log"


@dataclass
class MemoryConfig:
    chroma_enabled: bool = False
    persist_dir: str = "data/chroma"
    collection: str = "prometheos"


@dataclass
class AppConfig:
    lmstudio: LMStudioConfig = field(default_factory=LMStudioConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        lmstudio = LMStudioConfig(**(data.get("lmstudio") or {}))
        scheduler = SchedulerConfig(**(data.get("scheduler") or {}))
        storage = StorageConfig(**(data.get("storage") or {}))
        logging = LoggingConfig(**(data.get("logging") or {}))
        memory = MemoryConfig(**(data.get("memory") or {}))

        mcp_data = data.get("mcp") or {}
        servers_raw = mcp_data.get("servers") or []
        servers = [MCPServerConfig(**server) for server in servers_raw]
        mcp = MCPConfig(servers=servers)

        return cls(
            lmstudio=lmstudio,
            scheduler=scheduler,
            storage=storage,
            mcp=mcp,
            logging=logging,
            memory=memory,
        )


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "config.yaml"


def resolve_config_path(path: Optional[str] = None) -> Path:
    if path:
        return Path(path)
    env_path = os.getenv("PROMETHEOS_CONFIG")
    if env_path:
        return Path(env_path)
    return _default_config_path()


def load_config(path: Optional[str] = None) -> AppConfig:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    data = yaml.safe_load(config_path.read_text()) or {}
    config = AppConfig.from_dict(data)
    _normalize_mcp_commands(config, config_path)
    return config


def _normalize_mcp_commands(config: AppConfig, config_path: Path) -> None:
    if not config.mcp.servers:
        return
    base_dir = config_path.parent
    root_dir = base_dir.parent
    for server in config.mcp.servers:
        if not server.command:
            continue
        normalized: List[str] = []
        for idx, part in enumerate(server.command):
            if idx == 0:
                normalized.append(part)
                continue
            if os.path.isabs(part):
                normalized.append(part)
                continue
            candidate = base_dir / part
            if candidate.exists():
                normalized.append(str(candidate.resolve()))
                continue
            candidate = root_dir / part
            if candidate.exists():
                normalized.append(str(candidate.resolve()))
                continue
            normalized.append(part)
        server.command = normalized
