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
from lib.lut_config import LUT

class FaultBit(Bit):
    '''
        Stores the information for an individual fault bit
            Attributes:
                bit - the bit's name/bitstream address

                tile - the tile on the part that is influenced by the bit

                addr - the bit's address within the tile

                phys_functions - the bit's functions as found in the Project X-Ray database

                type - the type of Single Bit Upset (SBU) caused by the fault bit (driven high/low)

                design_name - the name of the resource in the design

                affected_rsrcs - the design resource(s) affected by the bit and its design failure

                affected_pips - the PIP(s) affected by the bit and its design failure

                failure - description of the design failure caused by the bit

                note - any special notes to be recorded and printed about the bit
    '''

    # Init from corresponding Bit object
    def __init__(self, bit:Bit, design_bits:list, frame_list:list, design:DesignQuery):
        # Copy input Bit attributes
        self.bit = bit.bit
        self.tile = bit.tile
        self.addr = bit.addr
        self.phys_fctns = bit.phys_fctns

        # Add FaultBit specific attributes
        # Select fault type based on the bit's presence in design bits
        if self.bit in design_bits:
            self.type = '1->0'
        # If the bit address could not be found, make sure that the bit has a valid frame address
        elif self.bit.split('_')[1] in frame_list:
            self.type = '0->1'
        else:
            self.type = 'NA'

        self.design_name = 'NA'
        self.affected_rsrcs = ['NA']
        self.affected_pips = ['NA']
        self.failure = 'Fault evaluation not yet supported for this bit'
        self.note = 'NA'

        # Update design name and affected resources with design data
        self.update_with_design_info(design)

    ##################################################
    #             Init Overload Functions            #
    ##################################################

    @classmethod
    def fromAddress(cls, bitstream_addr:str, frame_list:list, tilegrid:dict, tile_imgs:dict, design_bits:list, design:DesignQuery):
        '''
            Initialize FaultBit from bitstream address and part information
                Arguments: String of the bit's bitstream address, list of valid frames for the part,
                           dicts of the tilegrid and images of the part's tiles, a list of design
                           bits, and a query for the design
                Returns: Newly generated FaultBit object from the data provided
        '''

        bit = Bit(bitstream_addr, tilegrid, tile_imgs)
        return cls(bit, design_bits, frame_list, design)
    
    @classmethod
    def fromBit(cls, bit:Bit, frame_list:list, design_bits:list, design:DesignQuery):
        '''
            Initialize FaultBit from corresponding Bit object
                Arguments: Bit object to adapt, lists of valid frames for the part
                           and design bits, and a query for the design
                Returns: Newly generated FaultBit object from the data provided
        '''

        return cls(bit, design_bits, frame_list, design)

    def __str__(self):
        '''
            String representation of the Fault Bit
        '''

        out_str = f'{self.bit}\n'
        out_str += f'\tTile: {self.tile}\n'
        out_str += f'\tAddress: {self.addr}\n'
        out_str += f'\tPhysical Functions:{self.phys_fctns}\n'
        out_str += f'\tType: {self.type}\n'
        out_str += f'\tDesign Name: {self.design_name}\n'
        out_str += f'\tAffected Resources: {self.affected_rsrcs}\n'
        out_str += f'\tAffected PIPs: {self.affected_pips}\n'
        out_str += f'\tFailure: {self.failure}\n'
        out_str += f'\tNote: {self.note}\n'

        return out_str
        
    ##################################################
    #           Design Info Update Functions         #
    ##################################################
    
    def update_with_design_info(self, design:DesignQuery):
        '''
            Updates the FaultBit's stored data with the info from the given design
                Arguments: Query of the design
        '''

        # Separate fault bit value updating for undefined and defined bits
        if type(self.tile) == list:
            self.affected_rsrcs = possible_aff_rsrcs(self.tile, design)

        else:
            # Update fault bit values depending on the bit's tile
            if 'INT_L' in self.tile or 'INT_R' in self.tile:
                self.__get_design_info_INT(design)
            elif 'CLB' in self.tile:
                self.__get_design_info_CLB(design)
            elif 'IOI3' in self.tile:
                self.__get_design_info_IOI3(design)
            elif 'HCLK_L' in self.tile or 'HCLK_R' in self.tile:
                self.__get_design_info_HCLK(design)
            elif 'BRAM' in self.tile:
                self.__get_design_info_BRAM(design)
            elif 'DSP' in self.tile:
                self.__get_design_info_DSP(design)

            # Give default value for affected resources if no specific resources are found
            if not self.affected_rsrcs or (len(self.affected_rsrcs) <= 1 and 'NA' in self.affected_rsrcs):
                self.affected_rsrcs = ['No affected resources found']

    def __get_design_info_INT(self, design:DesignQuery):
        '''
            Helper function for design info updating for bits in INT tiles
                Arguments: Query of the design
        '''

        # Extract the name of the mux from the bit's physical function
        mux_name = self.phys_fctns[0][0].split(' ')[0]
        self.design_name = f'{self.tile}/{mux_name}'

        # Get the net that routes through the mux
        net = design.get_net(self.tile, mux_name)

        # Find the resources affected by the bit's net if it has one
        if net and net != 'NA':
            self.affected_rsrcs = design.get_affected_rsrcs(net, self.tile, mux_name)

    def __get_design_info_CLB(self, design:DesignQuery):
        '''
            Helper function for design info updating for bits in CLB tiles
                Arguments: Query of the design
        '''

        # For CLB bits with multiple functions, all functions just control one element.
        # Arbitrarily use the first function in the list.
        function = self.phys_fctns[0]
        
        # Get the full site address from the tile and site offset
        fctn_site = function[0]
        site_name = get_global_site(fctn_site, self.tile, design)

        # Attempt to find affected resources if the site exists and is used
        if site_name != 'NA':
            # Standard CLB fault bit value updating
            if len(function) == 3:
                fctn_bel = function[1]
                self.design_name = get_site_related_cells(self.tile, site_name, fctn_bel, design)
                self.affected_rsrcs = self.design_name.split(', ')

                # LUT configuration memory upset evaulation
                for cell in self.affected_rsrcs:
                    # Verify that the cell is a LUT
                    if cell != 'NA' and 'LUT' in fctn_bel:
                        # Add note header if it hasn't been added
                        if self.note == 'NA':
                            self.note = 'INIT string changes:\n'

                        lut = LUT(cell, design)
                        upset_bit_index = int(function[-1][-3:-1])
                        lut.simulate_upset([upset_bit_index])

                        # Add note about changes to the cell init string
                        if lut.cell_init_str != lut.cell_init_str_upset:
                            self.note += f'\t\t{cell}: {lut.cell_init_str} -> {lut.cell_init_str_upset}\n'
                        else:
                            self.note += f'\t\t{cell}: {lut.cell_init_str} (no change)\n'

                # Set failure message according to if a design resource was found or not
                if self.design_name == 'NA':
                    self.failure = f'No instanced resource found for this bit'
                else:
                    self.failure = f'{self.phys_fctns[0][-1]} bit altered for {self.design_name}.'

            # Special CLB fault bit value updating for functions that don't correspond to a BEL
            # which can have a cell mapped to it
            elif len(function) == 2:
                # Attempt to get affected resources within this site
                self.design_name = function[1]
                self.affected_rsrcs = design.get_CLB_affected_resources(site_name, function[1])

                # Set failure message according to if affected resources were found or not
                if not self.affected_rsrcs or 'NA' in self.affected_rsrcs:
                    self.failure = f'Not able to find any failures caused by this fault'
                else:
                    self.failure = f'{self.phys_fctns[0][-1]} bit altered for {self.design_name}'

    def __get_design_info_IOI3(self, design:DesignQuery):
        '''
            Helper function for design info updating for bits in IOI3 tiles
                Arguments: Query of the design
        '''

        # Choose the first function, since they all control one element
        function = self.phys_fctns[0]
        
        # Check if the function is actually a pip related to the clock routing
        if 'IOI' in function[0]:
            # Get the sink node of the pip and the net that uses that sink node
            sink_wire = function[0]
            sink_net = design.get_net(self.tile, sink_wire)

            # Trace the affected resources if there is a net at this node
            if sink_net and sink_net != 'NA':
                self.affected_rsrcs = design.get_affected_rsrcs(sink_net, self.tile, sink_wire)
                self.failure = f'Faults occurred in net: {sink_net}'
            else:
                self.failure = 'Not able to find any failures caused by this fault'

            # Revise bit fields to mimic the standard routing bit format
            self.phys_fctns = [[f'{sink_wire} 3-15 Routing Mux']]
            self.design_name = f'{self.tile}/{sink_wire}'

        # Standard bit function format
        else:
            # Get the full site address from the tile and site offset
            fctn_site = function[0]
            site_name = get_global_site(fctn_site, self.tile, design)

            # Attempt to find affected resources if the site exists and is used
            if site_name != 'NA':
                # Query cells in the tile and get all cells in the site
                design.query_cells(self.tile)
                cells = list(design.cells[self.tile][site_name].values())

                # Update bit fields if cells are found in the site
                if cells and '<LOCKED>' not in cells:
                    # Update design name and affected resources
                    self.design_name = ', '.join(cells)
                    self.affected_rsrcs = cells
                    self.failure = f'Above function(s) affected for {self.design_name}*'
                    
                    # Make a note about how the results may be inaccurate
                    self.note =  '* At the moment BFAT is not programmed to determine the exact'
                    self.note += ' effects of every RIO/LIO function -- these design resources'
                    self.note += ' are only a prediction based off of the site that the bit affects'
                else:
                    self.failure = 'No instanced resource found for this bit'
            
    def __get_design_info_HCLK(self, design:DesignQuery):
        '''
            Helper function for design info updating for bits in HCLK tiles
                Arguments: Query of the design
        '''

        # Analyze the first function, since they all control one element
        function = self.phys_fctns[0]

        # If this function is a pip, get downstream resources of the net
        if function[0] != 'ENABLE_BUFFER':
            # Get the sink node of the pip and the net that runs through the pip
            sink_wire = function[0]
            sink_net = design.get_net(self.tile, sink_wire)

            # Trace the affected resources if there is a net at this node
            if sink_net and sink_net != 'NA':
                self.affected_rsrcs = design.get_affected_rsrcs(sink_net, self.tile, sink_wire)
                self.failure = f'Faults occurred in net: {sink_net}'
            else:
                self.failure = 'Not able to find any failures caused by this fault'

            # Revise bit fields to mimic the standard routing bit format
            self.phys_fctns = [[f'{sink_wire} 2-16 Routing Mux']]
            self.design_name = f'{self.tile}/{sink_wire}'

        # Special handling for ENABLE_BUFFER bits
        else:
            # Get the buffer input wire
            src_wire = function[1]

            # Find the wire index number in the source's string
            for char in src_wire:
                if char.isnumeric():
                    first_digit_index = src_wire.find(char)
                    break
            src_wire_index = int(src_wire[first_digit_index:])

            # Determine the buffer sink used from the source depending on the tile
            if 'HCLK_L' in self.tile:
                # Sink wire index is 8 less than the source wire index
                sink_wire = f'HCLK_CK_INOUT_L{src_wire_index - 8}'
            elif 'HCLK_R' in self.tile:
                # Sink wire index is equal to the source wire index
                sink_wire = f'HCLK_CK_INOUT_R{src_wire_index}'

            sink_net = design.get_net(self.tile, sink_wire)

            # Trace the affected resources if there is a net at this node
            if sink_net and sink_net != 'NA':
                self.affected_rsrcs = design.get_affected_rsrcs(sink_net, self.tile, sink_wire)
                self.failure = f'Faults occurred in net: {sink_net}'
            else:
                self.failure = 'Not able to find any failures caused by this fault'

            # Revise bit fields to mimic the standard routing bit format
            self.phys_fctns = [[f'{sink_wire} Buffer']]
            self.design_name = f'{self.tile}/{sink_wire}'
            self.affected_pips = [f'{src_wire}->>{sink_wire}']

    def __get_design_info_BRAM(self, design:DesignQuery):
        '''
            Helper function for design info updating for bits in BRAM tiles
                Arguments: Query of the design
        '''

        # Analyze the first function, since they all control one element
        function = self.phys_fctns[0]

        # Check if the function actually controls a routing pip
        if 'ADDRARDADDRL' in function[0] or 'ADDRBWRADDRL' in function[0]:
            # Get the sink node of the pip and the net that uses that sink node
            sink_wire = function[0]
            sink_net = design.get_net(self.tile, sink_wire)

            # Trace the affected resources if there is a net at this node
            if sink_net and sink_net != 'NA':
                self.affected_rsrcs = design.get_affected_rsrcs(sink_net, self.tile, sink_wire)
                self.failure = f'Faults occurred in net: {sink_net}'
            else:
                self.failure = 'Not able to find any failures caused by this fault'

            # Revise bit fields to mimic the standard routing bit format
            self.phys_fctns = [[f'{sink_wire} 3-3 Routing Mux']]
            self.design_name = f'{self.tile}/{sink_wire}'

        # Standard BRAM bit evaluation for when a site is specified
        elif 'RAMB' in function[0]:
            # Though the implemented design displays two RAMB18s and one RAMB36,
            # this is inaccurate. The RAMB36 is actually just the two RAMB18s
            # cascaded together.
            
            # So, if a function specifies a RAMB18 but a RAMB36 is instanced and
            # not a RAMB18, the RAMB36 is still affected since they use the same
            # physical resource. 

            design.query_cells(self.tile)
            site_name = 'NA'

            # Check if the RAMB36 is instanced when a RAMB18 site is given
            if 'RAMB18' in function[0]:
                # Look for the RAMB36 site
                for site in design.cells[self.tile]:
                    # If the RAMB36 has instanced cells, this is the affected site
                    if 'RAMB36' in site and list(design.cells[self.tile][site].values()):
                        site_name = site
            
            # If not instanced RAMB36 was found, use the given RAMB18 site
            if site_name == 'NA':
                site_name = get_global_site(function[0], self.tile, design)

            # Attempt to find affected resources if the site exists and is used
            if site_name != 'NA':
                # Get the cells in the site (should only be one)
                cells = list(design.cells[self.tile][site_name].values())

                # Update bit fields if cells are found in the site
                if cells:
                    # Update design name and affected resources
                    self.design_name = ', '.join(cells)
                    self.affected_rsrcs = cells
                    self.failure = f'Above function(s) affected for {self.design_name}'
                else:
                    self.failure = 'No instanced resource found for this bit'

        # If the site is not specified, assume all RAMBs are affected
        else:
            tile_cells = []
            design.query_cells(self.tile)

            # Retrieve all cells in the tile
            for site_bels in design.cells[self.tile].values():
                # Skip site iteration if the site has no bels with a cell
                if 'None' in site_bels:
                    continue
                # Get the cell for each of the bels
                for cell in site_bels.values():
                    tile_cells.append(cell)
            
            # Update bit attributes with the found information
            if tile_cells:
                self.design_name = ', '.join(tile_cells)
                self.affected_rsrcs = tile_cells
                self.failure = f'Above function(s) affected for {self.design_name}'
            else:
                self.failure = 'No instanced resource found for this bit'

    def __get_design_info_DSP(self, design:DesignQuery):
        '''
            Helper function for design info updating for bits in DSP tiles
                Arguments: Query of the design
        '''

        # Analyze the first function, since they all control one element
        function = self.phys_fctns[0]      

        # Check if the function actually controls a routing pip
        if 'DSP_0' in function[0] or 'DSP_1' in function[0]:
            # Get the sink node of the pip and the net that uses that sink node
            sink_wire = function[0]
            sink_net = design.get_net(self.tile, sink_wire)

            # Trace the affected resources if there is a net at this node
            if sink_net and sink_net != 'NA':
                self.affected_rsrcs = design.get_affected_rsrcs(sink_net, self.tile, sink_wire)
                self.failure = f'Faults occurred in net: {sink_net}'
            else:
                self.failure = 'Not able to find any failures caused by this fault'

            # Revise bit fields to mimic the standard routing bit format
            self.phys_fctns = [[f'{sink_wire} Routing Mux']]
            self.design_name = f'{self.tile}/{sink_wire}'

        # Standard BRAM bit evaluation
        else:
            # Determine the affected site from the function
            site_offset = function[1][-1]
            site_name = get_global_site(f'DSP48_Y{site_offset}', self.tile, design)

            # Attempt to find affected resources if the site exists
            if site_name != 'NA':
                # Query cells in the tile and get all cells in the site
                design.query_cells(self.tile)
                cells = list(design.cells[self.tile][site_name].values())

                # Update bit fields if cells are found in the site
                if cells:
                    # Update design name and affected resources
                    self.design_name = ', '.join(cells)
                    self.affected_rsrcs = cells
                    self.failure = f'Above function(s) affected for {self.design_name}*'
                else:
                    self.failure = 'No instanced resource found for this bit'

