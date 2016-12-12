from volatility.framework.configuration import requirements
from volatility.framework.symbols import intermed
from volatility.framework.symbols.windows import extensions

__author__ = 'mike'


class WindowsKernelIntermedSymbols(intermed.IntermediateSymbolTable):
    provides = {"type": "interface"}

    def __init__(self, context, config_path, name, idd_filepath):
        super().__init__(name = name, idd_filepath = idd_filepath)

        # Set-up windows specific types
        self.set_type_class('_ETHREAD', extensions._ETHREAD)
        self.set_type_class('_LIST_ENTRY', extensions._LIST_ENTRY)

    @classmethod
    def get_requirements(cls):
        return [requirements.StringRequirement("idd_filepath", description = "JSON file containnig the symbols")]
