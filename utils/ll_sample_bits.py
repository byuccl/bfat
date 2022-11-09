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
    ll_sample_bits.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Parses a logic location (.ll) file for a sample list of fault
    bits which can be ran through BFAT.

    Arguments:
        - '.ll' file from the design to be parsed
        - number of bits to include in the fault bit list

    Returns:
        - output file (.json) of the generated fault bit list
'''

import json
import random

def parse_ll_file(ll_file:str):
    '''
        Parses in bit address information from the given logic location file
            Arguments: path to the .ll file
            Returns: list of all bits in the file
    '''

    ll_bits = []
    
    # Open the .ll file to parse in the bits
    with open(ll_file) as ll_f:
        # Iterate through each line of the file
        for line in ll_f:
            line_split = line.split()
            
            # Ignore lines that do not give bit information
            if line_split[0] != 'Bit':
                continue

            # Get frame address and bit offset from start of frame
            frame_addr = line_split[2]
            full_offset = line_split[3]

            # Split full offset into a word offset and a bit offset from start of word
            word_offset = str(int(full_offset) // 32)
            bit_offset = str(int(full_offset) % 32)

            # Format the three address fields
            frame_addr = frame_addr.split('x')[1]
            word_offset = word_offset.rjust(3, '0')
            bit_offset = bit_offset.rjust(2, '0')

            # Put addresses into a list and add to the list of all bits 
            bitstream_addr = [frame_addr, word_offset, bit_offset]
            ll_bits.append(bitstream_addr)

    return ll_bits


def write_bit_list(ll_bits:list, num_bits:int, ll_file:str):
    '''
        Writes a file containing the specified number of bits from the .ll file
            Arguments: list of bits addresses from .ll file, number of bits to include,
                       file path of the ll_file
            Returns: Output .json file with the fault bit addresses
    '''

    fault_bits = []

    # Check that there is more bits in the ll file than the specified number
    if num_bits > len(ll_bits):
        print(f"There is less than {num_bits} useable bits in the provided .ll file.")
        num_bits = len(ll_bits)

    # Add the specified number of bits to the fault bits list
    while len(fault_bits) < num_bits: 
        # Get a random bit and add it to the fault bit list
        rand_bit = random.choice(ll_bits)
        fault_bits.append([rand_bit])

        # Remove the bit to avoid duplicates
        ll_bits.remove(rand_bit)

    fault_bits_json = json.dumps(fault_bits, indent=4)   

    # Generate file name for the fault bit list
    ll_filename = ll_file.split('/')[-1].split('.')[0]
    fault_bits_path = f'{ll_filename}_ll_sample_bits.json'

    # Write the fault bit list in a json format
    with open(fault_bits_path, 'w') as bits_f:
        bits_f.write(fault_bits_json)

##################################################
#                 Main Function                  #
##################################################

def main(args):
    '''
        Main function: Creates a non-deterministic, variable-length fault bit list
        based on the bits in the provided .ll file.
    '''

    # Gathers all bits from the .ll file
    ll_bits = parse_ll_file(args.ll_file)

    # Write the specified number of bits to a .json file
    write_bit_list(ll_bits, args.num_bits, args.ll_file)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Parses in a logical location file (.ll) '
                                    + 'and populates a fault bit list with bits from the file')
    parser.add_argument('ll_file', help='Logical location file describing a limited list of '
                        + 'bits and their related resources in the design')
    parser.add_argument('num_bits', type=int, help='The number of randomly selected bits from '
                        + 'the file to include in the fault bit list')
    args = parser.parse_args()

    main(args)