##################################################
#          Bit Group Analysis Functions          #
##################################################

def analyze_bit_group(group_bits:list, frame_list:list, tilegrid:dict, tile_imgs:dict, design_bits:list, design:DesignQuery):
    '''
        Analyzes the fault bits in the provided bit group in their part and design
            Arguments: List of fault bits to be analyzed, list of valid frames for the part,
                       dicts of the part's tilegrid and tile images, list of the design bits,
                       and a query for the design's data
            Returns: Dict of the updated FaultBit objects after analysis
    '''

    fault_bits = {}
    int_tiles = {}

    # Generate FaultBit object for each bit in group and organize by tile
    for gb in group_bits:
        bitstream_addr = 'bit_' + '_'.join(gb)
        fb = FaultBit.fromAddress(bitstream_addr, frame_list, tilegrid, tile_imgs, design_bits, design)

        # Add any fault bits for INT tiles a dictionary under its tile
        if 'INT_L' in fb.tile or 'INT_R' in fb.tile:
            # Create a new entry for tile if needed and add new bit to the tile's entry
            try:
                int_tiles[fb.tile].append(fb)
            except KeyError:
                int_tiles[fb.tile] = []
                int_tiles[fb.tile].append(fb)
        
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
            mux_name = tb.phys_fctns[0][0].split(' ')[0]
            affected_muxes.add(mux_name)

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
        possible_rsrcs[tile] = {}
        design.query_cells(tile)
        
        # Verify that there are cells in the tile
        if tile not in design.cells:
            continue

        # Get all cells in the tile
        for site, site_bels in design.cells[tile].items():
            # Skip site iteration if the site has no bels with a cell
            if 'None' in site_bels:
                continue
            # Get the cell for each of the bels
            for bel, cell in site_bels.items():
                possible_rsrcs[tile][f'{site}/{bel}'] = cell

    return possible_rsrcs

