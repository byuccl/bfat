'''
    bfat.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Analyzes a design and evaluates provided fault bits to report their
    identities and the effects of their flipped values on the design.

    Arguments:
        -bitstream of the design to be analyzed
        -dcp vivado checkpoint file of operational design
        -json file of fault bits to analyze

    Optional flags:
        -out_file [-of]: Path of output file. Default is <design_name>_fault_report.txt
        -debug [-d]: Flag for printing debug statements included in code to standard out

    Returns:
        -output file (.txt) that reports the location and cause of any determinable fault bits
'''

import time
import json
from io import TextIOWrapper
from lib.tile import Tile
from lib.file_processing import parse_tilegrid, parse_fault_bits
from lib.design_query import VivadoQuery
from lib.bit_definitions import def_fault_bits
from lib.statistics import Statistics, print_stat_footer, get_bit_group_stats
from bitread import get_high_bits

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

def gen_tile_images(tile_info:dict, part:str):
    '''
        Generates the data structures storing the information for each tile type on the part
            Arguments: Dict of the part's tilegrid and a string of the part name
            Returns: Dict of images of every tile type in the design
    '''

    tile_imgs = {}
    # Iterate through, and create an object for, each Tile Archetype
    for curr_tile in tile_info:
        t_tp = get_tile_type_name(curr_tile)
        # If the tile type does not already have an archetype, add it to the dictionary
        if t_tp not in tile_imgs:
            tile_imgs[t_tp] = Tile(t_tp, t_tp, part)

    return tile_imgs

##################################################
#    Functions for Printing the Fault Report     #
##################################################

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

def gen_tcl_cmds(fault_info:list, outfile:TextIOWrapper):
    '''
        Automatically generates and prints tcl commands to select related design objects
        for the fault bit whose information is passed in.
            Arguments: List of fault info and opened file object for output file
    '''

    tile, _, _, _, _, fault_msg, aff_rsrcs, aff_pips = fault_info
    tile_type = get_tile_type_name(tile)

    # Get the nets and pips from the fault bit's fault info and add them to
    # the generated tcl command to select them in Vivado
    if 'INT' in tile and ('Opens' in fault_msg or 'Shorts' in fault_msg):
        
        # Print the tcl command for selecting the affected pips
        reformatted_pips = [f'{tile}/{tile_type}.{pip.split(" ")[0]}' for pip in aff_pips]
        outfile.write(f'\n\tselect_objects [get_pips {{{" ".join(reformatted_pips)}}}]')

        msg_nets = []

        # Determine composition of fault message and extract nets from it
        if ';' in fault_msg:
            fault_msg_halves = fault_msg.split(';')
            for half in fault_msg_halves:
                half = half.split(':')[1]
                msg_nets.extend(half.strip().split(', '))
        else:
            net_list_str = fault_msg.split(':')[1]
            msg_nets.extend(net_list_str.strip().split(', '))

        # Identify all unconnected node placeholders from message
        uc_nets = set()
        for msg_net in msg_nets:
            if 'Unconnected Node' in msg_net:
                uc_nets.add(msg_net)

        # Remove all unconnected node placeholders from message nets
        for uc_net in uc_nets:
            msg_nets.remove(uc_net)

        if msg_nets:
            msg_nets_str = ' '.join(sorted(msg_nets))

            # Change net names for VCC and GND so they can be selected with the tcl command
            msg_nets_str = msg_nets_str.replace("GLOBAL_LOGIC0", "GND_2")
            msg_nets_str = msg_nets_str.replace("GLOBAL_LOGIC1", "VCC_2")

            outfile.write(f'\n\tselect_objects [get_nets {{{msg_nets_str}}}]')

    # Get the cells of the affected resources if there are any and add them
    # to the generated tcl command to select them in Vivado
    if aff_rsrcs and 'NA' not in aff_rsrcs and 'No affected resources found' not in aff_rsrcs:
        aff_rsrcs_str = ' '.join(sorted(aff_rsrcs))
        outfile.write(f'\n\tselect_objects [get_cells {{{aff_rsrcs_str}}}]\n')
    elif 'INT' in tile and ('Opens' in fault_msg or 'Shorts' in fault_msg):
        outfile.write('\n')
    outfile.write('\n')

