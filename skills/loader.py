"""
J — Skill Loader
Auto-discovers all skill modules and builds a unified tool registry.
"""

import importlib
import inspect
import logging
from pathlib import Path

logger = logging.getLogger("j.skills.loader")

# Global skills registry: function_name -> callable
SKILLS_REGISTRY: dict[str, callable] = {}


def _skill_marker(func):
    """Decorator to mark a function as a J skill."""
    func._is_j_skill = True
    return func


# Make the decorator importable
skill = _skill_marker


def discover_skills() -> dict[str, callable]:
    """
    Scan all .py files in the skills/ directory.
    Any function decorated with @skill gets registered.
    """
    skills_dir = Path(__file__).parent
    registry = {}

    for py_file in sorted(skills_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "loader.py":
            continue

        module_name = f"skills.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.error("Failed to import skill module %s: %s", module_name, e)
            continue

        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if getattr(obj, "_is_j_skill", False):
                registry[name] = obj
                logger.debug("Registered skill: %s (from %s)", name, py_file.name)

    SKILLS_REGISTRY.update(registry)
    logger.info("Discovered %d skills from %s", len(registry), skills_dir)
    return registry


def get_registry() -> dict[str, callable]:
    """Return the current skills registry, discovering if empty."""
    if not SKILLS_REGISTRY:
        discover_skills()
    return SKILLS_REGISTRY
