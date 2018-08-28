import logging
import typing

from volatility.framework import interfaces, layers, renderers
from volatility.framework.configuration import requirements
from volatility.framework.renderers import format_hints
from volatility.framework.symbols.windows import extensions
from volatility.plugins import yarascan
from volatility.plugins.windows import pslist

vollog = logging.getLogger(__name__)

try:
    import yara
except ImportError:
    vollog.info("Python Yara module not found, plugin (and dependent plugins) not available")


class VadYaraScan(interfaces.plugins.PluginInterface):

    @classmethod
    def get_requirements(cls):
        return [requirements.TranslationLayerRequirement(name = 'primary',
                                                         description = "Primary kernel address space",
                                                         architectures = ["Intel32", "Intel64"]),
                requirements.SymbolRequirement(name = "nt_symbols", description = "Windows OS"),
                requirements.BooleanRequirement(name = "all",
                                                description = "Scan both process and kernel memory",
                                                default = False,
                                                optional = True),
                requirements.BooleanRequirement(name = "insensitive",
                                                description = "Makes the search case insensitive",
                                                default = False,
                                                optional = True),
                requirements.BooleanRequirement(name = "kernel",
                                                description = "Scan kernel modules",
                                                default = False,
                                                optional = True),
                requirements.BooleanRequirement(name = "wide",
                                                description = "Match wide (unicode) strings",
                                                default = False,
                                                optional = True),
                requirements.StringRequirement(name = "yara_rules",
                                               description = "Yara rules (as a string)",
                                               optional = True),
                requirements.URIRequirement(name = "yara_file",
                                            description = "Yara rules (as a file)",
                                            optional = True),
                requirements.IntRequirement(name = "max_size",
                                            default = 0x40000000,
                                            description = "Set the maximum size (default is 1GB)",
                                            optional = True)
                ]

    def _generator(self):

        layer = self.context.memory[self.config['primary']]
        rules = None
        if self.config.get('yara_rules', None) is not None:
            rule = self.config['yara_rules']
            if rule[0] not in ["{", "/"]:
                rule = '"{}"'.format(rule)
            if self.config.get('case', False):
                rule += " nocase"
            if self.config.get('wide', False):
                rule += " wide ascii"
            rules = yara.compile(sources = {'n': 'rule r1 {{strings: $a = {} condition: $a}}'.format(rule)})
        elif self.config.get('yara_file', None) is not None:
            rules = yara.compile(file = layers.ResourceAccessor().open(self.config['yara_file'], "rb"))
        else:
            vollog.error("No yara rules, nor yara rules file were specified")

        filter = pslist.PsList.create_filter([self.config.get('pid', None)])

        for task in pslist.PsList.list_processes(self.context,
                                                 self.config['primary'],
                                                 self.config['nt_symbols'],
                                                 filter = filter):
            for offset, name in layer.scan(context = self.context,
                                           scanner = yarascan.YaraScanner(rules = rules),
                                           max_address = self.config['max_size'],
                                           scan_iterator = self.vad_iterator_factory(task)):
                yield format_hints.Hex(offset), name

    def vad_iterator_factory(self,
                             task: typing.Any) -> typing.Callable[[interfaces.layers.ScannerInterface,
                                                                   int,
                                                                   int],
                                                                  typing.Iterable[interfaces.layers.IteratorValue]]:

        task = self._check_type(task, extensions._EPROCESS)
        layer_name = task.add_process_layer()

        def scan_iterator(scanner: interfaces.layers.ScannerInterface,
                          min_address: int,
                          max_address: int) \
                -> typing.Iterable[interfaces.layers.IteratorValue]:
            vad_root = task.get_vad_root()
            for vad in vad_root.traverse():
                end = vad.get_end()
                start = vad.get_start()
                while end - start > scanner.chunk_size + scanner.overlap:
                    yield [(layer_name, start, scanner.chunk_size + scanner.overlap)], \
                          start + scanner.chunk_size + scanner.overlap
                    start += scanner.chunk_size
                yield [(layer_name, start, end - start)], end

        return scan_iterator

    def run(self):
        return renderers.TreeGrid([('Offset', format_hints.Hex),
                                   ('Rule', str)], self._generator())
