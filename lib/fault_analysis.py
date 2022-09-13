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
    fault_analysis.py
    BYU Configurable Computing Lab (CCL): BFAT project 2022

    Supplementary python file for BFAT functions for analyzing the design
    failures that occur due to fault bits
'''

import copy
from lib.define_bit import Bit, bit_bitstream_addr
from lib.design_query import DesignQuery
from lib.tile import Tile

class FaultBit(Bit):
    '''
        Stores the information for an individual fault bit
            Attributes:
                bit - the bit's name/bitstream address

                tile - the tile on the part that is influenced by the bit

                addr - the bit's address within the tile

                resource - the physical resource influenced by the bit

                function - the function/role of the bit in the resource

                type - the type of Single Bit Upset (SBU) caused by the fault bit (driven high/low)

                design_name - the name of the resource in the design

                affected_rsrcs - the design resource(s) affected by the bit and its design failure

                affected_pips - the PIP(s) affected by the bit and its design failure

                failure - description of the design failure caused by the bit
    '''

    # Init from corresponding Bit object
    def __init__(self, bit:Bit, design_bits:list, design:DesignQuery):
        # Copy input Bit attributes
        self.bit = bit.bit
        self.tile = bit.tile
        self.addr = bit.addr
        self.resource = bit.resource
        self.function = bit.function

        # Add FaultBit specific attributes
        # Select fault type based on the bit's presence in design bits
        if self.bit in design_bits:
            self.type = '1->0'
        else:
            self.type = '0->1'

        self.design_name = 'NA'
        self.affected_rsrcs = ['NA']
        self.affected_pips = ['NA']
        self.failure = 'fault evaluation not yet supported for this bit'

        # Update design name and affected resources with design data
        self.update_with_design_info(design)

    ##################################################
    #             Init Overload Functions            #
    ##################################################

    @classmethod
    def fromAddress(cls, bitstream_addr:str, tilegrid:dict, tile_imgs:dict, design_bits:list, design:DesignQuery):
        '''
            Initialize FaultBit from bitstream address and part information
                Arguments: String of the bit's bitstream address, dicts of the tilegrid
                           and images of the part's tiles, a list of design bits, and
                           a query for the design
                Returns: Newly generated FaultBit object from the data provided
        '''

        bit = Bit(bitstream_addr, tilegrid, tile_imgs)
        return cls(bit, design_bits, design)
    
    @classmethod
    def fromBit(cls, bit:Bit, design_bits:list, design:DesignQuery):
        '''
            Initialize FaultBit from corresponding Bit object
                Arguments: Bit object to adapt, list of design bits, and a query for the design
                Returns: Newly generated FaultBit object from the data provided
        '''

        return cls(bit, design_bits, design)

    def __str__(self):
        '''
            String representation of the Fault Bit
        '''

        out_str = f'{self.bit}\n'
        out_str += f'\tTile: {self.tile}\n'
        out_str += f'\tAddress: {self.addr}\n'
        out_str += f'\tResource: {self.resource}\n'
        out_str += f'\tFunction: {self.function}\n'
        out_str += f'\tType: {self.type}\n'
        out_str += f'\tDesign Name: {self.design_name}\n'
        out_str += f'\tAffected Resources: {self.affected_rsrcs}\n'
        out_str += f'\tAffected PIPs: {self.affected_pips}\n'
        out_str += f'\tFailure: {self.failure}'

        return out_str
    
    def update_with_design_info(self, design:DesignQuery):
        '''
            Updates the FaultBit's stored data with the info form the given design
                Arguments: Query of the design
        '''

        # Separate fault bit value updating for undefined and defined bits
        if type(self.tile) == list:
            self.affected_rsrcs = possible_aff_rsrcs(self.tile, design)

        else:
            # Update fault bit values for bits from INT tiles
            if 'INT_L' in self.tile or 'INT_R' in self.tile:
                mux_name = self.resource.split(' ')[0]
                self.design_name = f'{self.tile}/{mux_name}'
                net = design.get_net(self.tile, mux_name)

                # Find the resources affected by the bit's net if it has one
                if net and net != 'NA':
                    self.affected_rsrcs = design.get_affected_rsrcs(net, self.tile, mux_name)
                else:
                    self.affected_rsrcs = ['No affected resources found']

            # Update fault bit values for bits from CLB tiles
            elif 'CLB' in self.tile and '.' not in self.resource:
                site_name = get_global_site(self.resource, self.tile, design)

                # Attempt to get affected resources within this site if it is used
                if site_name != 'NA':
                    self.affected_rsrcs = design.get_CLB_affected_resources(site_name, self.function)

                # Revise bit object attributes
                self.resource = f'{self.resource}.{self.function}'
                self.function = 'Configuration'
                if self.affected_rsrcs and 'NA' not in self.affected_rsrcs:
                    self.design_name = self.resource.split('.')[1]
                else:
                    self.fault = 'Not able to find any errors'

            # Update fault bit values for all other defined fault bits
            else:
                # Get the site and bel name from the resource
                rsrc_elements = self.resource.split('.')
                rsrc_site = rsrc_elements[0]
                rsrc_bel = rsrc_elements[-1]

                # Get the full site address from the tile and the site offset
                site_name = get_global_site(rsrc_site, self.tile, design)
                
                # Find the cell within the site that matches the bit's bel
                if site_name != 'NA':
                    self.design_name = get_site_related_cells(self.tile, site_name, rsrc_bel, design)
                    self.affected_rsrcs = self.design_name.split(', ')

            # Give default value for affected resources if no specific resources are found
            if not self.affected_rsrcs or (len(self.affected_rsrcs) <= 1 and 'NA' in self.affected_rsrcs):
                self.affected_rsrcs = ['No affected resources found']

##################################################
#          Bit Group Analysus Functions          #
##################################################

def analyze_bit_group(group_bits:list, tilegrid:dict, tile_imgs:dict, design_bits:list, design:DesignQuery):
    '''
        Analyzes the fault bits in the provided bit group in their part and design
            Arguments: List of fault bits to be analyzed, dicts of the part's tilegrid and 
                       tile images, list of the design bits, and a query for the design's data
            Returns: Dict of the updated FaultBit objects after analysis
    '''

    fault_bits = {}
    int_tiles = {}

    # Generate FaultBit object for each bit in group and organize by tile
    for gb in group_bits:
        bitstream_addr = 'bit_' + '_'.join(gb)
        fb = FaultBit.fromAddress(bitstream_addr, tilegrid, tile_imgs, design_bits, design)

        # Add any fault bits for INT tiles a dictionary under its tile
        if 'INT_L' in fb.tile or 'INT_R' in fb.tile:
            # Create a new entry for tile if needed and add new bit to the tile's entry
            try:
                int_tiles[fb.tile].append(fb)
            except KeyError:
                int_tiles[fb.tile] = []
                int_tiles[fb.tile].append(fb)
        
        elif 'CLB' in fb.tile:
            # Set failure message according to if a design resource was found or not
            if fb.design_name == 'NA':
                fb.failure = f'No instanced resource found for this bit'
            else:
                fb.failure = f'{fb.function} bit altered for {fb.design_name}'
        
        # Add the bit to the collection of fault bits
        fault_bits[fb.bit] = copy.deepcopy(fb)
        del fb

    # Evaluate the fault bits in each tile affected by bit group
    for tile in int_tiles:
        tile_obj = copy.deepcopy(tile_imgs[tile[:tile.find('_X')]])
        tile_obj.name = tile
        affected_muxes = set()

        # Add each affected routing mux to a list
        for tb in int_tiles[tile]:
            affected_muxes.add(tb.resource.split(' ')[0])

        # Set config bits in each routing mux to their values from the design
        for mux in affected_muxes:
            tile_obj = set_mux_config(tile_obj, mux, tilegrid, design_bits)

        # Evaluate fault errors in current tile
        tile_report = eval_INT_tile(tile_obj, affected_muxes, int_tiles, design_bits, tilegrid, design)

        # Set corresponding fault descriptions & affected pips of each of the tile's fault bits
        for tb in tile_report:
            fault_bits[tb].failure, fault_bits[tb].affected_pips = tile_report[tb]

        del tile_obj
    
    return fault_bits

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

def possible_aff_rsrcs(potential_tiles:list, design:DesignQuery):
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

##################################################
#          Design Name Helper Functions          #
##################################################

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
        return ', '.join(sorted(rel_cells))
    else:
        return 'NA'

##################################################
#       INT Tile Fault Analysis Functions        #
##################################################

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

        # Determine the original source connected to the sink
        short_srcs_copy = short_srcs.copy()
        for src in short_srcs_copy:
            if src in init_cnctd_srcs[mux]:
                init_src = src + ' (initially connected)'
                short_srcs.remove(src)
                short_srcs.add(init_src)

        # Get the affected pips for each fault bit related to the current mux
        mux_affected_pips = get_affected_pips(tile_fault_bits, mux, open_srcs, short_srcs_copy, tile)

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
            fault_desc = 'Not able to find any failures caused by this fault'

        # Apply the generated fault message to each related fault bit
        for bit in tile_fault_bits:
            # Check if each fault bit is associated with the current routing mux before
            # applying the fault message
            if mux in bit.resource:
                tile_report[bit.bit] = [fault_desc, mux_affected_pips[bit.bit]]

    return tile_report

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
            pin = p.split()[0]
            is_init_cnctn = '(initially connected)' in p

            net = design.get_net(tile, pin)

            # Add bit to section nets if found and to indirect pins if not
            if net != 'NA' and is_init_cnctn:
                sec_nets.add(f'{net} (initially connected)')
            elif net != 'NA':
                sec_nets.add(net)
            else:
                indirect_pins.add(p)

        # Trace indirect pins for potential connected nets
        for idp in indirect_pins:
            conn_nets = find_connected_net(tile, idp, fault_bits, design_bits, tilegrid, design)
            
            # Remove any nets already found from the connected nets found
            rem_nets = {cn for cn in conn_nets if cn in sec_nets or f'{cn} (initially connected)' in sec_nets}
            conn_nets.difference_update(rem_nets)

            # Add found nets to section nets or add placeholder for pin if none are found
            if conn_nets:
                sec_nets.update(conn_nets)
            else:
                sec_nets.add(f'Unconnected Wire({idp})')

        # Create section entry for current message section
        sections[head] = ', '.join(sorted(sec_nets))

    return '; '.join([f'{h}: {sn}' for h, sn in sections.items()])

##################################################
#             Net Tracing Functions              #
##################################################

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
