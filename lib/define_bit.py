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
    define_bit.py
    BYU Configurable Computing Lab (CCL): BFAT project 2022

    Supplementary python file for identifying and defining the affected location
    and function of bits from the bitstream.
'''

class Bit:
    '''
        Generates and stores information on an individual bit in the bitstream
            Attributes:
                bit - the bit's name and bitstream address

                tile - the tile on the part that is influenced by the bit

                addr - the bit's address within the influenced tile

                phys_fctns - the bit's functions as found in the Project X-Ray database
    '''

    def __init__(self, bitstream_addr:str, tilegrid:dict, tile_imgs:dict):
        # Set initial values for class attributes
        self.bit = bitstream_addr
        self.tile = 'NA'
        self.addr = 'NA'
        self.phys_fctns = []

        # Use the database to define the bit
        self.define_bit(tilegrid, tile_imgs)

    def define_bit(self, tilegrid:dict, tile_imgs:dict):
        '''
            Defines the bit's attributes using the provided part's tilegrid and tile mapping
                Arguments: Dicts of the part's tilegrid and of the general structures
                           of the part's tiles.
        '''

        # Get the bit's tile address
        tile_addr, potential_tiles = bit_tile_addr(self.bit.split('_')[1:], tilegrid, tile_imgs)

        # Update the bit's tile and address if a correct tile address was found
        if tile_addr:
            self.tile, self.addr, bus_val = tile_addr
        else:
            self.tile = potential_tiles

        # Associate the bit with its physical resources/functions if a tile address was found
        if self.tile and self.tile != 'NA' and type(self.tile) != list:
            t_tp = self.tile[:self.tile.find('_X')]

            # Separate association of bits for INT tiles from bits from other tiles
            if 'INT_L' in t_tp or 'INT_R' in t_tp:
                # Check each routing mux in the tile for the given bit
                for mux_name, mux in tile_imgs[t_tp].resources.items():
                    # Identify if the bit is in the row bits or column bits for the routing mux
                    if self.addr in mux.row_bits:
                        mux_str = f'{mux_name} {mux.mux_type} Routing Mux'
                        bit_type = 'Row Bit'
                        self.phys_fctns.append([mux_str, bit_type])
                        break
                    elif self.addr in mux.col_bits:
                        mux_str = f'{mux_name} {mux.mux_type} Routing Mux'
                        bit_type = 'Column Bit'
                        self.phys_fctns.append([mux_str, bit_type])
                        break

            # Seperate association of BRAM data initialization bits from other bits
            elif 'BRAM' in t_tp and bus_val == 0:
                # Check if the bit matches the intialization bit of a BRAM resource
                for curr_fctn, fctn_bit in tile_imgs[t_tp].init_resources.items():
                    # If the bit matches, add the resource to the bit's function list
                    if fctn_bit == self.addr:
                        fctn_list = curr_fctn.split('.')
                        self.phys_fctns.append(fctn_list)
            
            # Standard bit resource association
            else:
                # Search for the bit in each function for the given tile
                for curr_fctn, fctn_bits in tile_imgs[t_tp].resources.items():
                    # Add bit to bit functions if bit address is found in the function bits
                    if any([bit.replace('!', '') == self.addr for bit in fctn_bits]):
                        fctn_list = curr_fctn.split('.')
                        self.phys_fctns.append(fctn_list)

    def __str__(self):
        '''
            String representation of the Bit
        '''

        out_str = f'{self.bit}\n'
        out_str += f'\tTile: {self.tile}\n'
        out_str += f'\tAddress: {self.addr}\n'
        out_str += f'\tPhysical Functions:{self.phys_fctns}\n'

        return out_str

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

    bit_tiles = {}                                  # {tile : dataset index}
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
