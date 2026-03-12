import os
import shutil
import sys


def _project_root():
    return os.path.dirname(os.path.dirname(__file__))


def _resource_root():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", _project_root())
    return _project_root()


def _runtime_root():
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "KinoAnalytica")
    return _project_root()


def resource_path(relative_path):
    return os.path.join(_resource_root(), relative_path)


def runtime_path(relative_path):
    target = os.path.join(_runtime_root(), relative_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    return target


def ensure_runtime_file(relative_path, seed_from_resource=True):
    target = runtime_path(relative_path)
    if os.path.exists(target):
        return target

    if seed_from_resource:
        source = resource_path(relative_path)
        if os.path.exists(source):
            shutil.copy2(source, target)
            return target

    return target

