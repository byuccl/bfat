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
    tile.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Classes used for storing configuration bit information and fundamental functions
    used in tiles and any corresponding resources in designs given to BFAT
'''

from os.path import exists

# Directory that contains the ProjectXray .db files
XRAY_DB = 'database/prjxray-db'

class Tile:
    '''
        Stores the configuration information for a specific tile
            Attributes:
                name - string of the tile's name (ex: CLBLL_L_X45Y78)

                type - string of the tile's type (ex: CLBLL)

                resources - dictionary of the resources available in the tile and their
                            corresponding configuration bits

                config_bits - dictionary of the configuration bits in the tile and their
                              current values

                nets - dictionary of the nodes in the tile and their routed nets

                pips (INT specific) - dictionary of the pips in the INT switchbox and the
                                      configuration bits needed to activate them

                cnxs (INT specific) - dictionary of the connections formed through activated
                                      pips in the INT switchbox
    '''

    def __init__(self, tile_name:str, tile_type:str, part:str):
        self.name = tile_name
        self.type = tile_type
        self.resources = {}         # {resource : [bit_config]}
        self.config_bits = {}       # {bit_addr : bit_value}
        self.nets = {}              # {node : net}

        # Interconnect-specific Variables and Population (Possible pips and Connections formed)
        if self.type in ('INT_L', 'INT_R'):
            self.pips = {}          # {sink : {src : [bit_config]}}
            self.special_pips = {}  # {sink : {src : config_type}}
            self.cnxs = {}          # {src : [sinks]}
            self.populate_tile(part)
            self.resources.update({sink : RTMux(sink, self.pips[sink]) for sink in self.pips})

        # Generic Population
        else:
            self.populate_tile(part)

    def model_tile(self):
        '''
            Models all used routing mux from a single tile from the design
                Returns: 2D list of strings modelling each routing mux in the requested tile
        '''

        tile_mdl = [self.model_mux(mux.sink_nd) for mux in self.resources.items()]
        return tile_mdl

    def print_tile(self, statistics:dict):
        '''
            Models and prints off all routing muxes in a single tile
                Arguments: Dict of the current statistics
        '''

        tl_mdl = self.model_tile(statistics)

        first_mux = True
        # Print the model of each mux in the tile
        for mux in sorted(tl_mdl):
            # Print the models of each used mux with a connection formed
            if 'No connections formed' not in mux[1]:
                # Print a new line after each mux model printed except the first
                if not first_mux:
                    print('', end='\n')
                first_mux = False

                print(mux[0])
                first_ln = True
                # Print each line of the current mux model
                for line in mux[1:]:
                    # Print a new line after each line of the current mux model except the first
                    if not first_ln:
                        print('')
                    first_ln = False
                    print('\t' + line, end='')

    def model_mux(self, sink:str):
        '''
            Models a single routing mux from the given tile
                Arguments: String of the sink node
                Returns: List of strings modelling the requested routing mux
        '''

        mux_mdl = []
        mux_mdl.append(self.type + '_' + self.name + '_' + sink + ':')

        # Evaluate connections formed in rourting mux if any and report status
        if sink in self.cnxs:
            # Iterate through each source node connected to the sink node
            for src in self.cnxs[sink]:
                row_str = ''
                col_bits = []
                # Check each row bit of the current source to see if they are used
                for row in self.resources[sink].row_bits:
                    # If the current row bit is used save its value
                    if row in self.pips[sink][src]:
                        row_str = row
                        break
                # Check each column bit of the current source to see if they are used
                for col in self.resources[sink].col_bits:
                    # If the current column bit is used add it to a list
                    if col in self.pips[sink][src]:
                        col_bits.append(col)
                col_str = ', '.join(col_bits)

                # Add explaination of mux status to mux model
                mux_mdl.append(f'Driven by node {src} through column bit(s) {col_str}; & row bit {row_str}')

        else:
            mux_mdl.append('No connections formed in ' + sink + ' routing mux')

        return mux_mdl

    def print_mux(self, mux_name:str):
        '''
            Models and prints off a single routing mux
                Arguments: String of the routing mux's name
        '''

        mux = self.model_mux(mux_name)

        print(mux[0])
        first_ln = True
        # Print each line of the mux model
        for line in mux[1:]:
            # Print an extra space after each line after the first
            if not first_ln:
                print('')
            first_ln = False
            print('\t' + line, end='')

    def change_bit(self, bit:str, value:int):
        '''
            Changes selected config bit to have the given value
                Arguments: String of the bit address to change and int of the value to be set to
        '''

        self.config_bits[bit] = value

    def eval_connections(self):
        '''
            Evaluates pip rules and current config bit values to find any connections formed in
            the tile and updates the cnxs class field.
        '''

        updated_cnxs = {}

        # Evaluate the pip connections for each routing mux in the tile
        for mux in self.pips:
            # Evaluate the bit rules for each pip connected to the current routing mux
            for src in self.pips[mux]:
                connected = True
                # Evaluate each bit_rule for the current pip to find if anything doesn't match
                for bit_rule in self.pips[mux][src]:
                    # Check that the config bit value matches the values specified by its rule
                    if bit_rule[0] == '!':
                        # Check any low rules for the bit inside the rule
                        if self.config_bits[bit_rule[1:]] != 0:
                            connected = False
                            break
                    elif self.config_bits[bit_rule] != 1:
                        connected = False
                        break
                
                # Add the source and mux to the dictionary if everything matched for this rule
                if connected:
                    # Create a dictionary entry if there isn't one and add the source and sink
                    try:
                        updated_cnxs[src].append(mux)
                    except KeyError:
                        updated_cnxs[src] = [mux]
        
        self.cnxs = updated_cnxs

    def populate_tile(self, part:str):
        '''
            Opens the corresponding projectXray database file, parses in the info, and uses
            it to populate the object variables
                Arguments: String of the part name
        '''

        # Determine the family of the part
        if 'xc7' in part:
            if 'xc7a' in part:
                arch = "artix7"
            if 'xc7k' in part:
                arch = "kintex7"
            if 'xc7s' in part:
                arch = "spartan7"
            if 'xc7z' in part:
                arch = "zynq7"
        
        segbits_path = f'{XRAY_DB}/{arch}/segbits_{self.type.lower()}.db'

        # Make sure that the segbits file for this tile type exists
        if exists(segbits_path):
            # Open the corresponding segbits*.db file to read from 
            with open(segbits_path) as db_f:
                # Iterate through each line and get the necessary information from it
                for line in db_f:
                    db_ln = line.strip().split(' ')
                    header = db_ln[0].split('.')
                    bits = db_ln[1:]

                    # Add config bits to tile's dict with default value of 0
                    for cfgb in bits:
                        self.config_bits[cfgb.replace('!','')] = 0

                    # Interconnect tile population
                    if self.type in ('INT_L', 'INT_R'):
                        sink = header[1]
                        # Get the name of the source pin from the line
                        if len(header) > 2:
                            src = header[2]
                        else:
                            src = 'Config Bit'

                        # Add the current PIP and its bit configuration to the tile's pips
                        try:
                            self.pips[sink][src] = bits
                        except KeyError:
                            self.pips[sink] = {}
                            self.pips[sink][src] = bits

                    # Generic tile population
                    else:
                        rsrc = ''
                        first = True
                        # Get the name of the resource
                        for h_pt in header[1:]:
                            if not first:
                                rsrc += '.'
                            rsrc += h_pt
                            first = False

                        self.resources[rsrc] = bits
        
        # Add default/always active pips from ppips file if the tile is an interconnect
        if self.type in ('INT_L', 'INT_R'):
            ppips_path = f'{XRAY_DB}/{arch}/ppips_{self.type.lower()}.db'

            # Make sure that the segbits file for this tile type exists
            if exists(ppips_path):
                # Open the corresponding ppips*.db file to read from 
                with open(ppips_path) as ppips_f:
                    # Iterate through each line and get the necessary information from it
                    for line in ppips_f:
                        db_ln = line.strip().split(' ')
                        header = db_ln[0].split('.')
                        pip_type = db_ln[1]
                        
                        # Extract pip sink and source from the header
                        sink = header[1]
                        src = header[2]

                        # Add the current PIP and its configuration type to the tile's pips
                        try:
                            self.special_pips[sink][src] = pip_type
                        except KeyError:
                            self.special_pips[sink] = {}
                            self.special_pips[sink][src] = pip_type


class RTMux:
    '''
        Models the routing mux for the given sink node in its tile_type
            Attributes:
                sink_nd - string of the sink node for the routing mux

                mux_type - string of the mux's type based on the number of configuration bits used
                           to connect a pip and the number of possible sources it can connect to

                row_bits - list of the row bits used by the routing mux

                col_bits - list of the column bits used by the routing mux
    '''

    def __init__(self, sink_nd:str, pips:dict):
        self.sink_nd = sink_nd
        self.mux_type = ''
        self.row_bits = []
        self.col_bits = []
        self.gen_mux(pips)

    def def_mux_type(self, num_srcs:int):
        '''
            Determines the mux's number of rows, number of columns, and mux type
                Arguments: Int of the number of possible sources to connect to the mux
                Returns: Ints of the number of connections a given row bit or column bit for
                         the mux type will be used in
        '''

        # Set the mux type based on the number of sources available to the sink
        if num_srcs == 24:
            self.mux_type = '5-24'
            return 4, 24
        elif num_srcs == 20:
            self.mux_type = '2-20'
            return 5, 4
        elif num_srcs == 18:
            self.mux_type = '2-18'
            return 6, 3
        elif num_srcs == 16:
            self.mux_type = '5-16'
            return 4, 16
        elif num_srcs == 12:
            self.mux_type = '2-12'
            return 4, 3

        print(f'Unrecognized number of source nodes ({num_srcs}) for {self.sink_nd} sink node')
        return 0, 0

    def gen_mux(self, pips:dict):
        '''
            Generates the model of the routing mux
                Arguments: Dict of the pips in the tile that have this mux as the sink node
        '''

        num_srcs = len(pips)
        cfg_bit_cnt = {}

        # Iterate through each src node from tile_type.pips and its cfg_bits
        for src in pips:
            cfg_bits = [bit.replace('!', '') for bit in pips[src]]

            # Create a counter for each new cfg_bit and increment each recurring one
            for cfgb in cfg_bits:
                if cfgb not in cfg_bit_cnt:
                    cfg_bit_cnt.update({cfgb : 1})
                else:
                    cfg_bit_cnt.update({cfgb : cfg_bit_cnt[cfgb] + 1})

        # Depending on how many src nodes there are, assign each to be a row or col
        # mux_type format: <num cfg bit inputs>_<num srcs>
        row_num, col_num = self.def_mux_type(num_srcs)

        for cfgb in cfg_bit_cnt:
            if cfg_bit_cnt[cfgb] == col_num:
                self.col_bits.append(cfgb)
            elif cfg_bit_cnt[cfgb] == row_num:
                self.row_bits.append(cfgb)
            else:
                print('Unrecognized number of inclusions (' + str(cfg_bit_cnt[cfgb])
                      + ') in routing mux for ' + cfgb)
