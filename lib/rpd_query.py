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
    rpd_query.py
    BYU Configurable Computing Lab (CCL): BitInspector project 2022

    Supplementary python file for BitInspector functions for querying a design's
    dcp file for design info through Rapidwright
'''

import rapidwright
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.device import Wire
from lib.design_query import DesignQuery

class RpdQuery(DesignQuery):
    '''
        Design query through use of the rapidwright tool
            Arguments: String of the path to the design's dcp file

            Attributes:
                query - Rapidwright Design object to query the design's dcp file for design info

                part - Name of the part on which the design is implemented

                nets - Collection of the locations and name of nets in the design routing

                pips - Collection of the PIPs used for nets in the design routing

                cells - Collection of the location and name of cells in the design

                wires - Collection of the location, name, and connections of wires in the design
    '''

    # Class Constructor
    def __init__(self, dcp):
        super().__init__(dcp)
        print('')
        self.query = Design.readCheckpoint(dcp)
        print('')
        self.part = self.query.getPartName()
    
    #######################
    #   Design Querying   #
    #######################

    def query_nets(self, tile:str):
        '''
            Queries Rapidwright for the names and routing of the nets in requested tile
                Arguments: String of the tile to query
        '''

        nets = self.query.getNets()

        # Iterate through each net in the design
        for net in nets:
            net_name = str(net)

            # Iterate through each PIP Rapidwright can find for it
            for pip in net.getPIPs():
                # Check that it is a PIP from an INT tile
                pip_tile = str(pip.getTile())
                
                # Check that the current tile matches the requested tile
                if pip_tile == tile:
                    pip_str = str(pip)

                    # Determine the divider between the pins for the current PIP
                    div = ''
                    if '<<->>' in pip_str:
                        div = '<<->>'
                    elif '->>' in pip_str:
                        div = '->>'
                    else:
                        div = '->'

                    # Split the PIP string to get the sink and source pins of the pip
                    src_pin, sink_pin = pip_str.split('.')[1].split(div)

                    # Add entry for current tile in the stored net data if there isn't one yet
                    if tile not in self.nets:
                        self.nets[tile] = {}

                    # Add info to tile net mapping
                    self.nets[tile][src_pin] = net_name
                    self.nets[tile][sink_pin] = net_name
        
        self.tiles_queried_nets.add(tile)

    def query_pips(self, net:str):
        '''
            Queries Rapidwright for the names and routing of the nets in requested tile
                Arguments: String of the net to query
        '''

        nets = self.query.getNets()

        # Iterate through each net in the design
        for design_net in nets:
            net_name = str(design_net)

            # Check that the current net name matches the requested net
            if net_name == net:
                # Iterate through each PIP Rapidwright can find for it
                for pip in design_net.getPIPs():
                    pip_str = str(pip)

                    # Determine the divider between the pins for the current PIP
                    div = ''
                    if '<<->>' in pip_str:
                        div = '<<->>'
                    elif '->>' in pip_str:
                        div = '->>'
                    else:
                        div = '->'

                    # Check that it is a PIP from an INT tile
                    tile = str(pip.getTile())
                    src_pin, sink_pin = pip_str.split('.')[1].split(div)

                    # Add entry for current net to stored PIP data there isn't one yet
                    if net_name not in self.pips:
                        self.pips[net_name] = []
                    
                    # Add PIP information to the stored data
                    self.pips[net_name].append((f'{tile}/{src_pin}', f'{tile}/{sink_pin}'))

    def query_cells(self, tile:str):
        '''
            Queries Rapidwright for the cells in the requested tile
                Arguments: String of the tile to query
        '''

        # Get all sites in the tile
        tile_obj = self.query.getDevice().getTile(tile)
        sites = list(tile_obj.getSites())

        # Add each site and its cells to the stored data
        for site in sites:
            # Create an entry for the current tile if there isn't one
            if tile not in self.cells:
                self.cells[tile] = {}
            site_name = str(site.getName())
            self.cells[tile][site_name] = {}

            # Get siteInst object with design information from the site object
            site_inst = self.query.getSiteInstFromSite(site)

            # Verify that the site has a corresponding siteInst
            if site_inst:
                # Check each cell found in the site instance from Rapidwright and add the BEL
                # and cell name to its entry
                for cell in list(site_inst.getCells()):
                    bel = str(cell.getBELName())
                    self.cells[tile][site_name][bel] = str(cell.getName())


    def query_wires(self, tile:str):
        '''
            Queries Rapidwright for the requested wire and its connections
                Arguments: String of the tile to query
        '''
        
        device = self.query.getDevice()
        tile_obj = device.getTile(tile)

        # Check that Rapidwright can find the given tile
        if tile_obj:
            self.wires[tile] = {}
            tile_wires = list(tile_obj.getWireNames())

            # Iterate through the wires in the given tile
            for wire in tile_wires:
                connections = [Wire(tile_obj, wire)]
                connections += list(tile_obj.getWireConnections(wire))

                # Add the connections found to the wire structure if any are found
                if connections:
                    self.wires[tile][wire] = connections

    #################################
    #   Affected Resource Tracing   #
    #################################

    def trace_affected_resources(self, net:str, tile:str, wire:str, traced_nodes:set, affected_rsrcs:set):
        '''
            Recursively traces downstream through the net in the design from the provided
            tile and node.
                Arguments: String of the net to be traced, the current tile, and the current wire;
                           and sets of the current nodes traced and affected resources found
                Returns: Updated sets of the nodes traced and affected resources found after
                         tracing this node
        '''

        traced_nodes.add((tile, wire))
        wire_cnxs = self.get_wire_connections(tile, wire)

        # Iterate through each connection to the wire at the given node
        for cnx in wire_cnxs:
            cnx_name = f'{cnx.getTile().getName()}/{cnx.getWireName()}'

            net_obj = self.query.getNet(net)
            net_sink_pins = net_obj.getSinkPins()
            # Iterate through the Sink pins of the current net to check if we arrived at a site
            for pin in net_sink_pins:
                # Check if the current sink pin matches the current PIP sink
                pin_node_name = pin.getNodeFromPin().getName()
                if pin_node_name == cnx_name:
                    # This pin is a sink pin into a site
                    site_inst = pin.getSiteInst()

                    # Get connected cells that are forward from this site pin
                    connected_cells, _ = self.trace_cells(pin.getBELPin(), site_inst, set(), set())
                    for cell in connected_cells:
                        affected_rsrcs.add(cell)
                    break

            # Iterate through each PIP for the given net
            for pip in self.get_pips(net):
                # Call trace again on any connected sink pins
                if cnx_name == pip[0]:
                    new_tile, new_node = pip[1].split('/')

                    # Do not trace nodes that have already been traced
                    if (new_tile, new_node) not in traced_nodes:
                        affected_rsrcs, traced_nodes = self.trace_affected_resources(net, new_tile, new_node,
                                                                                     traced_nodes, affected_rsrcs)

        return affected_rsrcs, traced_nodes

    def trace_cells(self, init_bel_pin, site_inst, cells:set, traced_bels:set):
        '''
            Recursive function which traces forward through a site from a BEL pin looking for cells
                Arguments: The starting BEL pin, site instance object, set of found cells
                Returns: Set of found cells, and a set of the bels already traced
        '''

        traced_bels.add(init_bel_pin.getBEL().getName())

        # Iterate through forward BEL pins from the current source pin
        for bel_pin in init_bel_pin.getSiteConns():
            bel = bel_pin.getBEL()
            bel_name = bel.getName()
            bel_class = bel.getBELClass().toString()

            # If we have reached a site output port, check if the net enters the site again later
            if bel_class == 'PORT':
                site_pin = site_inst.getSitePinInst(bel_name)
                
                # Check if this is a used site pin, if not then exit
                if site_pin:
                    net_sink_pins = site_pin.getNet().getSinkPins()
                else:
                    continue

                # If any of the site's pins match any of the net's sink pins, get the cells of that sink pin
                for net_sink_pin in net_sink_pins:
                    if net_sink_pin in site_inst.getSitePinInsts():
                        sink_bel_pin = net_sink_pin.getBELPin()
                        # Trace the net sink's bel pin if its BEL has not yet been traced
                        if sink_bel_pin.getBEL().getName() not in traced_bels:
                            cells, traced_bels = self.trace_cells(sink_bel_pin, site_inst, cells, traced_bels)

            # If BEL pin connects to a routing BEL, trace through the routing BEL
            elif bel_class == 'RBEL':
                pip = site_inst.getUsedSitePIP(bel_name)
                # Trace forward from the routing BEL if the current BEL pin is part of a used pip
                if pip and pip.getInputPin() == bel_pin:
                    # Trace forward from routing BEL if the forward BEL has not yet be traced
                    if pip.getOutputPin().getBEL().getName() not in traced_bels:
                        cells, traced_bels = self.trace_cells(pip.getOutputPin(), site_inst, cells, traced_bels)

            # If BEL pin is an input to a regular BEL, check if there is a cell mapped to the BEL
            else:
                cell = site_inst.getCell(bel_name)
                # Add the cell to the affected cells if the BEL pin matches a cell pin
                if cell and cell.getLogicalPinMapping(bel_pin.getName()):
                    cell_name = str(cell.getName())
                    cells.add(cell_name)

                    # Get any forward cells from the output pins of this BEL
                    for out_pin in [pin for pin in bel.getPins() if pin.isOutput()]:
                        cells, traced_bels = self.trace_cells(out_pin, site_inst, cells, traced_bels)
        
        return cells, traced_bels

    def get_CLB_affected_resources(self, site:str, function:str):
        '''
            Handles affected resource tracing for certain special cases in CLB tiles
                Arguments: strings of the tile, site, and function of the bit
                Returns: list of affected resources
        '''

        affected_rsrcs = set()
        site_inst = self.query.getSiteInst(site)

        # Define constants for the three edge case types to handle
        ROUTING_BELS = ['CLKINV', 'NOCLKINV', 'CEUSEDMUX', 'SRUSEDMUX']
        FF_CONTROL = ['FFSYNC', 'LATCH']
        LUTRAM_CONTROL = ['WA7USED', 'WA8USED']

        # Resource tracing for the routing bels
        if function in ROUTING_BELS:
            # Assign a routing bel based on the function
            if function == 'NOCLKINV':
                routing_bel = 'CLKINV'
            else:
                routing_bel = function

            bel_pip = site_inst.getUsedSitePIP(routing_bel)
            # Verify that this is a used routing bel
            if bel_pip:
                # Get forward cells from this bel
                output_bel_pin = bel_pip.getOutputPin()
                affected_rsrcs, _ = self.trace_cells(output_bel_pin, site_inst, affected_rsrcs, set())

        # Resource fetching for flip-flop control bits
        elif function in FF_CONTROL:
            # Get all resources mapped to flip-flops
            ff_cells = [cell for cell in site_inst.getCells() if 'FF' in cell.getBEL().toString()]
            affected_rsrcs = {str(cell.getName()) for cell in ff_cells}
        
        # Resource fetching for LUTRAM control bits
        elif function in LUTRAM_CONTROL:
            # Get all resources mapped to LUTRAMs
            lut_cells = [cell for cell in site_inst.getCells() if 'LUT' in cell.getBEL().toString()]
            affected_rsrcs = {str(cell.getName()) for cell in lut_cells}

        # Unrecognized case
        else:
            print(f'Unrecognized CLB bit function: {function}')

        return list(affected_rsrcs)
            

    ##################################
    #   find_fault_bits.py Helpers   #
    ##################################

    def get_CLB_tiles(self, used:bool):
        '''
            Gets all CLB tiles that have either used or unused sites
                Arguments: bool to determine whether used or unused tiles should be gathered
                Returns: set of tile names
        '''

        # Get the device used to implement the design
        device = self.query.getDevice()
        # Get all of the CLB tiles from the device
        clb_tiles = {tile for tile in device.getAllTiles() if 'CLB' in str(tile)}

        matching_clb_tiles = set()
        # Check each CLB tile to see if it matches the usage condition
        for clb_tile in clb_tiles:
            # Add the current CLB tile to the set if it matches the usage condition
            if any([self.query.isSiteUsed(site) == used for site in clb_tile.getSites()]):
                matching_clb_tiles.add(str(clb_tile))

        return matching_clb_tiles

    def get_used_INT_tiles(self):
        '''
            Gets all INT tiles with utilized switchboxes
                Returns: set of tile names
        '''

        tiles_used = set()
        nets = self.query.getNets()

        # Update set of tiles used with the pips used in each net
        for net in nets:
            # Add and INT tiles found for PIPs used by the current net
            for pip in net.getPIPs():
                pip_tile = str(pip.getTile())

                # Check that the pip's tile is and INT tile
                if 'INT' in pip_tile and '_INT_' not in pip_tile and 'INTERFACE' not in pip_tile:
                    tiles_used.add(pip_tile)

        return tiles_used

    ###############################
    #   net_analysis.py Helpers   #
    ###############################

    def get_all_nets(self):
        '''
            Retrieves all nets in the design
                Returns: list of all net names
        '''

        nets = [str(net.toString()) for net in self.query.getNets()]
        return nets