def classify_fault_bits(group_bits:dict):
    '''
        Separates the insignificant fault bits from the significant and sorts them
        into their own dictionaries storing any significant information they have.
            Arguments: Dict of the fault bits in the bit group
            Returns: Dicts of the significant, errorless, and unsupported bits in the fault
                     report and a list of the undefined bits in the fault_report
    '''

    undefined_bits = []
    unsupported_bits = {}
    errorless_bits = {}
    significant_bits = {}

    # Iterate through each fault bit in the current bit group and classify fault bits
    for fault_bit, bit_info in group_bits.items():
        tile, rsrc, fctn, dsgn_rsrc, _, fault_msg, _, _ = bit_info

        # Classify fault bit by its significance and add it to its respective collections
        if tile == 'NA':
            undefined_bits.append(fault_bit)
        elif tile != 'NA' and 'not yet supported' in fault_msg:
            unsupported_bits[fault_bit] = [tile, rsrc, fctn]
        elif 'Not able to find any errors' in fault_msg or 'No instanced resource' in fault_msg:
            errorless_bits[fault_bit] = [tile, rsrc, fctn, dsgn_rsrc]
        else:
            significant_bits[fault_bit] = bit_info

    return significant_bits, errorless_bits, unsupported_bits, undefined_bits

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
        if section_name == 'Significant Bits':
            # Print out the information for each fault bit in the current bit group
            for fault_bit, bit_info in section_bits.items():
                tile, rsrc, fctn, dsgn_rsrc, change, fault_msg, aff_rsrcs, aff_pips = bit_info
                outfile.write(f'{fault_bit} ({change})\n')
                outfile.write(f'\t{tile} - {rsrc} - {fctn}\n')
                outfile.write(f'\tResource Design Name: {dsgn_rsrc}\n')

                # Change some net names in the fault message for consistency
                fault_msg = fault_msg.replace('GND_2', 'GLOBAL_LOGIC0')
                fault_msg = fault_msg.replace('GND_4', 'GLOBAL_LOGIC0')
                fault_msg = fault_msg.replace('VCC_2', 'GLOBAL_LOGIC1')
                fault_msg = fault_msg.replace('VCC_4', 'GLOBAL_LOGIC1')

                outfile.write(f'\t{fault_msg}\n')

                # Only print affected pips if this is a routing bit
                if 'INT' in tile:
                    outfile.write('\tAffected PIPs:\n')
                    # Print each affected pip in an indented list of 1 per line
                    for aff_pip in aff_pips:
                        outfile.write(f'\t\t{aff_pip}\n')

                outfile.write('\tAffected Resources:\n')
                # Print each affected resource in an indented list of 1 per line
                for aff_rsrc in sorted(aff_rsrcs):
                    outfile.write(f'\t\t{aff_rsrc}\n')

                gen_tcl_cmds(bit_info, outfile)

        elif section_name == 'Undefined Bits':
            # Print out each undefined bit
            for bit in section_bits:
                outfile.write(f'{bit}\n')
            outfile.write('\n')
        else:
            # Print out each error-less bit and bit information
            for bit, bit_info in section_bits.items():
                outfile.write(f'{bit}: ')
                outfile.write(' - '.join(bit_info))
                outfile.write('\n')
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

                significant_bits, errorless_bits, unsupported_bits, undefined_bits = classify_fault_bits(group_bits)

                # Print summary of each section
                print_bit_group_section('Significant Bits', significant_bits, out_f)
                print_bit_group_section('Errorless Bits', errorless_bits, out_f)
                print_bit_group_section('Unsupported Bits', unsupported_bits, out_f)
                print_bit_group_section('Undefined Bits', undefined_bits, out_f)

                # Calculate and print group stats, and update total stats
                group_stats = get_bit_group_stats(group_bits, True, out_f)
                statistics.update(group_stats.stats)
                # print_bit_group_stats(out_f, group_stats)

    return statistics

##################################################
#         Helper and Debugging Functions         #
##################################################

def change_bit(tiles:dict, curr_tile:str, bit:str, value:int):
    '''
        Helper function that changes the value of a single bit from a single tile
            Arguments: Dict of all tiles in the design, strings of the tile, the bit's
                       address, and the int value to assign it
    '''

    tiles[curr_tile].change_bit(bit, value)

def debug_print(message:str, debug_flag:bool):
    '''
        Wrapper/helper function to print the debug statement only if the debug
        flag has been raised.
            Arguments: String of the message to be printed and bool debug flag
    '''

    if debug_flag:
        print(message)

##################################################
#                 Main Function                  #
##################################################

def main():
    '''
        Main function: Creates a report of the effects the passed in fault bits have
        on the given design.
    '''

    t_start = time.perf_counter()

    # Parse in all high bits from the bitstream [base_frame, word, bit] and get the part name
    design_bits, part = get_high_bits(ARGS.bitstream)
    debug_print(f'Bitstream Read In:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Parse in the corresponding part's tilegrid.json file
    tile_info = parse_tilegrid(part)
    # Parse in the fault bit information
    bit_groups = parse_fault_bits(ARGS.fault_bits)
    debug_print(f'Input Files Parsed:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Generate images of tiles from the part's tilegrid
    tile_imgs = gen_tile_images(tile_info, part)
    debug_print(f'Tile Images Generated:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Create a design query to get design info from the dcp file
    design = VivadoQuery(ARGS.dcp_file)
    debug_print(f'Design Query Created:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Define and evaluate each fault bit and generate data structure for a report
    fault_report = def_fault_bits(bit_groups, tile_info, tile_imgs, design_bits, design)
    debug_print(f'Fault Bits Analyzed:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Write fault report data structure out to provided json file
    if ARGS.json:
        # Open output json file and write to it
        with open(ARGS.json, 'w') as jo_f:
            json.dump(fault_report, jo_f, indent = 4)

        debug_print(f'JSON File Written:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Create and output report based on analysis of fault bits
    outfile = get_outfile_name(ARGS.out_file, ARGS.fault_bits)
    statistics = print_fault_report(outfile, fault_report)
    debug_print(f'Fault Report Printed:\t\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

    # Calculate and print fault bit statistics
    print_stat_footer(outfile, ARGS.dcp_file, statistics, round(time.perf_counter()-t_start, 2))
    debug_print(f'Statistical Footer Printed:\t{round(time.perf_counter()-t_start, 2)} sec', ARGS.debug)

if __name__ == '__main__':
    import argparse
    # Create Argument Parser to take in commandline arguments
    PARSER = argparse.ArgumentParser(description='Analyzes a design and evaluates provided fault '
                                                + 'bits to report the identities and the effects '
                                                + 'of the flipped values of each fault bit on '
                                                + 'the design.')
    PARSER.add_argument("bitstream", help='Bitstream file of the design to be analyzed')
    PARSER.add_argument('dcp_file', help='Vivado checkpoint file of the implemented design')
    PARSER.add_argument('fault_bits', help='Json file listing bits of interest')
    PARSER.add_argument('-of', '--out_file', default='',
                        help='File path where the output is to be written.')
    PARSER.add_argument('-d', '--debug', action='store_true', help='Flag debug statements')
    PARSER.add_argument('-j', '--json', default='',
                        help='File path to write fault report data as additional json file')
    ARGS = PARSER.parse_args()

    main()