##################################################
#          Design Name Helper Functions          #
##################################################

def get_global_site(local_site:str, tile:str, design:DesignQuery):
    '''
        Converts a site name which is offset from the tile address to one which can
        be interpreted independent of the tile offset (if that site is used)
            Arguments: String of site name from Project X-Ray database, string of tile name,
                       design query object
            Returns: String of the converted site name 
    '''

    # Separate and identify the resource's root and offset if possible
    try:
        site_root, site_offset = local_site.split('_')
    except ValueError:
        site_root = local_site
        site_offset = 'NA'

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

        # Check for a matching site based off of the Y offset
        if 'Y' in site_offset:
            # Set the site's y offset
            if '1' in site_offset:
                y_off = 1
            else:
                y_off = 0

            # Sort the sites by their y address and return the one that matches
            # the given offset
            sites = sorted(sites, key=lambda s: int(s[(s.find('Y') + 1):]))
            return sites[y_off]

        # Check for a matching site based off of the X offset
        elif 'X' in site_offset:
            # Set the site's y offset
            if '1' in site_offset:
                x_off = 1
            else:
                x_off = 0
            
            # Sort the sites by their y address and return the one that matches
            # the given offset
            sites = sorted(sites, key=lambda s: int(s[(s.find('X') + 1):s.find('Y')]))
            return sites[x_off]

        # Handling for if no offset is given
        elif len(sites) == 1:
            return sites[0]

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
            if mux in bit.phys_fctns[0][0]:
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
    if sink_nd in tile.pseudo_pips:
        # Iterate through each source node of the current sink node in the special pips dictionary
        for src_nd in tile.pseudo_pips[sink_nd]:
            # If the pip is marked as "default", make sure all config bits for the mux are off
            if tile.pseudo_pips[sink_nd][src_nd] == 'default':
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
