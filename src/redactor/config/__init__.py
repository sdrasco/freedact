"""Configuration loading utilities.

Precedence of configuration sources:
    1. Package defaults (``defaults.yml``)
    2. Optional user-provided YAML passed to :func:`load_config`
    3. Environment variable secret referenced by ``pseudonyms.seed.secret_env``
"""

from .schema import ConfigModel, load_config

__all__ = ["ConfigModel", "load_config"]
