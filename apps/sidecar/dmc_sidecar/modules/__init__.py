from .base import AutomationModule
from .current_students import CurrentStudentsModule
from .graduation import GraduationModule


def get_module(module_name: str) -> AutomationModule:
    if module_name == "graduation":
        return GraduationModule()
    if module_name == "currentStudents":
        return CurrentStudentsModule()
    raise ValueError(f"unsupported module: {module_name}")
