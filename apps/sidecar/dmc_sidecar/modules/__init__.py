from .base import AutomationModule
from .graduation import GraduationModule


def get_module(module_name: str) -> AutomationModule:
    if module_name == "graduation":
        return GraduationModule()
    raise ValueError(f"unsupported module: {module_name}")
