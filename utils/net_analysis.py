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

    Optional flags:
        - all_nets [-a]: Flag to use all flags in the design instead of reading nets from a file
        - rapidwright [-rpd]: Flag to use Rapidwright implementation of design querying
        - graph [-g]: Flag to plot a histogram of the frequency of related bits to each net
        - pickle [-p]: Flag to pickle the output structure and save the serialized data to a file
        - pickled_input [-pi]: Flag to use a previously generated .pickle file in place of a nets file
        - non_tmr [-ntmr]: Filter out triplicated nets with the given TMR prefix
        - out_file [-of]: Path of output file. Default is <design_name>_fault_report.txt

    Returns:
        - output '.txt' file containing the analysis of the net(s)
'''

import sys

# Add the parent directory of this file (bfat root) to the interpreter's path
sys.path.append(f'{"/".join(__file__.split("/")[:-1])}/..')

from bfat import get_tile_type_name
from lib.tile import Tile
from lib.file_processing import parse_tilegrid
from lib.design_query import DesignQuery
from lib.define_bit import bit_bitstream_addr
from tqdm import tqdm
from statistics import mean, stdev, median, quantiles
import pickle

############################################
#           Data Storage Classes           #
############################################

class AnalyzedNet:
    '''
        Stores relevant information about the net and its sensitive bits
            Arguments: string of the net's name, design query object

            Attributes:
                name - the net's name

                pips - information about all used interconnect pips by the net
                    - each pip is stored as a PipInfo object

                num_bits - total number of configuration bits affecting the net's routing
    '''

    __slots__ = ('name', 'pips', 'num_bits')

    def __init__(self, net_name:str, design:DesignQuery, tilegrid:dict):
        '''
            Constructor, finds all pips and sensitive bits related to the net and
            populates class members with the retrieved information
                Arguments: net_name, design query object, tilegrid information
        '''

        # Set some default values
        self.name = net_name
        self.pips = []
        self.num_bits = 0

        # Query design for pips of the net and verify the net exists and uses pips
        net_pips = design.get_pips(self.name)
        if self.name not in design.pips or design.pips[self.name] == []:
            return

        # Gather bit configuration information about each pip's routing mux
        for pip in net_pips:
            # Ignore non-INT pips
            if any(['INT_L' not in wire and 'INT_R' not in wire for wire in pip]):
                continue
            
            # Create PipInfo objects for storing configuration bit information
            pip_info = PipInfo(pip, design, tilegrid)

            # Verify that the object was created correctly
            if hasattr(pip_info, 'pip_name'):
                self.pips.append(pip_info)
                self.num_bits += len(pip_info.row_bits) + len(pip_info.col_bits)

class PipInfo:
    '''
        Stores relevant information about a pip
            Arguments: part tilegrid information
        
            Attributes:
                pip_name - name of the pip, formatted to match Vivado

                mux_name - name of the routing mux

                mux_type - type of the routing mux (2-12, 2-18, 2-20, 5-16, 5-24)

                row_bits - list of the row bits for the routing mux

                col_bits - list of the column bits for the routing mux
    '''

    __slots__ = ('pip_name', 'mux_name', 'mux_type', 'row_bits', 'col_bits')

    def __init__(self, pip:tuple, design:DesignQuery, tilegrid:dict):
        '''
            Constructor, gathers all configuration bit information about the pip and its
            routing mux and stores it in member variables
        '''

        # Retrieve the tile name and the sink/source nodes of the pip, construct tile object
        tile, sink = pip[1].split('/')
        src = pip[0].split('/')[1]
        tile_type = get_tile_type_name(tile)
        tile_obj = Tile(tile, tile_type, design.part)

        # Verify that the pip sink is a switchbox routing mux in the tile
        if sink not in tile_obj.pips or src not in tile_obj.pips[sink]:
            return
        
        # Format relevant information and add to the member variables
        self.pip_name = f'{tile}/{tile_type}.{src}->>{sink}'
        self.mux_name = sink
        self.mux_type = tile_obj.resources[sink].mux_type

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

        # Populate object members with bit information
        self.row_bits = mux_conv_bits['Row Bits']
        self.col_bits = mux_conv_bits['Column Bits']

############################################
# Functions for dealing with .pickle files #
############################################

def unserialize_structure(pickled_file:str):
    '''
        Unserializes a file containing the data from a previous run of this tool
            Arguments: string of the path to the pickled file
            Returns: list of analyzed nets
    '''

    # Open the file and unserialize the data
    with open(pickled_file, 'rb') as p_f:
        analyzed_nets = pickle.load(p_f)

    does_not_match = False
    # Check that the resulting data structure matches the expected format
    if not isinstance(analyzed_nets, list):
        does_not_match = True
    elif len(analyzed_nets) > 0 and not isinstance(analyzed_nets[0], AnalyzedNet):
        does_not_match = True

    # Throw exception if the data structure does not match
    if does_not_match:
        raise Exception('Input serialized data structure does not match expected format')

    return analyzed_nets

def serialize_structure(analyzed_nets:list, report_name:str):
    '''
        Serializes the final data structure and exports it to a file with
        a generated name
            Arguments: list of analyzed nets, string of report's filename
            Returns: Output .pickle file of the analysis
    '''

    # Change file extension to .pickle
    if len(report_name.split('.')) > 1:
        report_name = '.'.join(report_name.split('.')[:-1])
    outfile_name = report_name + '.pickle'

    # Open the file to write the data to
    with open(outfile_name, 'wb') as o_f:
        pickle.dump(analyzed_nets, o_f)

############################################
#          Feature Flag Functions          #
############################################

def graph_output(nets:list):
    '''
        Plots a histogram showing the frequency at which different nets exhibit
        higher/lower numbers of used routing bits:
            Arguments: list of analyzed nets, string of the report's filename
            Returns: GUI of the plot
    '''

    import matplotlib.pyplot as plt

    N_BINS = 50

    # Extract the number of related bits from each net's object
    bit_freqs = [net.num_bits for net in nets]

    # Create the plot
    plt.hist(bit_freqs, density=False, bins=N_BINS)
    plt.title('Net Routing Sensitivity Analysis')
    plt.xlabel('Related bits per net')
    plt.ylabel('Frequency')
    plt.yscale('log')
    plt.show()

def remove_tmr_nets(nets:list, tmr_suffix:str):
    '''
        Filters out from a list of nets all triplicated nets
            Arguments: list of either AnalyzedNet objects or strings of net names
            Returns: list of non-triplicated AnalyzedNet objects or net names
    '''

    non_tmr_nets = []

    # Set of already checked net names (for efficiency)
    checked_nets = set()

    # Verify that the list of nets is either of AnalyzedNets or strings
    if all([isinstance(net_obj, AnalyzedNet) for net_obj in nets]):
        net_names = [net.name for net in nets]
    elif all([isinstance(net_obj, str) for net_obj in nets]):
        net_names = nets

    # Iterate through all nets in the list
    for net_obj in tqdm(nets):
        # If the given data structure is an AnalyzedNet object, use the name member
        if isinstance(net_obj, AnalyzedNet):
            net_name = net_obj.name
        elif isinstance(net_obj, str):
            net_name = net_obj

        # Skip net if it has already been checked
        if net_name in checked_nets:
            continue
        checked_nets.add(net_name)

        # Check if the TMR suffix is in the net name 
        if tmr_suffix not in net_name:
            non_tmr_nets.append(net_obj)
            continue

        # Find the index of the TMR copy number in the string
        tmr_num_index = net_name.find(tmr_suffix) + 1 + len(tmr_suffix) # +1 is to account for '_'
        tmr_num = net_name[tmr_num_index]

        # Create list of TMR numbers to check
        tmr_nums_to_check = ['0', '1', '2']
        tmr_nums_to_check.remove(tmr_num)

        num_copies = 0
        # Check that two other copies of this net exist in the list of nets
        for curr_tmr_num in tmr_nums_to_check:
            # Create a copy of the net name with the changed TMR number
            net_copy = list(net_name)
            net_copy[int(tmr_num_index)] = curr_tmr_num
            net_copy = ''.join(net_copy)

            # Set flag if the copy exists
            if net_copy in net_names:
                num_copies += 1
            checked_nets.add(net_name)

        # This is a non-TMR net if less than 2 copies exist
        if num_copies < 2:
            non_tmr_nets.append(net_obj)
            
    return non_tmr_nets

############################################
#             File I/O Helpers             #
############################################

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

def get_outfile_name(outname_arg:str, nets_path:str, tmr_nets_ignored:bool):
    '''
        Generates a name for the output fault report file based on the arguments passed
        in by the user and net list file used
            Arguments: Strings of the file paths to the output file and the net list file,
                       flag telling whether TMR nets were ignored or net
            Returns: String of the appropriate output file name
    '''

    outfile_name = ''

    # Return the user provided name if one was provided
    if outname_arg:
        outfile_name = outname_arg

    # If --all_nets flag was used (no nets file), generate entirely new file name
    elif not nets_path:
        # If TMR nets were ignored, note that in the output file name
        if tmr_nets_ignored:
            outfile_name = 'all_nonTMR_nets_analysis.txt'
        else:
            outfile_name = 'all_nets_analysis.txt'

    # Otherwise, generate name based on input nets file name
    else:
        # Obtain extensionless filename of the nets file
        nets_path = nets_path.strip().split('/')
        nets_file_name, _ = nets_path[-1].split('.')

        # If TMR nets were ignored, note that in the output file name
        if tmr_nets_ignored:
            outfile_name = f'{nets_file_name}_nonTMR_analysis.txt'
        else:
            outfile_name = f'{nets_file_name}_analysis.txt'

    return outfile_name

def print_analysis(analyzed_nets:list, outfile:str):
    '''
        Formats and prints the information about the nets' sensitive bits
            Arguments: analyzed nets list, string of output file path
            Returns: Output file (.txt) of the analysis
    '''
    
    # Open the output file to write to it
    with open(outfile, 'w') as o_f:
        # Write each net's information to the output file
        for net in analyzed_nets:
            o_f.write(f'{net.name}\n')
            o_f.write(f'Pips: ({len(net.pips)})\n')

            # Write each pip's sensitivity information to the file for the net
            for pip in net.pips:
                o_f.write(f'\t{pip.pip_name} - {pip.mux_name} {pip.mux_type} Routing Mux:\n')
                o_f.write(f'\t\tRow Bits: {pip.row_bits}\n')
                o_f.write(f'\t\tColumn Bits: {pip.col_bits}\n\n')
            
            o_f.write(f'Total config bits: {net.num_bits}\n')
            o_f.write('\n-----------------------------------\n\n')

        # Extract the number of related bits from each net's object
        bit_freqs = [net.num_bits for net in analyzed_nets]

        # Gather some summary statistics about the data
        num_nets = len(bit_freqs)
        num_bits = sum(bit_freqs)
        bits_mean = mean(bit_freqs)
        bits_median = median(bit_freqs)
        
        # Standard deviation is only valid for data sets longer than one
        if num_nets > 1:
            bits_sd = stdev(bit_freqs)
        else:
            bits_sd = 'NA'

        # Deciles only valid for data sets larger than 10
        if num_nets > 10:
            bits_deciles = quantiles(bit_freqs, n=10)
        else:
            bits_deciles = 'NA'

        # Print the previously calculated summary statistics
        o_f.write('Summary Statistics:\n')
        o_f.write(f'\tNumber of Nets Analyzed: {num_nets}\n')
        o_f.write(f'\tNumber of Sensitive Bits: {num_bits}\n')
        o_f.write(f'\tMean of Bits Per Net: {bits_mean}\n')
        o_f.write(f'\tStdDev of Bits Per Net: {bits_sd}\n')
        o_f.write(f'\tMedian of Bits Per Net: {bits_median}\n')
        o_f.write(f'\tDeciles of Bits Per Net: {bits_deciles}')

############################################
#               Main Function              #
############################################

def main(args):
    '''
        Main function: Writes a sensitivity report for all the nets given
        for a specific design with all related pips and routing bits
    '''

    # Unserialize data structure if flag is set
    if args.pickled_input:
        print('Unserializing data structure...')
        analyzed_nets = unserialize_structure(args.nets)

        # Remove all triplicated nets from the data structure if flag is set
        if args.non_tmr:
            print('Removing triplicated nets...')
            analyzed_nets[:] = remove_tmr_nets(analyzed_nets, args.non_tmr)

    # Standard net analysis flow
    else:
        print('Building design query...')

        # Create design query object
        if args.rapidwright:
            from lib.rpd_query import RpdQuery
            design = RpdQuery(args.dcp_file)
        else:
            from lib.design_query import VivadoQuery
            design = VivadoQuery(args.dcp_file)

        # Get part tilegrid information
        print('Parsing part tilegrid information from database...')
        tilegrid = parse_tilegrid(design.part)

        # Retrieve the nets to analyze
        print('Retrieving nets...')
        if args.all_nets:
            nets = design.get_all_nets()
        else:
            nets = parse_nets_file(args.nets)

        # Remove all triplicated nets from the list if flag is set
        if args.non_tmr:
            print('Removing triplicated nets...')
            nets[:] = remove_tmr_nets(nets, args.non_tmr)

        print('Analyzing nets...')
        analyzed_nets = []

        # Analyze all nets (retrieve all relevant pips, routing muxes, and configuration bits)
        for net in tqdm(nets):
            analyzed_net = AnalyzedNet(net, design, tilegrid)
            analyzed_nets.append(analyzed_net)

    # Get the output file name
    print('Generating output file...')
    outfile = get_outfile_name(args.out_file, args.nets, bool(args.non_tmr))

    # Print report of the found information
    print_analysis(analyzed_nets, outfile)

    # If the -p flag is set, serialize the analyzed_nets structure and write to a file
    if args.pickle:
        print('Serializing analysis data structure...')
        serialize_structure(analyzed_nets, outfile)

    # If the -g flag is set, graph a histogram of the data
    if args.graph:
        print('Generating histogram of the data...')
        graph_output(analyzed_nets)

    print('Done!')

if __name__ == '__main__':
    import argparse
    # Create Argument Parser to take in command line arguments
    parser = argparse.ArgumentParser(description="Analyzes the given nets in a design and "
                                                + "reports all of the nets' sensitive bits")
    # Input Files
    parser.add_argument('dcp_file', help='Vivado checkpoint file of the implemented design')
    parser.add_argument('nets', nargs='?',
                        help='Text file containing the names of the net(s) to analyze')
    # Feature Flags
    parser.add_argument('-a', '--all_nets', action='store_true',
                        help='Analyze the sensitivity of all nets in the design (this will take a while)')
    parser.add_argument('-rpd', '--rapidwright', action='store_true',
                        help='Flag to use Rapidwright to read design data (unneeded if using --pickled_input')
    parser.add_argument('-g', '--graph', action='store_true',
                        help='Plots a histogram of the frequency that the nets exhibit numbers of routing bits.')
    parser.add_argument('-p', '--pickle', action='store_true',
                        help='Write the analysis data structure in a serialized format to a file')
    parser.add_argument('-pi', '--pickled_input', action='store_true',
                        help='Input a pickled data structure containing the contents of a previous run of this tool '
                        'instead of a nets file')
    parser.add_argument('-ntmr', '--non_tmr', default='', help='Ignore all triplicated nets with the given TMR suffix')
    # Optional Output File Path
    parser.add_argument('-of', '--out_file', default='', help='File path where the output is to be written.')
    args = parser.parse_args()

    # Make sure a nets file is given if the "all" flag is not set
    if not args.nets and not args.all_nets:
        raise Exception('The nets argument is required unless the --all_nets flag is set')

    main(args)