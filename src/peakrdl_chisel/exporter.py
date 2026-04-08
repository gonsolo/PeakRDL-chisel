"""ChiselExporter — walk an elaborated SystemRDL tree and emit Chisel3 source.

The exporter collects register metadata (name, offset, width, fields, array
dimensions) into plain dicts, then passes them to a Jinja2 template that emits
a synthesizable Chisel3 Module.
"""

import os
from typing import Union, Optional, List, Dict, Any

import jinja2 as jj
from systemrdl.node import (
    RootNode, AddrmapNode, RegNode, FieldNode,
)


class ChiselExporter:
    """Compile a SystemRDL addrmap into a Chisel3 register block."""

    def __init__(self) -> None:
        loader = jj.FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates"))
        self.jj_env = jj.Environment(
            loader=loader,
            undefined=jj.StrictUndefined,
            keep_trailing_newline=True,
        )
        # Custom filter: CamelCase conversion
        self.jj_env.filters['camel'] = _to_camel_case

    def export(
        self,
        node: Union[RootNode, AddrmapNode],
        output_dir: str,
        *,
        module_name: Optional[str] = None,
        package_name: Optional[str] = None,
    ) -> None:
        """Generate Chisel3 source files from *node* into *output_dir*."""

        if isinstance(node, RootNode):
            top_node = node.top
        else:
            top_node = node

        # Derive names
        raw_name = top_node.inst_name                       # e.g. "borg_gpu"
        mod_name = module_name or _to_camel_case(raw_name)  # e.g. "BorgGpu"
        pkg_name = package_name or raw_name.replace("-", "_")

        # Collect register info
        regs = _collect_registers(top_node)

        # Compute address width from the addrmap size
        addr_width = (top_node.size - 1).bit_length()

        # Build template context
        context: Dict[str, Any] = {
            "module_name": mod_name,
            "package_name": pkg_name,
            "addr_width": addr_width,
            "data_width": 32,
            "registers": regs,
        }

        os.makedirs(output_dir, exist_ok=True)

        # Render module
        template = self.jj_env.get_template("module.scala.j2")
        output_path = os.path.join(output_dir, f"{mod_name}Regs.scala")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(template.render(context))

        print(f"Generated Chisel register block: {output_path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_camel_case(name: str) -> str:
    """Convert snake_case to CamelCase."""
    return "".join(w.capitalize() for w in name.split("_"))


def _collect_registers(addrmap: AddrmapNode) -> List[Dict[str, Any]]:
    """Walk the addrmap and gather register metadata."""
    regs: List[Dict[str, Any]] = []

    for child in addrmap.children():
        if not isinstance(child, RegNode):
            continue

        fields = _collect_fields(child)

        entry: Dict[str, Any] = {
            "name": child.inst_name,
            "offset": child.address_offset if not child.is_array else child.raw_address_offset,
            "width": child.size * 8,  # size is in bytes
            "fields": fields,
            "is_array": child.is_array,
            "array_dim": child.array_dimensions[0] if child.is_array else 1,
            "array_stride": child.array_stride if child.is_array else child.size,
            # Derived access summary
            "is_sw_readable": any(f["sw_read"] for f in fields),
            "is_sw_writable": any(f["sw_write"] for f in fields),
            "is_hw_readable": any(f["hw_read"] for f in fields),
            "is_hw_writable": any(f["hw_write"] for f in fields),
        }
        regs.append(entry)

    return regs


def _collect_fields(reg: RegNode) -> List[Dict[str, Any]]:
    """Gather field metadata from a single register."""
    fields: List[Dict[str, Any]] = []

    for field in reg.fields():
        sw = field.get_property("sw")
        hw = field.get_property("hw")

        entry: Dict[str, Any] = {
            "name": field.inst_name,
            "high": field.high,
            "low": field.low,
            "width": field.width,
            "reset": field.get_property("reset") or 0,
            "sw_read": str(sw) in ("AccessType.rw", "AccessType.r"),
            "sw_write": str(sw) in ("AccessType.rw", "AccessType.w"),
            "hw_read": str(hw) in ("AccessType.rw", "AccessType.r"),
            "hw_write": str(hw) in ("AccessType.rw", "AccessType.w"),
            "is_singlepulse": field.get_property("singlepulse"),
            "is_reserved": field.inst_name.startswith("RSVD"),
        }
        fields.append(entry)

    return fields
