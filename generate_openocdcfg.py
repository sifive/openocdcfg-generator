#!/usr/bin/env python3
# Copyright (c) 2020 SiFive Inc.
# SPDX-License-Identifier: Apache-2.0

"""Generate OpenOCD configuration files from devicetree source files"""

import argparse
import sys

import jinja2
import pydevicetree

TEMPLATES_PATH = "templates"

SUPPORTED_BOARDS = ["arty", "vc707", "hifive"]
SUPPORTED_PROTOCOLS = ["jtag", "cjtag"]


def missingvalue(message):
    """
    Raise an UndefinedError
    This function is made available to the template so that it can report
    when required values are not present and cause template rendering to
    fail.
    """
    raise jinja2.UndefinedError(message)


def format_hex(num):
    """Format an integer as a hex number"""
    return "0x%x" % num


def parse_arguments(argv):
    """Parse the arguments into a dictionary with argparse"""
    arg_parser = argparse.ArgumentParser(
        description="Generate OpenOCD configuration files from Devicetrees")

    arg_parser.add_argument("-d", "--dts", required=True,
                            help="The path to the Devicetree for the target")
    arg_parser.add_argument("-b", "--board", required=True,
                            help="The board of the target to generate an OpenOCD config for. \
                                Supported boards include: %s" % ", ".join(SUPPORTED_BOARDS))
    arg_parser.add_argument("-o", "--output",
                            type=argparse.FileType('w'),
                            help="The path of the linker script file to output")
    arg_parser.add_argument("-p", "--protocol",
                            help="Supported protocols include: %s" % ", ".join(SUPPORTED_PROTOCOLS))
    arg_parser.add_argument("-t", "--tunnel", action="store_true",
                            help="Enable JTAG tunneling (Xilinx BSCAN)")

    return arg_parser.parse_args(argv)


def get_template(parsed_args):
    """Initialize jinja2 and return the right template"""
    env = jinja2.Environment(
        loader=jinja2.PackageLoader(__name__, TEMPLATES_PATH),
        trim_blocks=True, lstrip_blocks=True,
    )
    # Make the missingvalue() function available in the template so that the
    # template fails to render if we don't provide the values it needs.
    env.globals["missingvalue"] = missingvalue
    env.filters["format_hex"] = format_hex

    if "arty" in parsed_args.board or "vc707" in parsed_args.board:
        template = env.get_template("fpga.cfg")
    elif "hifive" in parsed_args.board:
        template = env.get_template("hifive.cfg")
    else:
        print("Board %s is not supported!" %
              parsed_args.board, file=sys.stderr)
        sys.exit(1)

    return template


def get_ram(tree):
    """Get the base and size of the RAM to use as the OpenOCD work area"""
    metal_ram = tree.chosen("metal,ram")
    if metal_ram:
        node = tree.get_by_reference(metal_ram[0])
        region = metal_ram[1]
        offset = metal_ram[2]
        if node:
            reg = node.get_reg()
            base = reg[region][0] + offset
            size = reg[region][1] - offset
            return {"base": base, "size": size}
        return None
    return None


def get_flash(tree):
    """Get the memory and control base addresses of the SPI flash to program"""
    metal_entry = tree.chosen("metal,entry")
    if metal_entry:
        node = tree.get_by_reference(metal_entry[0])
        if node and "sifive,spi" in node.get_field("compatible"):
            reg = node.get_reg()
            mem_base = reg.get_by_name("mem")[0]
            control_base = reg.get_by_name("control")[0]
            return {"mem_base": mem_base, "control_base": control_base}
        return None
    return None


def main(argv):
    """Parse arguments, extract data, and render the OpenOCD configuration to file"""
    parsed_args = parse_arguments(argv)

    template = get_template(parsed_args)

    dts = pydevicetree.Devicetree.parseFile(
        parsed_args.dts, followIncludes=True)

    if parsed_args.protocol:
        if parsed_args.protocol not in SUPPORTED_PROTOCOLS:
            print("Protocol %s in not supported" % protocol, file=sys.stderr)
            sys.exit(1)
        protocol = parsed_args.protocol
    else:
        protocol = "jtag"

    if parsed_args.tunnel:
        connection = "tunnel"
    else:
        connection = "probe"

    values = {
        "ram": get_ram(dts),
        "flash": get_flash(dts),
        "connection": connection,
        "protocol": protocol,
    }

    if parsed_args.output:
        parsed_args.output.write(template.render(values))
        parsed_args.output.close()
    else:
        print(template.render(values))


if __name__ == "__main__":
    main(sys.argv[1:])
