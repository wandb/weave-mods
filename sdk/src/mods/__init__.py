import sys
from importlib import import_module
from types import ModuleType

from mods import api


class ModuleWithProperty(ModuleType):
    @property
    def st(self):
        mst = import_module("mods.streamlit")
        return mst

    def __getattr__(self, name):
        if name == "streamlit" or name == "st":
            mst = import_module("mods.streamlit")
            return mst
        return super().__getattribute__(name)


sys.modules[__name__].__class__ = ModuleWithProperty

__all__ = ["streamlit", "api"]
