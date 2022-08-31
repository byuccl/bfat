#!/usr/bin/env python3
#
# Copyright (C) 2022 Brigham Young University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

'''
    net_analysis.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Determines all sensitive bits related to the given nets.

    Arguments:
        - dcp checkpoint file for the design to analyze
        - '.txt' file containing the net names to analyzed, separated by line

    Returns:
        - output '.txt' file containing the analysis of the net(s)
'''

from distutils.command.config import config
import sys

# Add the parent directory of this file (bfat root) to the interpreter's path
sys.path.append(f'{"/".join(__file__.split("/")[:-1])}/..')

from bfat import get_tile_type_name
from lib.tile import Tile
from lib.file_processing import parse_tilegrid
from lib.design_query import DesignQuery
from lib.bit_definitions import bit_bitstream_addr

def parse_nets_file(nets_file:str):
    '''
        Parses a text file containing all of the nets to analyze
            Arguments: String of the path to the nets file
            Returns: List containing all of the nets
    '''

    nets = []

    # Open the file and add the net on each line to the list
    with open(nets_file) as nets_f:
        for line in nets_f:
            net = line.strip()

            # Make sure the net is in the correct format
            if ' ' in net or '\t' in net:
                raise Exception('File cannot include more than one net per line')

            nets.append(net)

    return nets

def analyze_nets(nets:list, design:DesignQuery, tilegrid:dict):
    '''
        Finds all pips and sensitive bits related to the given nets
            Arguments: list of net names, design query object, tilegrid information
            Returns: dict of each net containing all pips used in the following format:
                - ("pip name", "routing mux name/type", [configuration bits])
    '''

    net_sens_bits = {}

    # Iterate through all given nets
    for net in nets:
        net_sens_bits[net] = []

        # Query design for pips of the net and verify the net exists and uses pips
        net_pips = design.get_pips(net)
        if net not in design.pips or design.pips[net] == []:
            continue

        # Iterate through all pips of the net
        for pip in net_pips:
            # Ignore non-INT pips
            if any(['INT_L' not in wire and 'INT_R' not in wire for wire in pip]):
                continue
            
            # Retrieve the tile name and the sink/source nodes of the pip, construct tile object
            tile, sink = pip[1].split('/')
            src = pip[0].split('/')[1]
            tile_type = get_tile_type_name(tile)
            tile_obj = Tile(tile, tile_type, design.part)

            # Verify that the pip sink is a switchbox routing mux in the tile
            if sink not in tile_obj.pips or src not in tile_obj.pips[sink]:
                continue
            
            # Format relevant information to be added to the dictionary
            pip_formatted = f'{tile}/{tile_type}.{src}->>{sink}'
            mux_formatted = f'{sink} {tile_obj.resources[sink].mux_type} Routing Mux'

            # Get all configuration bits for the mux
            mux_config_bits = {'Row Bits' : tile_obj.resources[sink].row_bits,
                               'Column Bits' : tile_obj.resources[sink].col_bits}

            mux_conv_bits = {'Row Bits' : [], 'Column Bits' : []}
            # Convert each configuration bit to the full bittstream address format
            for bit_type, addresses in mux_config_bits.items():
                for addr in addresses:
                    tile_addr = [tile, addr, 0]
                    bitstream_addr = bit_bitstream_addr(tile_addr, tilegrid)
                    mux_conv_bits[bit_type].append(bitstream_addr)

            # Add information in a tuple to the dictionary
            net_sens_bits[net].append((pip_formatted, mux_formatted, mux_conv_bits))

    return net_sens_bits

def get_outfile_name(outname_arg:str, nets_path:str):
    '''
        Generates a name for the output fault report file based on the arguments passed
        in by the user and net list file used
            Arguments: Strings of the file paths to the output file and the net list file
            Returns: String of the appropriate output file name
    '''

    # Return the user provided name if one was provided
    if outname_arg:
        return outname_arg

    nets_path = nets_path.strip().split('/')
    outfile_name, _ = nets_path[-1].split('.')

    # Return the fault bit list file root name with default output file name formatting
    return f'{outfile_name}_analysis.txt'

def print_analysis(net_sens_bits:dict, outfile:str):
    '''
        Formats and prints the information about the nets' sensitive bits
            Arguments: net sensitive bit dictionary, string of output file path
            Returns: Output file (.txt) of the analysis
    '''
    
    # Open the output file to write to it
    with open(outfile, 'w') as o_f:
        # Iterate through the nets in the dictionary
        for net in net_sens_bits:
            o_f.write(f'{net}\n')
            o_f.write(f'Pips: ({len(net_sens_bits[net])})\n')

            all_net_config_bits = set()

            # Iterate through the tuples of pip/mux info for the net
            for pip_info in net_sens_bits[net]:
                pip, mux, config_bits = pip_info
                o_f.write(f'\t{pip} - {mux}:\n')

                # Iterate through all bits for the routing mux
                for bit_type, bits in config_bits.items():
                    o_f.write(f'\t\t{bit_type}: {bits}\n')
                    all_net_config_bits = all_net_config_bits.union(set(bits))
                
                o_f.write('\n')
            
            o_f.write(f'Total config bits: {len(all_net_config_bits)}\n')
            o_f.write('\n-----------------------------------\n\n')

def main(args):
    '''
        Main function: Writes a sensitivity report for all the nets given
        for a specific design with all related pips and routing bits
    '''

    # Create design query object
    if args.rapidwright:
        from lib.rpd_query import RpdQuery
        design = RpdQuery(args.dcp_file)
    else:
        from lib.design_query import VivadoQuery
        design = VivadoQuery(args.dcp_file)

    # Get part tilegrid information
    tilegrid = parse_tilegrid(design.part)

    # Parse in the nets to analyze
    nets = parse_nets_file(args.nets)

    # Retrieve all relevant pips, routing muxes, and configuration bits for each net
    net_sens_bits = analyze_nets(nets, design, tilegrid)

    # Get the output file name
    outfile = get_outfile_name(args.out_file, args.nets)

    # Print report of the found information
    print_analysis(net_sens_bits, outfile)

if __name__ == '__main__':
    import argparse
    # Create Argument Parser to take in command line arguments
    parser = argparse.ArgumentParser(description="Analyzes the given nets in a design and "
                                                + "reports all of the nets' sensitive bits")
    parser.add_argument('dcp_file', help='Vivado checkpoint file of the implemented design')
    parser.add_argument('nets', help='Text file containing the names of the net(s) to analyze')
    parser.add_argument('-rpd', '--rapidwright', action='store_true', help='Flag to use Rapidwright to read design data')
    parser.add_argument('-of', '--out_file', default='', help='File path where the output is to be written.')
    args = parser.parse_args()

    main(args)