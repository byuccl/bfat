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
    bit_definitions.py
    BYU Configurable Computing Lab (CCL): BFAT project 2021-2022

    Supplementary python file for BFAT functions for defining individual
    bits in the bitstream and their corresponding roles/functions
'''

import copy
from lib.tile import Tile
from lib.design_query import DesignQuery

class FaultBit:
    '''
        Stores the information regarding a given fault bit
            Attributes:
                bit - the bit's name/bitstream address

                tile - the tile on the part that is influenced by the bit

                addr - the bit's address within the tile

                resource - the physical resource influenced by the bit

                design_name - the name of the resource in the design

                function - the function/role of the bit in the resource

                type - the type of Single Bit Upset (SBU) caused by the fault bit (driven high/low)

                fault - description of the fault in the design caused by the bit

                affected_rsrcs - the design resources affected by this bit and the fault it causes
    '''

    def __init__(self, bit_name):
        # Define and set default values for each class attribute
        self.bit = bit_name
        self.tile = 'NA'
        self.addr = 'NA'
        self.resource = 'NA'
        self.design_name = 'NA'
        self.function = 'NA'
        self.type = 'NA'
        self.fault = 'fault evaluation not yet supported for this bit'
        self.affected_rsrcs = ['NA']
        self.affected_pips = ['NA']

##################################################
#       Functions for Defining Fault Bits        #
##################################################

def def_fault_bits(bit_groups:dict, tilegrid:dict, tile_imgs:dict, design_bits:list, design:DesignQuery):
    '''
        Defines given fault bits in each bit group
            Arguments: Bit group information, dict of the part's tilegrid and the tile images,
                       a list of design bits, and a query for the design's data
            Returns: Dict storing the results of the fault bit evaluation
    '''

    fault_bits = {}

    # Iterate through each bit group
    for bit_group in bit_groups:
        int_tiles = {}
        # Get the information on each fault bit in the current bit group
        for fault_bit in bit_groups[bit_group]:
            # Create a new FaultBit object for the current fault bit
            bit_name = f'bit_{fault_bit[0]}_{fault_bit[1]}_{fault_bit[2]}'
            new_bit = FaultBit(bit_name)

            # Get the tile address and all of the potential tiles based on the bit's frame
            tile_addr, bit_potential_tiles = bit_tile_addr(fault_bit, tilegrid, tile_imgs)            

            # Set the basic fault bit values based on the converted bit address if possible
            if tile_addr:
                new_bit = set_fault_bit_values(new_bit, tile_addr, tile_imgs, design_bits, design)
            # If a tile address could not be found, set bit tile to be all potential tiles found
            else:
                new_bit.affected_rsrcs = possible_aff_rsrcs(new_bit, bit_potential_tiles, design)

            # Add any fault bits for INT tiles a dictionary under its tile
            if 'INT_L' in new_bit.tile or 'INT_R' in new_bit.tile:
                # Create a new entry for tile if needed and add new bit to the tile's entry
                try:
                    int_tiles[new_bit.tile].append(new_bit)
                except KeyError:
                    int_tiles[new_bit.tile] = []
                    int_tiles[new_bit.tile].append(new_bit)

            # Set the bit's fault description for CLB tiles
            if 'CLB' in new_bit.tile:
                # Set CLB bit's description based on if an instanced cell is found for it
                if new_bit.design_name == 'NA':
                    new_bit.fault = 'No instanced resource found for this bit'
                else:
                    new_bit.fault = f'{new_bit.function} bit altered for {new_bit.design_name}'

            # Add the new bit to the collection of fault bits
            fault_bits[new_bit.bit] = copy.deepcopy(new_bit)
            del new_bit

        # Evaluate the faults occurring in each affected INT tile
        for tile in int_tiles:
            tile_obj = copy.deepcopy(tile_imgs[tile[0:tile.find('_X')]])
            tile_obj.name = tile
            affected_muxes = set()

            # Add each affected routing mux to a list
            for f_bit in int_tiles[tile]:
                affected_muxes.add(f_bit.resource.split(' ')[0])

            # Set config bits in each routing mux to their values from the design
            for mux in affected_muxes:
                tile_obj = set_mux_config(tile_obj, mux, tilegrid, design_bits)

            # Evaluate fault errors in current tile
            tile_report = eval_INT_tile(tile_obj, affected_muxes, int_tiles, design_bits, tilegrid, design)

            # Set corresponding fault descriptions & affected pips of each of the tile's fault bits
            for tile_fbit in tile_report:
                fault_bits[tile_fbit].fault, fault_bits[tile_fbit].affected_pips = tile_report[tile_fbit]

            del tile_obj

    fault_report = {}

    # Generate fault report with data from fault bit definitions
    for bit_group, group_bits in bit_groups.items():
        fault_report[bit_group] = {}

        # Add each fault bit in the bit group and its stored data to the fault report
        for fault_bit in group_bits:
            fbit_name = f'bit_{fault_bit[0]}_{fault_bit[1]}_{fault_bit[2]}'
            fbit = fault_bits[fbit_name]
            fault_report[bit_group][fbit_name] = [fbit.tile, fbit.resource, fbit.function, 
                                              fbit.design_name, fbit.type, fbit.fault,
                                              fbit.affected_rsrcs, fbit.affected_pips]

    return fault_report

def possible_aff_rsrcs(bit:FaultBit, potential_tiles:list, design:DesignQuery):
    '''
        Gets all design resources (cells) in each of the potential tiles for the
        given undefined bit
            Arguments: FaultBit object, list of potential tiles for the bit, design
                       query object
            Returns: dict with all cells in each potential tile
    '''

    possible_rsrcs = {}

    # Get all cells in each of the tiles
    for tile in potential_tiles:
        possible_rsrcs[tile] = []
        design.query_cells(tile)
        
        # Verify that there are cells in the tile
        if tile not in design.cells:
            continue

        # Get all cells in the tile
        for site_bels in design.cells[tile].values():
            # Skip site iteration if the site has no bels with a cell
            if 'None' in site_bels:
                continue
            # Get the cell for each of the bels
            for cell in site_bels.values():
                possible_rsrcs[tile].append(cell)

    return possible_rsrcs

def set_fault_bit_values(bit:FaultBit, tile_addr:list, tile_imgs:dict, design_bits:list, design:DesignQuery):
    '''
        Evaluates a fault bit and all the surrounding information to set its values except
        for its description. Takes in the fault_bit and returns an updated version of it.
            Arguments: FaultBit object, list of converted bit info, dict of tile images,
                       list of design bits, and a query for the design's data
            Returns: Updated fault bit object
    '''

    bit.tile, bit.addr, bus_val = tile_addr
    bit.resource, bit.function = associate_bit(tile_imgs, bit.tile[0:bit.tile.find('_X')], bit.addr, bus_val)

    # Set the fault change depending on if the bit is included in the design bits
    if bit.bit in design_bits:
        bit.type = '1->0'
    else:
        bit.type = '0->1'

    # Separate evaluation of fault values for bits from INT tiles and bits from other tiles
    if 'INT_L' in bit.tile or 'INT_R' in bit.tile:
        mux_name = bit.resource.split(' ')[0]
        bit.design_name = f'{bit.tile}/{mux_name}'
        net = design.get_net(bit.tile, mux_name)

        # Find the resources affected by the bit's net if it has one
        if net and net != 'NA':
            bit.affected_rsrcs = design.get_affected_rsrcs(net, bit.tile, mux_name)
        else:
            bit.affected_rsrcs = ['No affected resources found']
    # Special evaluation of CLB bits that do not correspond to BELs which can have cells
    elif 'CLB' in bit.tile and '.' not in bit.resource:
        site_name = get_global_site(bit.resource, bit.tile, design)
        bit.affected_rsrcs = design.get_CLB_affected_resources(site_name, bit.function)

        bit.resource = f'{site_name}.{bit.function}'
        bit.function = 'Configuration'

        if bit.affected_rsrcs:
            bit.design_name = bit.resource.split('.')[1]

    else:
        # Get the site and bel name from the resource
        rsrc_elements = bit.resource.split('.')
        rsrc_site = rsrc_elements[0]
        rsrc_bel = rsrc_elements[-1]

        # Get the full site address from the tile and the site offset
        site_name = get_global_site(rsrc_site, bit.tile, design)
        
        # Find the cell within the site that matches the bit's bel
        if site_name != 'NA':
            bit.design_name = get_site_related_cells(bit.tile, site_name, rsrc_bel, design)
            bit.affected_rsrcs = [bit.design_name]

    # Give default value for affected resources if no specific resources are found
    if not bit.affected_rsrcs or (len(bit.affected_rsrcs) <= 1 and 'NA' in bit.affected_rsrcs):
        bit.affected_rsrcs = ['No affected resources found']
    
    return bit

def associate_bit(tiles:dict, tile_name:str, addr:str, bus_val:int):
    '''
        Associates the given bit with its tile, resources, and function if available.
            Arguments: Dict of tiles in the design, string of the bit's tile, the
                       bit's address in the tile, and int corresponding to the bit's bus
            Returns: Strings of the bit's resource and its function within that resource
    '''

    rsrc = 'NA'
    fctn = 'NA'

    # Separate association of bits for INT tiles from bits from other tiles
    if 'INT_L' in tile_name or 'INT_R' in tile_name:
        # Check each routing mux in the tile for the given bit
        for mux in tiles[tile_name].resources:
            # Identify if the bit is in the row bits or column bits for the routing mux
            if addr in tiles[tile_name].resources[mux].row_bits:
                rsrc = f'{mux} {tiles[tile_name].resources[mux].mux_type} Routing Mux'
                fctn = 'Row Bit'
                break
            elif addr in tiles[tile_name].resources[mux].col_bits:
                rsrc = f'{mux} {tiles[tile_name].resources[mux].mux_type} Routing Mux'
                fctn = 'Column Bit'
                break

    # Separate association of BRAM initialization bits and other bits
    elif 'BRAM' in tile_name and bus_val == 0:
        # Check if the bit matches the intialization bit of a BRAM resource
        for curr_rsrc, rsrc_bit in tiles[tile_name].init_resources.items():
            # If the bit matches, get the resource and function
            if rsrc_bit == addr:
                rsrc_elements = curr_rsrc.split('.')
                rsrc = '.'.join(rsrc_elements[:-1])
                fctn = rsrc_elements[-1]
                break
            
    else:
        # Search for the bit in each resource for the given tile
        for curr_rsrc, rsrc_bits in tiles[tile_name].resources.items():
            # Set rsrc and fctn if bit address is found in the resource bits
            if any([bit.replace('!', '') == addr for bit in rsrc_bits]):
                rsrc_elements = curr_rsrc.split('.')
                rsrc = '.'.join(rsrc_elements[:-1])
                fctn = rsrc_elements[-1]
                break

    # Handle duplicate bit function
    if fctn == 'NOCLKINV':
        fctn = 'CLKINV'

    return rsrc, fctn

def get_global_site(local_site:str, tile:str, design:DesignQuery):
    '''
        Converts a site name which is offset from the tile address to one which can
        be interpreted independent of the tile offset
            Arguments: String of site name from Project X-Ray database, string of tile name,
                       design query object
            Returns: String of the converted site name 
    '''
    # Separate and identify the resource's root and offset if possible
    try:
        site_root, site_offset = local_site.split('_')
    except ValueError:
        return 'NA'

    # Query design for sites in the tile if it isn't already loaded
    if tile not in design.cells:
        design.query_cells(tile)

    # Find the site if it is in a tile used in the design
    if tile in design.cells:
        # Simplify the root for SLICE* sites
        if 'SLICE' in site_root:
            site_root = 'SLICE'

        # Add all sites matching the root to a list
        sites = [site for site in design.cells[tile] if site_root in site]

        # Check for a matching site if any related sites are found
        if sites:
            # Identify matching sites depending on the site's X or Y offset from the tile
            if 'Y' in site_offset:
                # Get the site's y index
                tile_y = int(tile[tile.find('Y', tile.find('_X')) + 1:])

                # Set the site's y offset
                if '1' in site_offset:
                    y_off = 1
                else:
                    y_off = 0

                # Return the site which matches the y address
                for site in sites:
                    # Return site if the y address matches
                    if f'Y{tile_y + y_off}' in site:
                        return site
            
            else:
                # Return the site which matches the x offset from the tile
                for site in sites:
                    # Get the site's x index and offset
                    x_off = int(site[site.find('X') + 1:site.find('Y')]) % 2

                    # Return the site if its x offset matches its local site address
                    if 'X0' in site_offset and x_off == 0 or 'X1' in site_offset and x_off > 0:
                        return site
    return 'NA'

def get_site_related_cells(tile:str, site:str, bel:str, design:DesignQuery):
    '''
        Finds the related cell(s) from the design in the provided site and bel
            Arguments: Strings if the tile, site, and bel to get the cell for
                       and a query for the design's data
            Returns: String of the related cell(s)
    '''

    rel_cells = [c for b, c in design.cells[tile][site].items() if bel in [b, f'{b[0]}{b[2:]}']]

    # Return cell(s) found or 'NA' if none found
    if rel_cells:
        return ', '.join(rel_cells)
    else:
        return 'NA'

def set_mux_config(tile:Tile, mux:str, tilegrid:dict, design_bits:list):
    '''
        Sets the values of the mux's configuration bits to the values they are given
        in the provided design
            Arguments: Tile object to update, string of the mux to update, dict of the
                       part's tilegrid, and a list of the high bits in the design
            Returns: Updated Tile object
    '''

    # Set each config bit in each PIP in the current routing mux to its original value
    for src in tile.pips[mux]:
        # Get bit tile addresses used in the current pip
        pip_bits = [bit.replace('!', '') for bit in tile.pips[mux][src]]

        # Set each config bit in the PIP to its original value
        for pip_bit in pip_bits:
            # Convert the bit tile address to its bitstream address
            bitstream_addr = bit_bitstream_addr([tile.name, pip_bit, 0], tilegrid)

            # Set the current PIP bit's value to be 1 if it is in the design bits
            if bitstream_addr in design_bits:
                tile.change_bit(pip_bit, 1)

    return tile

def eval_INT_tile(tile:Tile, muxes:set, int_fault_bits:dict, design_bits:list, tilegrid:dict, design:DesignQuery):
    '''
        Evaluates a given tile associated with fault bits, determines any fault errors and
        the fault bits that caused them, and finds affected pips for the fault
            Arguments: Tile object for current tile, list of routing muxes affected by fault bits,
                       dicts of all fault bits in the tile, list of all high bits, the part's
                       tilegrid, and a query for the design data
            Returns: Dict storing fault bit information for the tile
    '''

    tile_report = {}
    init_cnctd_srcs = {}
    tile_fault_bits = int_fault_bits[tile.name]

    # Get the connected sources for each routing mux in the tile before bit upsets
    for mux in muxes:
        init_cnctd_srcs[mux] = get_connected_srcs(tile, mux, design)

    # Iterate through each of the fault bits and implement the bit upsets
    [tile.change_bit(fb.addr, {'1->0':0, '0->1':1}.get(fb.type)) for fb in tile_fault_bits]

    # Get the connected sources for each mux after bit upsets are applied and evalute changes made
    for mux in muxes:
        fault_cnctd_srcs = get_connected_srcs(tile, mux, design)

        open_srcs = set()
        short_srcs = set()

        # Add any initial sources that aren't connected post-faults to the open sources
        {open_srcs.add(src) for src in init_cnctd_srcs[mux] if src not in fault_cnctd_srcs}

        # Add sources connected post-fault to the short sources if multiple sources found
        if len(fault_cnctd_srcs) > 1:
            short_srcs = fault_cnctd_srcs

        # Get the affected pips for each fault bit related to the current mux
        mux_affected_pips = get_affected_pips(tile_fault_bits, mux, open_srcs, short_srcs, tile)

        # Generate fault message using the shorts and opens sources
        if open_srcs and short_srcs:
            opens_list = ', '.join(sorted(open_srcs))
            shorts_list = ', '.join(sorted(short_srcs))
            fault_desc = f'Opens created for net(s): {opens_list}; Shorts formed between net(s): {shorts_list}'
        elif open_srcs:
            opens_list = ', '.join(sorted(open_srcs))
            fault_desc = f'Opens created for net(s): {opens_list}'
        elif short_srcs:
            shorts_list = ', '.join(sorted(short_srcs))
            fault_desc = f'Shorts formed between net(s): {shorts_list}'
        else:
            fault_desc = ''
        
        # Substitute pin/node names with corresponding net names or set to default
        if fault_desc:
            fault_desc = sub_pins_with_nets(fault_desc, tile.name, int_fault_bits, tilegrid, design_bits, design)
        else:
            fault_desc = 'Not able to find any errors caused by this fault'

        # Apply the generated fault message to each related fault bit
        for bit in tile_fault_bits:
            # Check if each fault bit is associated with the current routing mux before
            # applying the fault message
            if mux in bit.resource:
                tile_report[bit.bit] = [fault_desc, mux_affected_pips[bit.bit]]

    return tile_report

def get_affected_pips(tile_fault_bits, mux:str, opened_srcs:set, shorted_srcs:set, gen_tile:Tile):
    '''
        Retrieves all affected pips in the given routing mux and whether they have been
        activated or deactivated.
            Arguments: List of fault bits in the tile, the affected routing mux, set of
                       opened sources, set of shorted sources, and the current Tile object
            Returns: Dict of the affected pips for each fault bit in the tile
    '''

    srcs_dict = {'deactivated' : opened_srcs, 'activated' : shorted_srcs}

    # Initialize affected pips with values already associated with the bits
    affected_pips = {f_bit.bit : f_bit.affected_pips for f_bit in tile_fault_bits}

    # Iterate through both source types (deactivated and activated)
    for src_type, srcs in srcs_dict.items():
        # Iterate through the sources in the source type
        for src in srcs:
            # Default seperator between source and sink in a pip
            separator = '->>'

            # Edge case for VCC and GND because they are not part of the tile pips dictionary
            if src == 'VCC_WIRE' or src == 'GND_WIRE':
                # Determine whether any of the fault bits are related to the routing mux
                for f_bit in tile_fault_bits:
                    # Check if the bit is either a row or column bit for the routing mux
                    is_row_bit = f_bit.addr in gen_tile.resources[mux].row_bits
                    is_col_bit = f_bit.addr in gen_tile.resources[mux].col_bits
                    
                    # If current bit is row or column bit for mux, this is an affected pip
                    if is_row_bit or is_col_bit:
                        # Add pip to the dictionary for the bit if a pip is found
                        if 'NA' in affected_pips[f_bit.bit]:
                            affected_pips[f_bit.bit] = [f'{src}{separator}{mux} ({src_type})']
                        else:
                            affected_pips[f_bit.bit].append(f'{src}{separator}{mux} ({src_type})')
                        
            else:
                # Get all related bits to the pip, independent of their required value
                pip_bits = [bit.replace('!', '') for bit in gen_tile.pips[mux][src]]

                # Determine which fault bits are part of the pip rule
                for f_bit in tile_fault_bits:
                    # Check that the bit's tile address is in the pip rule
                    if f_bit.addr in pip_bits:
                        # Determine if the pip is standard or bidirectional
                        if src in gen_tile.pips and mux in gen_tile.pips[src]:
                            separator = '<<->>'
                        
                        # Add pip to the dictionary for the bit if a pip is found
                        if 'NA' in affected_pips[f_bit.bit]:
                            affected_pips[f_bit.bit] = [f'{src}{separator}{mux} ({src_type})']
                        else:
                            affected_pips[f_bit.bit].append(f'{src}{separator}{mux} ({src_type})')

    return affected_pips

def get_connected_srcs(tile:Tile, sink_nd:str, design:DesignQuery):
    '''
        Evaluates routing mux config bits and routing rules to determine which source nodes
        are connected to the sink node.
            Arguments: Tile object with updated config bits, string of the sink node, and a
                       query for the design's data
            Returns: Set of all connected source nodes
    '''

    connected_srcs = set()

    # Iterate through each source node of the current routing mux
    for src_nd in tile.pips[sink_nd]:
        # Iterate through and check the bit configuration for each config bit
        connected = True
        for pip_bit in tile.pips[sink_nd][src_nd]:
            # Set connected flag to false if any config bit value does not match configuration
            if pip_bit[0] == '!' and tile.config_bits[pip_bit[1:]] != 0:
                connected = False
                break
            elif pip_bit[0] != '!' and tile.config_bits[pip_bit] != 1:
                connected = False
                break

        # If connected flag remains true add it to the list of connected sources
        if connected:
            connected_srcs.add(src_nd)

    # Check if the sink node actually connects to VCC or GND
    if sink_nd in tile.special_pips:
        # Iterate through each source node of the current sink node in the special pips dictionary
        for src_nd in tile.special_pips[sink_nd]:
            # If the pip is marked as "default", make sure all config bits for the mux are off
            if tile.special_pips[sink_nd][src_nd] == 'default':
                # Gather related bits to the mux in a set and make sure all bits are off
                col_bits = set(tile.resources[sink_nd].col_bits)
                row_bits = set(tile.resources[sink_nd].row_bits)
                mux_bits = col_bits.union(row_bits)
                all_bits_are_off = all([tile.config_bits[bit] == 0 for bit in mux_bits])
                
                # Check if sink and source nodes have the same net routed through them
                try:
                    src_has_net = sink_nd in design.nets[tile.name]
                    sink_has_net = src_nd in design.nets[tile.name]
                except KeyError:
                    src_has_net = False
                    sink_has_net = False

                if src_has_net and sink_has_net:
                    nodes_share_net = design.nets[tile.name][src_nd] == design.nets[tile.name][sink_nd]
                else:
                    nodes_share_net = False

                # If both flags are set, add source to connected sources
                if all_bits_are_off and nodes_share_net:
                    connected_srcs.add(src_nd)

    return connected_srcs

def sub_pins_with_nets(msg:str, tile:str, fault_bits:dict, tilegrid:dict, design_bits:list, design:DesignQuery):
    '''
        Replace each pin in the given fault message with its corresponding net(s)
            Arguments: Strings of message to be edited and tile name, dicts of the
                       fault bits and the part's tilegrid, list of the design bits,
                       and a query for the design's data
            Returns: String of edited fault message with net names instead of pin names
    '''

    msg_sections = msg.split('; ')
    sections = {}

    # Find pins and their corresponding nets for each section of the message
    for s in msg_sections:
        head, pins = s.split(': ')
        sec_nets = set()
        indirect_pins = set()

        # Get nets for pins from design
        for p in pins.split(', '):
            net = design.get_net(tile, p)

            # Add bit to section nets if found and to indirect pins of not
            if net != 'NA':
                sec_nets.add(net)
            else:
                indirect_pins.add(p)

        # Trace indirect pins for potential connected nets
        for idp in indirect_pins:
            conn_nets = find_connected_net(tile, idp, fault_bits, design_bits, tilegrid, design)
            
            # Remove any nets already found from the connected nets found
            rem_nets = {cn for cn in conn_nets if cn in sec_nets}
            conn_nets.difference_update(rem_nets)

            # Add found nets to section nets or add placeholder for pin if none are found
            if conn_nets:
                sec_nets.update(conn_nets)
            else:
                sec_nets.add(f'Unconnected Wire({idp})')

        # Create section entry for current message section
        sections[head] = ', '.join(sorted(sec_nets))

    return '; '.join([f'{h}: {sn}' for h, sn in sections.items()])

def find_connected_net(tile_name:str, node:str, fault_bits:dict, design_bits:list, tilegrid:dict, design:DesignQuery):
    '''
        Wrapper function for the recursive trace_node_connection. Evaluates post-fault design
        to find any nets that could be connected to the given node.
            Arguments: Strings of the initial tile and node, list of design bits, dicts of the
                       fault bits and the part's tilegrid, and a query for the design's data
            Returns: Set of strings of net connected to the requested node
    '''

    tile_collection = {}
    traced_nodes = set()
    found_nets = trace_node_connections(tile_name, node, fault_bits, design_bits,
                                        tilegrid, tile_collection, design, traced_nodes)

    return found_nets

def trace_node_connections(tile_name:str, node:str, fault_bits:dict, design_bits:list, tilegrid:dict, tile_collection:dict, design:DesignQuery, traced_nodes:set):
    '''
        Recursively traces back through the node connections and board wires to verify if any
        nets are connected to the given node after SBU's are applied to the design.
            Arguments: Strings of the tile and node; list of the design bits; dicts for the fault
                       bits, the part's tilegrid, and the tiles already evaluated for this trace;
                       and a query for the design's data, set of traced nodes
            Returns: Set of strings of nets connected to the requested node
    '''

    # Add the current node to the set of traced nodes
    traced_nodes.add(f'{tile_name}/{node}')

    # Create and load a new tile object and save it if it hasn't been run yet
    try:
        tile = tile_collection[tile_name]
    except KeyError:
        tile_type = tile_name[:tile_name.find('_X')]
        tile = Tile(tile_name, tile_type, design.part)

        # Update tile config bits
        [tile.change_bit(bit, 1) for bit in tile.config_bits if bit_bitstream_addr([tile_name, bit, 0], tilegrid) in design_bits]

        # Check if there are any fault bits in the current tile
        if tile_name in fault_bits:
            # Apply changes from each fault bit
            for f_bit in fault_bits[tile_name]:
                # Invert the value for the fault bit if it is in the tile
                if f_bit.addr in tile.config_bits:
                    tile.change_bit(f_bit.addr, {0:1, 1:0}.get(tile.config_bits[f_bit.addr]))

        tile.eval_connections()
        tile_collection[tile_name] = tile

    connected_nodes = []

    # Determine if the node is a sink or src in a tile connection and get its connected nodes
    if node in tile.cnxs:
        connected_nodes.extend(tile.cnxs[node])
    else:
        # Check each source node with connections for the given node
        for src in tile.cnxs:
            # Add each sink that isn't the original node to the list if the node is a sink
            if node in tile.cnxs[src]:
                [connected_nodes.append(sink) for sink in tile.cnxs[src] if sink != node]

    # Remove targeted node from list
    if node in connected_nodes:
        connected_nodes.remove(node)

    found_nets = set()
    # Check each connected node for an associated net
    for connected_node in connected_nodes:
        found_net = design.get_net(tile_name, connected_node)

        # Add the net if found, or rerun the trace on INT connections to the current node
        if found_net != 'NA':
            found_nets.add(found_net)
        else:
            wire_cnxs = design.get_wire_connections(tile_name, connected_node)
            non_int_cnxs = set()

            # Save non-INT connections in a separate set and remove each from the original list
            [non_int_cnxs.add(cnx) for cnx in wire_cnxs if 'INT' not in cnx]
            [wire_cnxs.remove(nic) for nic in non_int_cnxs]

            # Trace the node at the end of each wire connection
            for wire_cnx in wire_cnxs:
                wire_tile, wire_node = wire_cnx.split('/')

                # Do not trace previously traced nodes
                if wire_cnx not in traced_nodes:
                    found_nets.update(trace_node_connections(wire_tile, wire_node, fault_bits,
                                                            design_bits, tilegrid,
                                                            tile_collection, design, traced_nodes))

    return found_nets


####################################################
#   Functions for Conversion Between Bit Formats   #
####################################################

def bit_tile_addr(bitstream_addr:list, tilegrid:dict, tile_imgs:dict):
    '''
        Converts a bit's bitstream address to its tile and tile address
            Arguments: List of the bitstream address and dicts of the tilegrid and tile images
            Returns: 3-element list with strings of the bit's tile, tile address, and an int of the
                     tilegrid data index the bit's data is found at in its tile. Also returns the
                     list of potential bits from the frame address and word offset
    '''

    bit_tiles = {}                          # {tile : dataset index}
    bit_frame = int(bitstream_addr[0], 16)
    word_offset = int(bitstream_addr[1])
    bit_offset = int(bitstream_addr[2])

    # Iterate through the tiles from the tilegrid to find which ones can potentially have the bit
    for curr_tile, info in tilegrid.items():
        # Check each dataset for the current tile to see if the base address can match
        for i, baseaddr in enumerate(info['baseaddr']):
            # Check if the bit frame address is in the range for the current tile
            if bit_frame >= baseaddr and bit_frame <= baseaddr + (info['frames'][i] - 1):
                # If the word offset is within the range for the current tile, add it to the list
                if word_offset >= info['offset'][i] and word_offset <= info['offset'][i] + (info['words'][i] - 1):
                    bit_tiles[curr_tile] = i

    bit_tiles_list = list(bit_tiles.keys())

    # If any potential tiles are found check if they use the bit
    if bit_tiles:
        # Iterate through the potential tiles and check if they use the bit
        for bit_tile, i in bit_tiles.items():
            frame_addr = bit_frame - tilegrid[bit_tile]['baseaddr'][i]
            bit_addr = bit_offset + (32 * (word_offset - tilegrid[bit_tile]['offset'][i]))

            addr = '{:02}_{:02}'.format(frame_addr, bit_addr)
            ttp_name = bit_tile[:bit_tile.find('_X')]

            # Check if this is a BRAM initialization bit
            if 'BRAM' in ttp_name and i == 0 and addr in tile_imgs[ttp_name].init_bits:
                return [bit_tile, addr, i], bit_tiles_list

            # Check the tile archetype's config bits for the bit
            elif (addr in tile_imgs[ttp_name].config_bits):
                return [bit_tile, addr, i], bit_tiles_list
    return [], bit_tiles_list

def bit_bitstream_addr(tile_addr:list, tilegrid:dict):
    '''
        Converts a bit's tile and tile address into its bitstream address
            Arguments: 2-element list of strings of the bit's tile and tile address and a dict
                       of the part's tilegrid
            Returns: String of the bit's bitstream address (bit_<frame(0x)>_<word(int)>_<bit(int)>)
    '''

    # Convert the bit back to its original format if one is provided
    if tile_addr:
        tile, addr, data_index = tile_addr
        frame_offset, bit = addr.split('_')
        baseaddr = tilegrid[tile]['baseaddr'][data_index]
        word_offset = tilegrid[tile]['offset'][data_index]

        frame = baseaddr + int(frame_offset)

        bit = int(bit)
        word = word_offset + int(bit / 32)
        bit = bit % 32

        return 'bit_{:08x}_{:03}_{:02}'.format(frame, word, bit)
    return ''
