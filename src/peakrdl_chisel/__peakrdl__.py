from typing import TYPE_CHECKING

from peakrdl.plugins.exporter import ExporterSubcommandPlugin

from .exporter import ChiselExporter

if TYPE_CHECKING:
    import argparse
    from systemrdl.node import AddrmapNode


class Exporter(ExporterSubcommandPlugin):
    short_desc = "Generate a Chisel3 register block module"
    long_desc = """Generate a synthesizable Chisel3 Module from a SystemRDL
    register description.  The output includes IO bundles, address decode
    logic, a read mux, and register storage."""

    def add_exporter_arguments(self, arg_group: 'argparse._ActionsContainer') -> None:
        arg_group.add_argument(
            "--module-name",
            metavar="NAME",
            default=None,
            help="Override the Chisel module name [default: from addrmap name]"
        )

        arg_group.add_argument(
            "--package-name",
            metavar="PKG",
            default=None,
            help="Scala package name [default: from addrmap name]"
        )

    def do_export(self, top_node: 'AddrmapNode', options: 'argparse.Namespace') -> None:
        x = ChiselExporter()
        x.export(
            top_node,
            options.output,
            module_name=options.module_name,
            package_name=options.package_name,
        )
