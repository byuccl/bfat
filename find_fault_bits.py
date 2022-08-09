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
    find_fault_bits.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    A script that generates a list of example fault bits for the given design.
    The kinds of faults that are auto-generated are:
        - LUT fault
        - Open in a net
        - Short between two nets
        - Short between net and unconnected node
        - Undefined bit (tile and function of bit could not be determined)
        - Errorless bits (CLB and INT bit)

    Arguments:
        - bitstream of the design
        - dcp vivado checkpoint file of operational design

    Optional flags:
        -run [-r]: Bitstream, dcp, and fault bits will be run through BFAT
        -debug [-d] Verbose printing after major function returns for debug purposes

    Returns:
        -output file (.json) in the working directory that contains the fault bits
'''

from bfat import get_tile_type_name, debug_print
from bitread import get_high_bits, get_frame_list
from lib.design_query import DesignQuery, VivadoQuery
from lib.file_processing import parse_tilegrid
from lib.tile import Tile
from lib.bit_definitions import bit_bitstream_addr
import subprocess
import json
import os
import time

def get_bit_in_LUT(design:DesignQuery, tilegrid_info:dict, part_name:str):
    '''
        Determines what bit must be flipped in order to create a LUT fault
            Arguments: Design query object, tilegrid information for the part, set of
                       all used CLB tiles, part name
            Returns: list of fault bits required to affect the LUT
    '''

    # Get all used CLB tiles
    used_CLB_tiles = design.get_CLB_tiles(True)

    # Iterate through tiles, sites, and resources until a LUT is found
    for tile_name in used_CLB_tiles:

        # Query design for cells in the tile, skip iteration of loop if the tile is empty
        design.query_cells(tile_name)
        if tile_name not in design.cells:
            continue

        # Iterate through slices until a LUT is found
        for slice_name in design.cells[tile_name]:           
            # Iterate through slice resources until a LUT is found
            for resource in design.cells[tile_name][slice_name]:
                if '6LUT' in resource:
                    break
            else:
                # Continue if LUT is not found
                continue
            # Break if LUT is found
            break
        else:
            # Continue if LUT is not found
            continue
        # Break if LUT is found
        break
    
    # Error detection for if there is somehow no LUTs in the entire design
    if design.get_cell(tile_name, slice_name, resource) == 'NA':
        print('The provided design does not utilize any LUTs, please use a more complex design')
        return []

    # Build tile object for the tile that the cell resides in
    tile_type = get_tile_type_name(tile_name)
    tile_obj = Tile(tile_name, tile_type, part_name)

    # Slice physical X position
    slice_x_pos = int(slice_name[(slice_name.find('X')+1):slice_name.find('Y')])

    # If the slice X address is even, it is an X0 slice
    if slice_x_pos % 2 == 0:
        # If this is a CLBLM tile, this is a SLICEM
        if 'CLBLM' in tile_type:
            new_slice_name = 'SLICEM_X0'
        else:
            new_slice_name = 'SLICEL_X0'
    else:
        new_slice_name = 'SLICEL_X1'

    # Build LUT resource name that matches the format of the tilegrid database
    new_resource_name = f'{new_slice_name}.{resource.replace("6", "")}.INIT[00]'

    # Get the bit address matching the LUT intialization bit specified (00)
    try:
        init_bit = tile_obj.resources[new_resource_name][0]
    except KeyError:
        print("The given resource does not exist:", new_resource_name)
        return    

    # Convert from 2-number tile address to 3-number bitstream address
    tile_bit_addr = [tile_name, init_bit, 0]
    bitstream_addr = bit_bitstream_addr(tile_bit_addr, tilegrid_info)

    return [bitstream_addr[4:].replace('_', ' ')]


def get_bit_for_open(design:DesignQuery, tilegrid_info:dict, used_INT_tiles:set, part_name:str):
    '''
        Determines what bits must be flipped to create an open in a net of the design
            Arguments: Design query object, tilegrid information for the part, set of
                       used INT tiles, part name
            Returns: List of bits required to create open
    '''

    # Iterate through INT tiles until a suitable pip to open is found
    for tile_name in used_INT_tiles:
        # Query the design for nets in the tile, skip iteration if no nets are found
        design.query_nets(tile_name)
        if tile_name not in design.nets:
            continue
        
        # Iterate through nets in the tile until a suitable pip to open is found
        for net in design.nets[tile_name].values():
            # Query the design for pips in the net, skip iteration if no pips are found
            design.query_pips(net)
            if net in design.pips:
                # Get a pip that the net uses that passes through the current tile
                pip_in_tile = [net_pip for net_pip in design.pips[net] if tile_name in net_pip[1]][0]
                break
        else:
            # Continue if suitable pip is not found
            continue
        # Break if suitable pip is found
        break
    
    # Error detection if there is somehow no pips in the entire design
    if design.get_pips(net) == 'NA':
        print('The provided design does not utilize any interconnect tile routing muxes, '
             + 'please use a more complex design')

    # Break pip into source and sink, remove tile from node names
    src = pip_in_tile[0].split('/')[1]
    sink = pip_in_tile[1].split('/')[1]

    # Build tile object for the tile that the pip resides in
    tile_type = get_tile_type_name(tile_name)
    tile_obj = Tile(tile_name, tile_type, part_name)

    # Get the first bit in the given pip's bit rule
    try:
        # Edge case for VCC or GND
        if src == 'VCC_WIRE' or src == 'GND_WIRE':
            pip_rule_bit = tile_obj.resources[sink].row_bits[0]
        else:
            pip_rule_bit = tile_obj.pips[sink][src][0]
    except KeyError:
        print("The given pip does not exist")
        return
    
    # We only need the address of the bit, not whether it must be on/off
    if pip_rule_bit[0] == '!':
        pip_rule_bit = pip_rule_bit[1:]

    # Convert from 2-number tile address to 3-number bitstream address
    tile_bit_addr = [tile_name, pip_rule_bit, 0]
    bitstream_addr = bit_bitstream_addr(tile_bit_addr, tilegrid_info)

    return [bitstream_addr[4:].replace('_', ' ')]


# TODO: Get all tiles with at least two nets?
def get_bits_for_short(design:DesignQuery, tilegrid_info:dict, INT_tiles:set, design_bits:list, part_name:str, uc_node:bool):
    '''
        Determines what bits must be flipped to create a short between nets in the design
            Arguments: Design query object, tilegrid information for the part, list of high bits
                       in the bitstream, part name, set of used INT tiles, flag to determine
                       whether the short should be with a net or an unconnected node
             Returns: List of bits required to create short
    '''

    # Iterate through all INT tiles
    for tile_name in INT_tiles:
        # Skip loop iteration if the tile does not have any nets
        design.query_nets(tile_name)
        if tile_name not in design.nets:
            continue

        # Build tile object for the tile current tile
        tile_type = get_tile_type_name(tile_name)
        tile_obj = Tile(tile_name, tile_type, part_name)

        # Iterate through nodes in the tile and the nets mapped onto them
        for sink_node, sink_net in design.nets[tile_name].items():
            # Query design for pips that the net passes through
            design.query_pips(sink_net)

            # Get all interconnect sinks that the net passes through
            net_pip_sinks = [net_pip[1] for net_pip in design.pips[sink_net]]

            # Get the pip for which sink_node is a sink
            try:
                active_pip = design.pips[sink_net][net_pip_sinks.index(tile_name + '/' + sink_node)]
                # Strip tile names from the pip
                active_pip = [node.split('/')[1] for node in active_pip]
            except ValueError:
                continue

            try:
                # Iterate through all sources of the current sink
                for src in tile_obj.pips[active_pip[1]]:
                    # Depending on the uc_node flag, check to make sure that either a net or an unconnected
                    # node is routed through the current source
                    if src != active_pip[0] and src in design.nets[tile_name] and not uc_node:
                        # Model a pip using the source and sink which have been found
                        inactive_pip = [src, active_pip[1]]
                    elif src != active_pip[0] and src not in design.nets[tile_name] and uc_node:
                        # Model a pip using the source and sink which have been found
                        inactive_pip = [src, active_pip[1]]
                    else:
                        continue

                    # Get bit rules for both pips
                    active_pip_rule = tile_obj.pips[active_pip[1]][active_pip[0]]
                    try:
                        inactive_pip_rule = tile_obj.pips[inactive_pip[1]][inactive_pip[0]]
                    except KeyError:
                        continue
                    
                    # Determine which bits must be flipped in order to activate the inactive pip
                    bit_group = choose_bits_in_rules(tile_name, active_pip_rule, inactive_pip_rule,
                                                     design_bits, tilegrid_info)

                    # Only return if the bit group contains exactly one bit
                    if len(bit_group) == 1:
                        return bit_group

            except KeyError:
                break
    
    print('The provided design is not complex enough to create a short between two nets, '
         + 'please use a more complex design')
    return []


def choose_bits_in_rules(tile_name:str, active_pip_rule:list, inactive_pip_rule:list, design_bits:list, tilegrid_info:dict):
    '''
        Determines which bits in the bitstream to flip to activate the inactive pip while maintaining
        the status of the active pip.
            Arguments: name of the current tile, bit rule for active pip, bit rule for inactive pip,
                       list of high bits in bitstream, tilegrid information for part
    '''

    # Determine if it is possible for both pips to be active at the same time
    for bit in active_pip_rule:
        if bit[0] == '!' and bit[1:] in inactive_pip_rule:
            return []
        elif bit[0] != '!' and f'!{bit}' in inactive_pip_rule:
            return []

    bit_group = []
    # Iterate through the bits in the inactive pip rule
    for bit in inactive_pip_rule:
        # Determine whether bit must be on or off for the pip to activate
        if bit[0] == '!':
            # Convert from 2-number tile address to 3-number bitstream address
            tile_bit_addr = [tile_name, bit[1:], 0]
            bitstream_addr = bit_bitstream_addr(tile_bit_addr, tilegrid_info)

            # If the bit is high in the bitstream, add it to fault bits list
            if bitstream_addr in design_bits:
                bit_group.append(bitstream_addr.replace('_', ' '))
        else:
            # Convert from 2-number tile address to 3-number bitstream address
            tile_bit_addr = [tile_name, bit, 0]
            bitstream_addr = bit_bitstream_addr(tile_bit_addr, tilegrid_info)[4:]

            # If the bit is low in the bitstream, add it to fault bits list
            if f'bit_{bitstream_addr}' not in design_bits:
                bit_group.append(bitstream_addr.replace('_', ' '))

    return bit_group


def get_undefined_bit(part:str):
    '''
        Finds a bit address that does not exist in the bitstream for demonstration purposes
            Arguments: part name (str)
            Returns: list including the undefined bit
    '''

    # Extract the string formatted frame list from the string/binary combo that the function returns
    frame_list = [frame_list_extra[0] for frame_list_extra in get_frame_list(part)]

    # Iterate through frame list until a gap in the addresses is found
    for index, frame_addr in enumerate(frame_list):
        addr_plus_1 = hex(int(frame_addr, 16)+1)[2:].rjust(8, '0')
        if frame_list[index+1] != addr_plus_1:
            frame_to_use = addr_plus_1
            break

    # Generate bitstream address using the frame that is not in the frame list
    bitstream_addr = frame_to_use + ' 000 00'
    return [bitstream_addr]


def get_errorless_bits(design:DesignQuery, tilegrid_info:dict, used_INT_tiles:set, part_name:str):
    '''
        Determines a CLB bit and an INT bit which will not cause an error in the design
            Arguments: Design query object, tilegrid information for the part,
            set of all used INT tiles, part name
            Returns: list of errorless fault bits
    '''
    
    # Get all CLB tiles with unused slices
    unused_CLB_tiles = design.get_CLB_tiles(False)

    unmapped_CLB = 'NA'
    # Iterate through CLB tiles and find one with no cells mapped to it
    for CLB_tile in unused_CLB_tiles:
        design.query_cells(CLB_tile)
        # The tile has no cells if it doesn't get added to the dictionary for design cells
        if CLB_tile not in design.cells.keys():
            unmapped_CLB = CLB_tile
            break       
        # The tile has no cells if all slices in the dictionary for the tile are empty
        tile_slices = list(design.cells[CLB_tile].keys())
        if all([design.cells[CLB_tile][tile_slice] == {} for tile_slice in tile_slices]):
            unmapped_CLB = CLB_tile
            break

    # Error detection if someone decides to use a design where every single CLB is used
    if unmapped_CLB == 'NA':
        print('The provided design utilizes every single CLB tile, please use a less complex design')
        return []

    # Build tile object for the unused CLB tile
    tile_type_CLB = get_tile_type_name(unmapped_CLB)
    tile_obj_CLB = Tile(unmapped_CLB, tile_type_CLB, part_name)

    # Grab an arbitrary LUT bit from the unused tile
    resource_name = [rsrc for rsrc in tile_obj_CLB.resources.keys() if 'LUT' in rsrc][0]
    LUT_bit = tile_obj_CLB.resources[resource_name][0]

    # Convert from 2-number tile address to 3-number bitstream address
    CLB_tile_bit_addr = [unmapped_CLB, LUT_bit, 0]
    CLB_bitstream_addr = bit_bitstream_addr(CLB_tile_bit_addr, tilegrid_info)

    #--------------------------Repeat for INT tile--------------------------------#

    all_INT_tiles = {tile for tile in tilegrid_info.keys() if 'INT' in tile}
    unused_INT_tiles = all_INT_tiles - used_INT_tiles

    unmapped_INT = 'NA'
    # Iterate through INT tiles and find one with no nets routed through it
    for INT_tile in unused_INT_tiles:
        design.query_nets(INT_tile)
        if INT_tile not in design.nets.keys() or design.nets[INT_tile] == {}:
            unmapped_INT = INT_tile
            break

    # Error detection if someone decides to use a design where every single INT is used
    if unmapped_INT == 'NA':
        print('The provided design utilizes every single INT tile, please use a less complex design')
        return []

    # Build tile object for the unused INT tile
    tile_type_INT = get_tile_type_name(unmapped_INT)
    tile_obj_INT = Tile(unmapped_INT, tile_type_INT, part_name)

    # Get an arbitrary PIP bit from the unused tile
    pip_sink = next(iter(tile_obj_INT.pips.keys()))
    pip_src = next(iter(tile_obj_INT.pips[pip_sink].keys()))
    pip_bit = tile_obj_INT.pips[pip_sink][pip_src][0]

    # We only need the address of the bit, not whether it must be on/off
    if pip_bit[0] == '!':
        pip_bit = pip_bit[1:]

    INT_tile_bit_addr = [unmapped_INT, pip_bit, 0]
    INT_bitstream_addr = bit_bitstream_addr(INT_tile_bit_addr, tilegrid_info)

    # Return list with the errorless CLB and INT bits
    return [CLB_bitstream_addr[4:].replace('_', ' '), INT_bitstream_addr[4:].replace('_', ' ')]


def find_fault_bits(bitstream:str, dcp:str, run_bfat:bool, debug:bool):
    '''
        Generates a list of example fault bits for the given design
            Arguments: Bitstream for design, Vivado checkpoint of implemented design,
                       flag used to determine if files should be run through BFAT
            Returns: list of fault bits (.txt)
    '''

    t_start = time.perf_counter()

    # Get the high bits in the bitstream and the part name
    design_bits = get_high_bits(bitstream)
    debug_print(f'Parsed bitstream file:\t\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    # Create data structure of the design
    design_query = VivadoQuery(dcp)
    part_name = design_query.part
    debug_print(f'Created design query:\t\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    # Get all used INT tiles
    used_INT_tiles = design_query.get_used_INT_tiles()
    debug_print(f'Retrieved used INT tiles:\t\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    # Get the tilegrid information for the part
    tilegrid_info = parse_tilegrid(part_name)
    debug_print(f'Parsed tilegrid information:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)



    # Retrieve the fault bit groups for each of the test cases
    LUT_bit_group = get_bit_in_LUT(design_query, tilegrid_info, part_name)
    debug_print(f'Generated LUT bit group:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    open_bit_group = get_bit_for_open(design_query, tilegrid_info, used_INT_tiles, part_name)
    debug_print(f'Generated net open bit group:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    short_bit_group = get_bits_for_short(design_query, tilegrid_info, used_INT_tiles, design_bits, part_name, False)
    debug_print(f'Generated net short bit group:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    short_uc_node_bit_group = get_bits_for_short(design_query, tilegrid_info, used_INT_tiles, design_bits, part_name, True)
    debug_print(f'Generated net and UC node bit group:\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    undef_bit_group = get_undefined_bit(part_name)
    debug_print(f'Generated undefined bit group:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    errorless_bit_group = get_errorless_bits(design_query, tilegrid_info, used_INT_tiles, part_name)
    debug_print(f'Generated errorless bit group:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)



    # Compile all generated bit groups into one list
    bit_groups = [LUT_bit_group, open_bit_group, short_bit_group, short_uc_node_bit_group, undef_bit_group,
                  errorless_bit_group]
    bit_groups = [bit_group for bit_group in bit_groups if bit_group != []]
    
    # Get filename of bitstream without extension
    bitstream_filename = bitstream.split('/')[-1].split('.')[0]

    # Format the bit groups such that bits are now lists
    bit_groups_formatted = [[bit.split(' ') for bit in bit_group] for bit_group in bit_groups]

    # Convert bit groups to json format
    bit_groups_json = json.dumps(bit_groups_formatted, indent=4)

    # Determine the output file path
    fault_bits_file_path = os.getcwd() + '/' + bitstream_filename + '_sample_bits.json'

    # Open file to write fault bits to
    with open(fault_bits_file_path, 'w') as faults_file:
        faults_file.write(bit_groups_json)
    debug_print(f'Fault bit list file created:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)

    # If run flag was set, run the generated files through BFAT
    if run_bfat:
        bits_file_path = f'{bitstream}s'
        # Write design bits from bitread to a file so it can be passed in to bfat
        with open(bits_file_path, "w") as bits_file:
            for bit in design_bits:
                bits_file.write(bit + "\n")

        # Bash command to run BFAT
        run_cmd = ["python3", "bfat.py", bits_file_path, dcp, fault_bits_file_path, '-bf']

        # Run BFAT as a subprocess
        cmd_run = subprocess.run(run_cmd, capture_output=True, text=True)

        # Print out error traceback if error occured during the
        # run and print out the stdout if not
        if cmd_run.returncode != 0:
            print(cmd_run.stderr)
        else:
            print(cmd_run.stdout.strip())
        
        debug_print(f'Ran BFAT:\t\t{round(time.perf_counter()-t_start, 2)} sec', debug)


if __name__ == '__main__':
    import argparse

    # Create argparser and parse argument variables
    PARSER = argparse.ArgumentParser(description='Generates a fault bit list for the given design')
    PARSER.add_argument('bitstream', help='Bitstream file of the design for which '
                        + 'fault bits will be generated')
    PARSER.add_argument('dcp_file', help='Vivado checkpoint of the implemented design')
    PARSER.add_argument('-r', '--run', action='store_true', default='', help='Run the given design '
                        + 'files and generated fault bits through BFAT')
    PARSER.add_argument('-d', '--debug', action='store_true', default='', help='Give timing information')
    ARGS = PARSER.parse_args()

    find_fault_bits(ARGS.bitstream, ARGS.dcp_file, ARGS.run, ARGS.debug)