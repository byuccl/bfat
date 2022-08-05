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
    design_query.py
    BYU Configurable Computing Lab (CCL): BFAT project 2022

    Supplementary python file for BFAT functions for querying a design's
    dcp file for design info through an open Vivado pipe
'''

from abc import ABCMeta, abstractmethod
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from queue import Queue, Empty

###################################
#  VivadoQuery Outstream Classes  #
###################################

class OutStreamReader:
    '''
        Non-blocking output stream reader for reading vivado output from the pipe
            Arguments: The output stream to read from
            
            Attributes:
                _s - Stream to read from

                _q - Queue to load the stream output into

                _t - Thread object on which the stream reader runs
    '''

    def __init__(self, stream):
        self._s = stream
        self._q = Queue()

        def _populateQueue(stream, queue:Queue):
            '''
                Populates the Queue and starts collecting lines from the stream
                    Arguments: Stream to read from and a queue to load stream output into
            '''

            while True:
                line = stream.readline()

                # Add line to queue if it exists and contains information
                if line:
                    # Add line if is not just a newline char
                    if line.strip():
                        queue.put(line.strip())
                else:
                    raise UnexpectedEndOfStream

        # Load the stream reader into a different Thread
        self._t = Thread(target = _populateQueue,
                args = (self._s, self._q))
        self._t.daemon = True

        # Start collecting lines from the stream reader
        self._t.start()

    def readline(self, timeout=None):
        '''
            Reads the next line from the stream if it exists
                Arguments: Float of time to wait before timeout
                Returns: Stream output if any is read or None if not
        '''
        
        # Get the next line if it exists, if not return None
        try:
            return self._q.get(block=timeout is not None,
                    timeout = timeout)
        except Empty:
            return None

class UnexpectedEndOfStream(Exception): pass

###################################
#         Query Classes           #
###################################

class DesignQuery(object):
    '''
        Abstract query for design information from the design's dcp checkpoint file
            Arguments: String of the path to the design's dcp checkpoint file

            Attributes:
                query - Object that queries the design dcp for design information

                part - Name of the part on which the design is implemented

                nets - collection of the locations and name of nets in the design routing

                pips - Collection of the PIPs used for nets in the design routing

                cells - Collection of the location and name of cells in the design

                wires - Collection of the location, name, and connections of wires in the design

            Abstract Methods:
                query_nets - Queries the design for the nets in a provided tile

                query_pips - Queries the design for the PIPs used by a provided net

                query_cells - Queries the design for the cells in a provided tile

                query_wires - Queries the design for the wires in a provided tile and their connections

                trace_affected_resources - Identifies any design resources affected by the provided
                                           net downstream of the provided inital tile and node
    '''
    __metadata__ = ABCMeta

    # Class Constructor
    @abstractmethod
    def __init__(self, dcp:str):
        self.query = dcp
        self.part = ''
        self.nets = {}       # {tile : {pin : net}}
        self.pips = {}       # {net : [(source, sink)]}
        self.cells = {}      # {tile : {site : {bel : cell}}}
        self.wires = {}      # {tile : {wire : [connections]}}

        self.tiles_queried_nets = set()

    #######################
    #   Get Design Data   #
    #######################

    def get_net(self, tile:str, pin:str):
        '''
            Gets the net at the requested location from the design data
                Arguments: Strings of the requested tile and pin
                Returns: String of the net name at the request location
        '''

        # Query nets if they have not been read in yet
        if tile not in self.tiles_queried_nets:
            self.query_nets(tile)

        # Return net name if available
        try:
            return self.nets[tile][pin]
        except KeyError:
            return 'NA'

    def get_pips(self, net:str):
        '''
            Gets the PIPs involved in a net from the design data
                Arguments: String of the net
                Returns: List of tuples as (source_pin, sink_pin)
        '''
        
        # Query PIPs if they have not been read in yet
        if net not in self.pips:
            self.query_pips(net)

        # Return list of PIPs if available
        try:
            return self.pips[net]
        except KeyError:
            return []

    def get_cell(self, tile:str, site:str, bel:str):
        '''
            Gets the cell at the requested location from the design data
                Arguments: Strings of the requested tile, site, and BEL 
                Returns: String of the cell name at the requested location
        '''
        
        # Query cells if they have not been read in yet
        if tile not in self.cells:
            self.query_cells(tile)

        # Return cell name if available
        try:
            return self.cells[tile][site][bel]
        except KeyError:
            return 'NA'

    def get_wire_connections(self, tile:str, wire:str):
        '''
            Gets the connections to the requested wire from the design data
                Arguments: Strings of the requested tile and wire
                Returns: List of the connections of the requested wire
        '''

        # Query wires if they have not been read in yet
        if tile not in self.wires:
            self.query_wires(tile)
        
        # Return wire connections if available
        try:
            return self.wires[tile][wire]
        except KeyError:
            return []

    ################################
    #   Abstract Design Querying   #
    ################################

    @abstractmethod
    def query_nets(self, tile: str):
        pass

    @abstractmethod
    def query_pips(self, net: str):
        pass

    @abstractmethod
    def query_cells(self, tile: str):
        pass

    @abstractmethod
    def query_wires(self, tile: str):
        pass

    ##########################################
    #   Abstract Affected Resource Tracing   #
    ##########################################

    def get_affected_rsrcs(self, net:str, init_tile:str, init_sink_wire:str):
        '''
            Wrapper function for recursive function trace_affected_resources
                Arguments: Strings of the net to trace and the tile and sink node to
                           begin the trace at
                Returns: List of the resources affected by the net downstream of the
                         initial tile and sink node
        '''

        init_rsrcs = set()
        traced_nodes = set()
        affected_rsrcs, traced_nodes = self.trace_affected_resources(net,
                                                init_tile, init_sink_wire,
                                                traced_nodes, init_rsrcs)

        return list(affected_rsrcs)

    @abstractmethod
    def trace_affected_resources(self, net:str, tile:str, node:str, traced_nodes:set, affected_rsrcs:set):
        pass

    ##########################
    #   Print Queried Data   #
    ##########################

    def print_nets(self):
        '''
            Helper function that prints out all the data currently stored on the
            design's nets in an organized format
        '''
        
        # Print nets if any are stored or report that none are stored yet
        if self.nets:
            print('Design Nets:')
            print('------------')
            # Print the nets of each tile that has been queried
            for tile in sorted(self.nets):
                print(f'{tile}:')
                # Print each pin and related net in the current tile
                for pin in sorted(self.nets[tile]):
                    print(f'\t{pin} : {self.nets[tile][pin]}')
        else:
            print('No nets queried from design')

    def print_cells(self):
        '''
            Helper function that prints out all the data currently stored on the
            design's cells in an organized format
        '''

        # Print cells if any are stored or report that none are stored yet
        if self.cells:
            print('Design Cells:')
            print('-------------')
            # Print cells in each tile that has been queried
            for tile in sorted(self.cells):
                print(f'{tile}:')
                # Print cells for each site in the current tile
                for site in sorted(self.cells[tile]):
                    print(f'\t{site}:')
                    # Print each BEL queried and its instanced cell in the current site
                    for bel in sorted(self.cells[tile][site]):
                        print(f'\t\t{bel} : {self.cells[tile][site][bel]}')
        else:
            print('No cells queried from design')

    def print_pips(self):
        '''
            Helper function that prints out all the data currently stored on the
            design's PIPs in an organized format
        '''

        # Print PIPs if any are stored or report that none are stored yet
        if self.pips:
            print('Design PIPs:')
            print('------------')
            # Print PIPs for each net that has been queried
            for net in sorted(self.pips):
                print(f'{net}:')
                # Print each PIP for the current net
                for pip in sorted(self.pips[net]):
                    print(f'\t{pip}')
        else:
            print('No net PIPs queried from design')

    def print_wires(self):
        '''
            Helper function that prints out all the data currently stored on the
            design's wires in an organized format
        '''

        # Print wires if any are stored or report that none are stored yet
        if self.wires:
            print('Design Wires:')
            print('-------------')
            # Print wires for each tile that has been queried
            for tile in sorted(self.wires):
                print(f'{tile}:')
                # Print each wire and its connections in the current tile
                for wire in sorted(self.wires[tile]):
                    print(f'\t{wire}:')
                    # Print the connections for the current wire
                    for connection in self.wires[tile][wire]:
                        print(f'\t\t{str(connection)}')
        else:
            print('No wires queried from design')

class VivadoQuery(DesignQuery):
    '''
        Design query through running vivado with an open subprocess pipe
            Arguments: String of the path to the design's dcp file

            Attributes:
                query - Pipe to an instance of vivado running in a different Thread used to query
                        the design's dcp file for design info

                part - Name of the part on which the design is implemented

                nets - Collection of the locations and name of nets in the design routing

                pips - Collection of the PIPs used for nets in the design routing

                cells - Collection of the location and name of cells in the design

                wires - Collection of the location, name, and connections of wires in the design
    '''

    # Class Constructor
    def __init__(self, dcp):
        super().__init__(dcp)

        # Open a pipe to run an instance of vivado through
        self.query = Popen([r'vivado -mode tcl'], shell=True, text=True,
                        stdin=PIPE, stdout=PIPE, stderr=STDOUT)

        # Create stream reader for the vivado pipe output
        self.outstream = OutStreamReader(self.query.stdout)

        # Check that Vivado pipe opened correctly and run initial tcl commands through Vivado
        try:
            # Open design checkpoint dcp
            self.run_command('readCheckpoint', dcp)
            # Remove the character limit on vivado command output
            self.run_command('setDisplayLimit', 0)
            # Edit tcl message config to enable output to be parsed
            self.run_command('supressInfoMsgs')
            self.run_command('setMsgLimit', 10000)
            # Get part name for the design from vivado and save it
            self.part = self.run_command('getDesignPart')
            # Query any information on global logic nets
            self.query_global_logic()
        except BrokenPipeError:
            print('\nVivado pipe not opened correctly. Check that Vivado is sourced\n\n')
            raise UnexpectedEndOfStream

    # Class Deconstructor
    def __del__(self):
        # Remove .jou file and rename .log file as latest_run.log
        Popen(['rm', 'vivado.jou'])
        Popen(['mv', 'vivado.log', 'latest_run.log'])

    # PIP divider identification
    def get_pip_divider(self, pip:str):
        '''
            Determines the divider symbol used in the provided PIP
                Arguments: String of the PIP to analyze
                Returns: String of the symbol used to divide the PIP nodes
        '''

        # Select identified divider in PIP
        if '<<->>' in pip:
            divider = '<<->>'
        elif '->>' in pip:
            divider = '->>'
        else:
            divider = '->'
        
        return divider

    #######################
    #   Design Querying   #
    #######################

    def query_nets(self, tile:str):
        '''
            Queries vivado for the names and routing of the nets in the requested tile
                Arguments: String of the tile to query
        '''

        tile_nets = self.run_command('getTileNets', tile)

        # Verify that nets were found for the tile
        if tile_nets and tile_nets != 'NA':
            # Get the PIPs for each net in the tile
            for net in tile_nets:
                net_pips = self.run_command('getNetPIPs', net, tile)

                # Verify that a real list of PIPs has been found
                if net_pips and net_pips != 'NA':
                    # Split each PIP into its components and add info to stored net data
                    for pip in net_pips:
                        tile, pip_pins = pip.split('/')
                        src_pin, sink_pin = pip_pins.split('.')[1].split(self.get_pip_divider(pip))

                        # Add entry for current tile in the stored net data if there isn't one yet
                        if tile not in self.nets:
                            self.nets[tile] = {}

                        # Add info to tile net mapping
                        self.nets[tile][src_pin] = net
                        self.nets[tile][sink_pin] = net
        
        self.tiles_queried_nets.add(tile)

    def query_pips(self, net:str):
        '''
            Queries vivado for the PIPs composing the requested net
                Arguments: String of the net to query
        '''

        pips = self.run_command('getNetPIPs', net)

        # Check that PIPs were found for the given net
        if pips and pips != 'NA':
            # Iterate through each PIP vivado can find for it
            for pip in pips:
                tile, pip_pins = pip.split('/')
                src_pin, sink_pin = pip_pins.split('.')[1].split(self.get_pip_divider(pip))

                # Add entry for current net to stored PIP data there isn't one yet
                if net not in self.pips:
                    self.pips[net] = []
                
                # Add PIP information to the stored data
                self.pips[net].append((f'{tile}/{src_pin}', f'{tile}/{sink_pin}'))

    def query_cells(self, tile:str):
        '''
            Queries vivado for the cell in the requested tile
                Arguments: String of the tile to query
        '''

        tile_sites = self.run_command('getTileSites', tile)
        # Check that sites were found in the given tile
        if tile_sites and tile_sites != 'NA':
            # Iterate through each site instance
            for site in tile_sites:
                # Create an entry for the current tile if there isn't one
                if tile not in self.cells:
                    self.cells[tile] = {}
                self.cells[tile][site] = {}

                site_cells = self.run_command('getSiteCells', site)
                # Check that cells were found in the given site
                if site_cells and site_cells != 'NA':
                    # Check each cell found in the site instance and add the BEL and cell
                    # name to its entry
                    for cell in site_cells:
                        bel = self.run_command('getCellBEL', cell)
                        self.cells[tile][site][bel] = cell

    def query_wires(self, tile:str):
        '''
            Queries vivado for the wires and their connections in the requested tile
                Arguments: String of the tile to query
        '''

        tile_wires = self.run_command('getTileWires', tile)
        # Check that wires were found for the given tile
        if tile_wires and tile_wires != 'NA':
            # Get connections for each wire found and add them to the stored data
            for wire in tile_wires:
                connections = self.run_command('getWireConnections', tile, wire)

                # Add the connections found to the wire structure if any are found
                if connections and connections != 'NA':
                    # Create new entry for new tiles
                    connections.append(f'{tile}/{wire}')
                    if tile not in self.wires:
                        self.wires[tile] = {}
                    self.wires[tile][wire] = connections

    def query_global_logic(self):
        '''
            Queries the design for all data related to GND and VCC nets
        '''

        gl_nets = set()

        # Query the design for any global logic (GND/VCC) nets
        for net_root in ['GND', 'VCC']:
            nets_found = self.run_command('getNets', net_root)

            # Add any global logic nets to the set
            [gl_nets.add(net) for net in nets_found if '_' in net and net.split('_')[0] == net_root]

        # Iterate through each net in the design
        for net in gl_nets:
            net_pips = self.run_command('getNetPIPs', net)

            # Check that PIPs were found for the given net
            if net_pips and net_pips != 'NA':
                # Add pip info for each pip to the stored nets and pips
                for pip in net_pips:
                    tile, pip_pins = pip.split('/')
                    src_pin, sink_pin = pip_pins.split('.')[1].split(self.get_pip_divider(pip))

                    # Add entry for current tile in the stored net data if there isn't one yet
                    if tile not in self.nets:
                        self.nets[tile] = {}

                    # Add info to tile net mapping
                    self.nets[tile][src_pin] = net
                    self.nets[tile][sink_pin] = net

                    # Add entry for current net to stored PIP data there isn't one yet
                    if net not in self.pips:
                        self.pips[net] = []
                    
                    # Add PIP information to the stored data
                    self.pips[net].append((f'{tile}/{src_pin}', f'{tile}/{sink_pin}'))

    ##########################
    #   Vivado Interfacing   #
    ##########################

    def run_command(self, cmd:str, arg1=None, arg2=None):
        '''
            Generates the appropriate tcl command to run in vivado through
            the open pipe and get the results back.
                Arguments: String of the command name, two optional strings of argument inputs
                Return: List or string of the output from vivado for the provided command
        '''
        
        # Set default values of args 1 and 2
        if arg1 is None:
            arg1 = ''
        if arg2 is None:
            arg2 = ''

        # Select tcl command and format in the provided args if needed
        tcl = {
            # Top-level commands
            'readCheckpoint' : f'open_checkpoint {arg1}\n',
            'setDisplayLimit' : f'set_param tcl.collectionResultDisplayLimit {arg1}\n',
            'supressInfoMsgs' : 'set_msg_config -severity INFO -suppress\n',
            'setMsgLimit' : f'set_param messaging.defaultLimit {arg1}\n',
            'getDesignPart' : 'puts [get_property PART [current_design]]\n',
            # Net Commands
            'getNets' : f'puts [get_nets -hierarchical {arg1}*]\n',
            'getNetPIPs' : f'puts [get_pips -of [get_nets {arg1}] {arg2}*]\n',
            'getNetCells' : f'puts [get_cells -of [get_nets {arg1}]]\n',
            'getNetAliases' : f'puts [get_nets -hier -segments -filter {{NAME =~ {arg1}}}]\n',
            # Site Commands
            'getSiteCells' : f'puts [get_cells -of [get_sites {arg1}]]\n',
            # Tile Commands
            'getTileSites' : f'puts [get_sites -of [get_tiles {arg1}]]\n',
            'getTileNets' : f'puts [get_nets -of [get_tiles {arg1}]]\n',
            'getTileWires' : f'set names []; foreach w [get_wires -of [get_tiles {arg1}]]' + ' {lappend names [string range $w [string last "/" $w]+1 [string length $w]] }; puts $names\n',
            # PIP Commands
            'getPIPNet' : f'puts [get_nets -of [get_pips {arg1}]]\n',
            # Cell Commands
            'getCellBEL' : f'puts [set n [get_property BEL [get_cells {arg1}]]; string range $n [string last "." $n]+1 [string length $n]]\n',
            'getCellPins' : f'puts [get_pins -of [get_cells {arg1}]]\n',
            'getCellSitePins' : f'puts [get_site_pins -of [get_pins -of [get_cells {arg1}]]]\n',
            # Pin/SitePin Commands
            'getPinNet' : f'puts [get_nets -of [get_pins {arg1}]]\n',
            'getPinDirection' : f'puts [get_property DIRECTION [get_pins {arg1}]]\n',
            # Node Commands
            'getNodeSite' : f'puts [get_sites -of [get_site_pins -of [get_nodes {arg1}]]]\n',
            'getNodeSitePin' : f'puts [get_site_pins -of [get_nodes {arg1}]]\n',
            'getNodeWires' : f'puts [get_wires -of [get_nodes {arg1}]]\n',
            # Wire Commands
            'getWireConnections' : f'puts [get_nodes -downhill -of_objects [get_nodes -of [get_wires {arg1}/{arg2}]]]\n',
            'getWireNode' : f'puts [get_nodes -of [get_wires {arg1}]]\n'
        }.get(cmd, '')
        
        # Return latest output from vivado if valid command, or return default value
        if tcl:
            # List of commands that return a string instead of a list
            str_cmds = ['getCellBEL', 'getPIPNet', 'getDesignPart', 'getPinNet',
                        'getPinDirection', 'getNodeSite', 'getNodeSitePin', 'getWireNode']

            # Send input tcl command to running vivado pipe
            self.query.stdin.write(tcl)
            self.query.stdin.flush()

            # Select python object return type based in the command run
            if cmd in str_cmds:
                return self.get_vivado_output(cmd, ret_list=False)
            elif cmd not in ['setDisplayLimit', 'supressInfoMsgs', 'setMsgLimit']:
                return self.get_vivado_output(cmd)
            else:
                return 'NA'
        else:
            return 'NA'
    
    def get_vivado_output(self, cmd:str, ret_list=None):
        '''
            Reads the latest output from the running vivado instance through the open
            pipe, formats it into the correct python data structure, and returns it
                Arguments: String of the command being run and a bool indicating
                           if a list is expected to be returned
                Returns: List or string of the output from vivado for the provided command
        '''

        # Set default values for bool flags
        if ret_list is None:
            ret_list = True
        end_reached = False

        # Read output stream as needed by the command running
        if cmd == 'readCheckpoint':
            # Get the next line until the last line output by reading a dcp is output
            while not end_reached:
                line = self.outstream.readline()

                # If the current line contains the indiciting substring return default value
                if line and 'open_checkpoint: Time (s):' in line:
                    return 'NA'
        else:
            # Get the next line until a real line is output that isn't just a newline
            while not end_reached:
                line = self.outstream.readline()

                # Save the raw output and flag the end of reading from the outstream
                if line and line != '\n':
                    end_reached = True
                    raw_out = line

                    # Remove all WARNING messages when a command comes back as invalid
                    if 'WARNING' in line:
                        # Continue reading in lines from the outstream until all messages are gone
                        while line:
                            line = self.outstream.readline()

        # Check that raw output is not a system message
        if raw_out and 'WARNING:' not in raw_out and 'ERROR:' not in raw_out and 'Resolution:' not in raw_out:
            # Return a string or list from the vivado output as indicated by ret_list parameter
            if ret_list:
                out = []
                raw_out = raw_out.split(' ')
                
                # Remove any item surrounded by <> from the list
                for item in raw_out:
                    # Check if current item if surrounded by <>
                    if item[0] == '<' and item[-1] == '>':
                        continue
                    elif item:
                        out.append(item)
                return out
            else:
                return raw_out

        return 'NA'

    #################################
    #   Affected Resource Tracing   #
    #################################

    def trace_affected_resources(self, net:str, tile:str, wire:str, traced_nodes:set, affected_rsrcs:set):
        '''
            Recursively traces downstream through the net in the design from the provided
            tile and node.
                Arguments: String of the net to be traced, the current tile, and the current node;
                           and sets of the current nodes traced and affected resources found
                Returns: Updated sets of the nodes traced and affected resources found after
                         tracing this node
        '''
        
        current_node = self.run_command('getWireNode', f'{tile}/{wire}')
        node_wires = self.run_command('getNodeWires', current_node)
        traced_nodes.add(current_node)
        pips = self.get_pips(net)

        # Find any non-INT or same-tile wire connections for the initial node
        sink_conns = {conn for conn in self.run_command('getWireConnections', tile, wire)}

        # Trace each wire connection for initial cells used by the net in the current tile
        for conn in sink_conns:
            conn_tile, conn_node = conn.split('/')

            # Trace affected cells in any non-INT tiles and trace net downstream in any INT tiles
            if 'INT' not in conn:
                # Query the cells in the tile if not already queried
                if conn_tile not in self.cells:
                    self.query_cells(conn_tile)
                
                init_cells = set()

                # Get site info for the node matching the current wire
                site = self.run_command('getNodeSite', conn)
                site_pin = self.run_command('getNodeSitePin', conn)

                # Verify that a site_pin was found
                if site_pin and site_pin != 'NA':
                    # Find any cells that are connected to the site pin
                    for cell in self.cells[conn_tile][site].values():
                        cell_site_pins = self.run_command('getCellSitePins', cell)

                        # Identify if the node's site pin is connected to the current cell
                        if site_pin in cell_site_pins:
                            affected_rsrcs.add(cell)
                            init_cells.add(cell)
                
                # Trace the site's affected cells from each of the initial cells found
                [affected_rsrcs.union(self.trace_cells(conn_tile, site, cell, affected_rsrcs)) for cell in init_cells]

            else:
                # Check each pip if their nodes match wires from the current node and connection
                conn_wires = self.run_command('getNodeWires', conn)
                for pip in pips:
                    # Check if current pip nodes matche wires and the node hasn't been traced yet
                    if pip[0] in node_wires and pip[1] in conn_wires and conn not in traced_nodes:
                        affected_rsrcs, traced_nodes = self.trace_affected_resources(net, conn_tile, conn_node,
                                                                                     traced_nodes, affected_rsrcs)

        return affected_rsrcs, traced_nodes

    def trace_cells(self, tile:str, site:str, cell:str, affected_resources:set):
        '''
            Recursively traces through the affected cells downstream of the provided cell
                Arguments: Strings of the tile, site, and name of the cell to be traced and
                           the current set of affected resources found so far
                Returns: Updated set of the affected resources found after tracing the cell
        '''

        # Find all of the output pins for the current cell
        cell_outpins = [pin for pin in self.run_command('getCellPins', cell) if self.run_command('getPinDirection', pin) == 'OUT']
        for cell_outpin in cell_outpins:
            pin_net = self.run_command('getPinNet', cell_outpin)
            # Verify that a proper cell pin was found
            if not pin_net or pin_net == 'NA':
                continue

            pin_net_aliases = self.run_command('getNetAliases', pin_net)
            # Iterate through all aliases of the net
            for pin_net_alias in pin_net_aliases:
                net_cells = self.run_command('getNetCells', pin_net_alias)

                # Add cells to the affected resources and trace that cell for others
                for net_cell in net_cells:
                    # Specify only different cells in the same tile
                    if net_cell != cell and net_cell in self.cells[tile][site].values() and net_cell not in affected_resources:
                        affected_resources.add(net_cell)
                        affected_resources.union(self.trace_cells(tile, site, net_cell, affected_resources))
        
        return affected_resources
