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
    bfat.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2022

    Analyzes a design and evaluates provided fault bits to report their
    identities and the effects of their flipped values on the design.

    Arguments:
        - bitstream of the design to be analyzed
        - dcp vivado checkpoint file of operational design
        - json file of fault bits to analyze

    Optional flags:
        - bits_file [-bf]: Flag to parse in a .bits file instead of a bitstream for the design
        - rapidwright [-rpd]: Flag to use Rapidwright implementation of design querying
        - out_file [-of]: Path of output file. Default is <bit_list_name>_fault_report.txt
        - pickle [-p]: Write fault report data as a .pickle file

    Returns:
        - output file (.txt) that reports the location and cause of any determinable fault bits
'''

import time
import pickle
from io import TextIOWrapper
from tqdm import tqdm
from textwrap import wrap

from lib.tile import Tile
from lib.file_processing import parse_tilegrid, parse_fault_bits, parse_design_bits
from lib.design_query import VivadoQuery
from lib.fault_analysis import FaultBit, analyze_bit_group
from lib.statistics import Statistics, print_stat_footer, get_bit_group_stats
from bitread import get_frame_list, get_high_bits
import lib.scaffold as scaffold

##################################################
# Functions for Design Generation and Processing #
##################################################

def get_tile_type_name(tile:str):
    '''
        Finds and generates name for a tile_type
            Arguments: String of the tile's name
            Returns: String of the tile's type
    '''

    end_index = tile.find('_X')
    return tile[:end_index]

def gen_tile_images(tilegrid:dict, part:str):
    '''
        Generates the data structures storing the information for each tile type on the part
            Arguments: Dict of the part's tilegrid and a string of the part name
            Returns: Dict of images of every tile type in the design
    '''

    tile_imgs = {}
    # Iterate through, and create an object for, each Tile Archetype
    for curr_tile in tilegrid:
        t_tp = get_tile_type_name(curr_tile)
        # If the tile type does not already have an archetype, add it to the dictionary
        if t_tp not in tile_imgs:
            tile_imgs[t_tp] = Tile(t_tp, t_tp, part)

    return tile_imgs

###################################################
#    Functions for Exporting the Fault Report     #
###################################################

def get_outfile_name(outname_arg:str, fault_bits_path:str):
    '''
        Generates a name for the output fault report file based on the arguments passed
        in by the user and fault bit list used
            Arguments: Strings of the file paths to the output file and the fault bit list file
            Returns: String of the appropriate output file name
    '''

    # Return the user provided name if one was provided
    if outname_arg:
        return outname_arg

    fault_bits_path = fault_bits_path.strip().split('/')
    outfile_name, _ = fault_bits_path[-1].split('.')

    # Return the fault bit list file root name with default output file name formatting
    return f'{outfile_name}_fault_report.txt'

def gen_tcl_cmds(bit:FaultBit, outfile:TextIOWrapper):
    '''
        Automatically generates and prints tcl commands to select related design objects
        for the fault bit whose information is passed in.
            Arguments: List of fault info and opened file object for output file
    '''

    tile_type = get_tile_type_name(bit.tile)

    outfile.write('\n\tVivado Tcl Commands:\n')

    # Print additional Tcl commands for pips and nets if this is a routing fault
    if 'Opens' in bit.failure or 'Shorts' in bit.failure or 'Faults' in bit.failure:
        
        # Only print pips if this is an INT tile
        if 'INT' in bit.tile:
            # Print the tcl command for selecting the affected pips
            reformatted_pips = [f'{bit.tile}/{tile_type}.{pip.split(" ")[0]}' for pip in bit.affected_pips]
            outfile.write(f'\t\tselect_objects [get_pips {{{" ".join(sorted(reformatted_pips))}}}]\n')

        msg_nets = []

        # Determine composition of fault message and extract nets from it
        if ';' in bit.failure:
            fault_msg_halves = bit.failure.split(';')
            for half in fault_msg_halves:
                half = half.split(':')[1]
                msg_nets.extend(half.strip().split(', '))
        else:
            net_list_str = bit.failure.split(':')[1]
            msg_nets.extend(net_list_str.strip().split(', '))

        # Identify all unconnected node placeholders from message
        uc_nets = set()
        for msg_net in msg_nets:
            if 'Unconnected Wire' in msg_net:
                uc_nets.add(msg_net)

        # Remove all unconnected node placeholders from message nets
        for uc_net in uc_nets:
            msg_nets.remove(uc_net)

        if msg_nets:
            msg_nets_str = ' '.join(sorted(msg_nets))

            # Change net names for VCC and GND so they can be selected with the tcl command
            msg_nets_str = msg_nets_str.replace("GLOBAL_LOGIC0", "<const0>")
            msg_nets_str = msg_nets_str.replace("GLOBAL_LOGIC1", "<const1>")

            # Remove "(initially connected)" from string"
            msg_nets_str = msg_nets_str.replace(' (initially connected)', '')

            outfile.write(f'\t\tselect_objects [get_nets {{{msg_nets_str}}}]\n')

    # Get the cells of the affected resources if there are any and add them
    # to the generated tcl command to select them in Vivado
    if bit.affected_rsrcs and 'NA' not in bit.affected_rsrcs and 'No affected resources found' not in bit.affected_rsrcs:
        aff_rsrcs_str = ' '.join(sorted(bit.affected_rsrcs))
        outfile.write(f'\t\tselect_objects [get_cells {{{aff_rsrcs_str}}}]\n')
    elif 'INT' in bit.tile and ('Opens' in bit.failure or 'Shorts' in bit.failure):
        outfile.write('\n')
    outfile.write('\n')

def classify_fault_bits(group_bits:dict):
    '''
        Separates the insignificant fault bits from the significant and sorts them
        into their own dictionaries storing any significant information they have.
            Arguments: Dict of the fault bits in the bit group
            Returns: Lists of the failure, non-failure, and undefined bits in the fault report
    '''

    undefined_bits = []
    nonfailure_bits = []
    failure_bits = []

    # Set failure message indicator substrings
    nf_strs = ['not yet supported',
               'Not able to find any failures',
               'No instanced resource']

    # Iterate through each fault bit in the current bit group and classify fault bits
    for b in group_bits.values():
        # Classify fault bit by its definition
        if type(b.tile) == list:
            undefined_bits.append(b)
        else:
            # Classify fault bit by any found failures for the bit
            if any([nf_str in b.failure for nf_str in nf_strs]):
                nonfailure_bits.append(b)
            else:
                failure_bits.append(b)

    return failure_bits, nonfailure_bits, undefined_bits

def print_bit_group_section(section_name:str, section_bits, outfile:TextIOWrapper):
    '''
        Prints information for a single section of a bit_group in the fault report
            Arguments: String of the section name, dict or list of the section bits, and the
                       open output file to write to
    '''

    # Print section if there are bits in the section
    if section_bits:
        soft_divider = '-' * 30
        outfile.write(f'{section_name}:\n{soft_divider}\n')

        # Identify section and print its information in its respective format
        if section_name == 'Failure Bits':
            # Print out the information for each fault bit in the current bit group
            for sb in section_bits:
                outfile.write(f'{sb.bit} ({sb.type})\n')

                # If the bit has more than one function, print them all under a header
                if len(sb.phys_fctns) > 1:
                    outfile.write('\tBit Functions:\n')
                    # Iterate through and print all bit functions
                    for fctn in sb.phys_fctns:
                        # Convert the bit function to a dash-seperated string
                        bit_fctn_str = ' - '.join(fctn)
                        outfile.write(f'\t\t{sb.tile} - {bit_fctn_str}\n')

                # Otherwise, just print the function
                else:
                    # Convert the bit function to a dash-seperated string
                    bit_fctn_str = ' - '.join(sb.phys_fctns[0])
                    outfile.write(f'\t{sb.tile} - {bit_fctn_str}\n')

                outfile.write(f'\tResource Design Name: {sb.design_name}\n')

                # Change some net names in the fault message for consistency
                sb.failure = sb.failure.replace('GLOBAL_LOGIC0', '<const0>')
                sb.failure = sb.failure.replace('GLOBAL_LOGIC1', '<const1>')

                outfile.write(f'\t{sb.failure}\n')

                # Only print affected pips if this is a routing bit
                if 'INT' in sb.tile:
                    outfile.write('\tAffected PIPs:\n')
                    # Print each affected pip in an indented list of 1 per line
                    for aff_pip in sb.affected_pips:
                        outfile.write(f'\t\t{aff_pip}\n')

                outfile.write('\tAffected Resources:\n')
                # Print each affected resource in an indented list of 1 per line
                for aff_rsrc in sorted(sb.affected_rsrcs):
                    outfile.write(f'\t\t{aff_rsrc}\n')

                # Print a note if one was logged for the bit (text wrap for long strings)
                if sb.note != 'NA' and '\n' not in sb.note:
                    wrap_len = 70
                    note_wrapped = '\n\t'.join(wrap(sb.note, wrap_len))
                    outfile.write(f'\n\t{note_wrapped}\n')
                elif sb.note != 'NA':
                    outfile.write(f'\n\t{sb.note}')

                gen_tcl_cmds(sb, outfile)

        elif section_name == 'Undefined Bits':
            # Print out each undefined bit and its potential tiles
            for sb in section_bits:
                outfile.write(f'{sb.bit} ({sb.type})\n')
                outfile.write('\tPotential Affected Resources:\n')

                # Print each potential tile and its cells for the undefined bit
                for tile, possible_aff_rsrcs in sorted(sb.affected_rsrcs.items()):
                    outfile.write(f'\t\t{tile}:\n')
                    for bel, rsrc in sorted(possible_aff_rsrcs.items()):
                        outfile.write(f'\t\t\t{bel}: {rsrc}\n')
                    if possible_aff_rsrcs == {}:
                        outfile.write('\t\t\tNo resources found for this tile\n')

                if sb.affected_rsrcs == {}:
                    outfile.write('\t\tNo potential tiles found\n')

            outfile.write('\n')
        else:
            # Print out each non-failure bit and bit information
            for sb in section_bits:
                outfile.write(f'{sb.bit} ({sb.type}): ')
                
                # Convert the bit function to a dash-seperated string
                bit_fctn_str = ' - '.join(sb.phys_fctns[0])
                outfile.write(' - '.join([sb.tile, bit_fctn_str, sb.design_name]))
                
                outfile.write('\n')
                outfile.write(f'\t{sb.failure}\n')
            outfile.write('\n')

def print_fault_report(outfile:str, fault_report:dict):
    '''
        Prints the fault_report passed in to the output text file designated by the user.
            Arguments: String of the outfile path and dict of the design's fault report
            Return: Statistics object of total statistic values for the design
    '''

    statistics = Statistics()

    # Open the output file to write to
    with open(outfile, 'w') as out_f:

        heavy_divider = '=' * 70

        # Iterate through significant fault bits of each bit group and print out its information
        for bit_group, group_bits in fault_report.items():
            # Only print fault bit information if there are still fault bits in the bit group
            if group_bits:
                out_f.write(f'{heavy_divider}\n')
                title_center_offset = ' ' * 29
                out_f.write(f'{title_center_offset}Bit Group {bit_group}\n')
                out_f.write(f'{heavy_divider}\n\n')

                failure_bits, nonfailure_bits, undefined_bits = classify_fault_bits(group_bits)

                # Print summary of each section
                print_bit_group_section('Failure Bits', failure_bits, out_f)
                print_bit_group_section('Non-Failure Bits', nonfailure_bits, out_f)
                print_bit_group_section('Undefined Bits', undefined_bits, out_f)

                # Calculate and print group stats, and update total stats
                group_stats = get_bit_group_stats(group_bits, True, out_f)
                statistics.update(group_stats.stats)

    return statistics

def pickle_fault_report(report_name:str, fault_report:dict):
    '''
        Serializes the fault report data structure. Saved with the same name
        as the fault report but a different file extension.
            Arguments: String of the original fault report path and dict of
                       the design's fault report
    '''

    # Change file extension to .pickle
    if len(report_name.split('.')) > 1:
        report_name = '.'.join(report_name.split('.')[:-1])
    outfile_name = report_name + '.pickle'

    # Open the file to write the data to
    with open(outfile_name, 'wb') as o_f:
        pickle.dump(fault_report, o_f)

###################################################
#                 Main Functions                  #
###################################################

def bfat_scaffold(args):
    '''
        Main function: Creates a report of the effects the passed in fault bits have
        on the given design. Assumes arguments from "scaffold" subcommand.
    '''
    
    t_start = time.perf_counter()
    
    # Parse in all high bits from the bitstream or from a .bits file [base_frame, word, bit]
    print("Reading in Design Bits...")
    design_bits = scaffold.get_design_bits(args.design)
    
    # Create a design query to get design info from the dcp file
    print("Generating Design Query...")
    design = scaffold.get_design_query(args.design, args.rapidwright)
    
    # Parse in the corresponding part's tilegrid.json file
    print('Parsing in Input Files...')
    tilegrid = parse_tilegrid(design.part)
    # Parse in a frame list for the part
    frame_list = [frame[0] for frame in get_frame_list(design.part)]
    # Parse in the fault bit information
    bit_groups = scaffold.get_fault_bits(args.design, args.fault_bits)
    
    # Generate images of tiles from the part's tilegrid
    print('Generating Tile Images...')
    tile_imgs = gen_tile_images(tilegrid, design.part)
    
    # Create dynamic progress bar for fault analysis of bit groups 
    fa_pbar = tqdm(bit_groups.items())
    fa_pbar.set_description('Analyzing Fault Bit Groups')
    
    # Define and evaluate each fault bit and generate data structure for a report
    fault_report = {}
    for bg, grp_bits in fa_pbar:
        fault_report[bg] = analyze_bit_group(grp_bits, frame_list, tilegrid, tile_imgs, design_bits, design)
        
    # Create and output report based on analysis of fault bits
    print('Printing Fault Report...')
    outfile = get_outfile_name(args.out_file, args.fault_bits)
    scaffold.write_fault_report(fault_report, args.design, outfile, args.rapidwright, round(time.perf_counter()-t_start, 2), args.pickle)

def bfat_manual(args):
    '''
        Main function: Creates a report of the effects the passed in fault bits have
        on the given design. Assumes arguments from "manual" subcommand.
    '''

    t_start = time.perf_counter()

    # Parse in all high bits from the bitstream or from a .bits file [base_frame, word, bit]
    print('Reading in Design Bits...')
    if args.bits_file:
        design_bits = parse_design_bits(args.bitstream)
    else:
        design_bits = get_high_bits(args.bitstream)

    # Create a design query to get design info from the dcp file
    print('Generating Design Query...')
    if args.rapidwright:
        from lib.rpd_query import RpdQuery
        design = RpdQuery(args.dcp_file)
    else:
        design = VivadoQuery(args.dcp_file)

    # Parse in the corresponding part's tilegrid.json file
    print('Parsing in Input Files...')
    tilegrid = parse_tilegrid(design.part)
    # Parse in a frame list for the part
    frame_list = [frame[0] for frame in get_frame_list(design.part)]
    # Parse in the fault bit information
    bit_groups = parse_fault_bits(args.fault_bits)

    # Generate images of tiles from the part's tilegrid
    print('Generating Tile Images...')
    tile_imgs = gen_tile_images(tilegrid, design.part)

    # Create dynamic progress bar for fault analysis of bit groups 
    fa_pbar = tqdm(bit_groups.items())
    fa_pbar.set_description('Analyzing Fault Bit Groups')
    
    # Define and evaluate each fault bit and generate data structure for a report
    fault_report = {}
    for bg, grp_bits in fa_pbar:
        fault_report[bg] = analyze_bit_group(grp_bits, frame_list, tilegrid, tile_imgs, design_bits, design)

    # Create and output report based on analysis of fault bits
    print('Printing Fault Report...')
    outfile = get_outfile_name(args.out_file, args.fault_bits)
    statistics = print_fault_report(outfile, fault_report)

    # Calculate and print fault bit statistics
    print('Printing Statistical Footer...')
    print_stat_footer(outfile, design.dcp, args.rapidwright, statistics, round(time.perf_counter()-t_start, 2))

    # Export fault report as .pickle if flag is set
    if args.pickle:
        print('Exporting Fault Report to .pickle...')
        pickle_fault_report(outfile, fault_report)

if __name__ == '__main__':
    import argparse
    
    bfat_desc = 'Analyzes a design and evaluates provided fault bits to report the identities and ' \
                'the effects of the flipped values of each fault bit on the design.'
    
    # Create root Argument Parser to take in commandline arguments
    parser = argparse.ArgumentParser(description=bfat_desc)
    subparsers = parser.add_subparsers()
    
    # Parent argument parser for arguments which are common between subparsers
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-rpd', '--rapidwright', action='store_true',
                        help='Flag to use Rapidwright to read design data')
    parent_parser.add_argument('-p', '--pickle', action='store_true',
                        help='Flag to write a .pickle file containing the raw fault report data')
    
    # Parser for inputs using new file system
    scaffold_sp = subparsers.add_parser("scaffold", description=bfat_desc+" Read and write files using the existing directory scaffolding as a base.", parents = [parent_parser])
    scaffold_sp.add_argument("design", help="Name of the design to analyze")
    scaffold_sp.add_argument("fault_bits", help="Filename of the JSON file listing bits of interest")
    scaffold_sp.add_argument("-of", "--out_file", help="Filename of the output report")
    scaffold_sp.set_defaults(func=bfat_scaffold)
    
    # Parser for inputs using old file system
    manual_sp = subparsers.add_parser("manual", description=bfat_desc+" Manually specify the locations of files to read from and write to", parents = [parent_parser])
    manual_sp.add_argument("bitstream", help="Bitstream file of the design to be analyzed")
    manual_sp.add_argument("dcp_file", help="Vivado checkpoint file of the implemented design")
    manual_sp.add_argument("fault_bits", help="Json file listing bits of interest")
    manual_sp.add_argument("-of", "--out_file", help="File path where the output is to be written")
    manual_sp.add_argument('-bf', '--bits_file', action='store_true', default='',
                        help='Specify a .bits text file of all high bits instead of a bitstream')
    manual_sp.set_defaults(func=bfat_manual)
    
    args = parser.parse_args()
    args.func(args)