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
    statistics.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Supplementary python file for BFAT functions calculating and
    reporting statistical data for the run
'''

from io import TextIOWrapper
from tokenize import group

class Statistics:
    '''
        Class to store statistical information about the BFAT run
            Attributes:
                stats - Collection of statistics and their current values

                order - List of statistics values in the order to be reported
    '''

    def __init__(self):
        self.stats = {}                         # Dict to store stat data
        self.order = ['Bit Groups',             # List of statistics in order
                      'Bit Groups w/ Errors',
                      'Fault Bits',
                      'INT Fault Bits',
                      'CLB Fault Bits',
                      'IOI3 Fault Bits',
                      'Non-Failure Fault Bits',
                      'Undefined Fault Bits',
                      'Bits Driven High',
                      'Bits Driven Low',
                      'Found Errors',
                      'PIP Open Errors',
                      'PIP Short Errors',
                      'CLB Altered Bit Errors',
                      'IOI3 Altered Bit Errors',
                      'IOI3 Routing Errors']

        # Create and initialize an entry in the stats dictionary for each stat to be counted
        for stat in self.order:
            self.stats[stat] = 0
    
    def __str__(self):

        # Print each statistic in the given order if it exists
        printout = ''
        for stat in self.order:
            # Create a 1-line gap between statistic sections
            if stat in ['Fault Bits', 'Found Errors']:
                printout += '\n'

            # Print the statistic as well as a percent of its parent statistic if it
            # isn't a parent statistic itself
            if stat not in ['Bit Groups', 'Fault Bits']:
                # Use 'Bit Groups' as parent statistic for percentage of
                # 'Bit Groups w/ Errors' and 'Fault Bits' for the others
                if stat == 'Bit Groups w/ Errors':
                    percent = round((self.stats[stat]/self.stats['Bit Groups'])*100, 2)
                else:
                    percent = round((self.stats[stat]/self.stats['Fault Bits'])*100, 2)
                printout += f'{stat}: {self.stats[stat]} ({percent}%)\n'
            else:
                printout += f'{stat}: {self.stats[stat]}\n'
        
        return printout

    def update(self, stat_updates:dict):
        '''
            Updates the values of any stats present in provided dictionary
            by adding their value to the current stored value
                Arguments: Dict of {stat_name : stat_value} to update the stat values
        '''

        # Add values of stats provided to current stored values
        for stat, value in stat_updates.items():
            # Check that the current stat exists in statistics collection
            if stat in self.stats:
                self.stats[stat] += value

def print_stat_footer(outfile:str, dcp_file:str, rpd_used:bool, statistics:dict, elapsed_time:float):
    '''
        Reads through the given fault report for the design and calculates significant statistical
        information and prints it all to the end of the provided output file.
            Arguments: String of output file path, path to the design's dcp file, bool of whether
                       RapidWright was used, dict of the statistics of the entire design, and a
                       float of the program's starting time
    '''

    # Open output file to write to
    with open(outfile, 'a') as out_f:
        dcp_name = ''
        # Iterate through each directory in file path to find the file name
        for dir_name in dcp_file.strip().split('/'):
            # If the current path segment is a dcp file save it
            if '.dcp' in dir_name:
                dcp_name = dir_name
                break
        design_str = f'Design modeled: {dcp_name}'

        # Determine which design query was used in the footer
        if rpd_used:
            design_query = 'RapidWright'
        else:
            design_query = 'Vivado'
        design_query_str = f'Design query used: {design_query}'


        design_beg_div = '=' * 70
        design_offset = ' ' * (35 - int(len(design_str) / 2))
        design_query_offset = ' ' * (35 - int(len(design_query_str) / 2))
        design_cls_div = '-' * 70

        out_f.write(f'\n{design_beg_div}\n')
        out_f.write(f'{design_offset}{design_str}\n')
        out_f.write(f'{design_query_offset}{design_query_str}\n')

        min_elapsed = int(elapsed_time/60)
        out_f.write(f'\t\t\t\tTotal time elapsed: {elapsed_time} sec\t({min_elapsed} min)\n')
        out_f.write(f'{design_cls_div}\n\n')

        out_f.write(str(statistics))

def get_bit_group_stats(group_bits:dict, print_flag = False, outfile: TextIOWrapper = None):
    '''
        Updates the statistics with the data from the passed in bit group
            Arguments: Dict of the provided bit group and its fault bits, bool flag to print
                       the bit group stats, and a TextIOWrapper for the file to print to
            Returns: Statistics object of the bit group
    '''

    group_stats = Statistics()

    group_stats.stats['Bit Groups'] += 1

    # Update statistic values based on the information of each bit
    error_in_group = False
    for fb in group_bits.values():
        group_stats.stats['Fault Bits'] += 1

        is_defined = type(fb.tile) != list

        # Update the statistics based on the current fault bit's tile
        if not is_defined:
            group_stats.stats['Undefined Fault Bits'] += 1
        elif 'INT_L' in fb.tile or 'INT_R' in fb.tile:
            group_stats.stats['INT Fault Bits'] += 1
        elif 'CLB' in fb.tile:
            group_stats.stats['CLB Fault Bits'] += 1
        elif 'IOI3' in fb.tile:
            group_stats.stats['IOI3 Fault Bits'] += 1

        # Update the statistics based on the current fault bit's change
        if fb.type == '0->1':
            group_stats.stats['Bits Driven High'] += 1
        elif fb.type == '1->0':
            group_stats.stats['Bits Driven Low'] += 1

        # Set failure message indicator substrings
        n_sptd = 'not yet supported'
        n_fail = 'Not able to find any failures'
        n_inst = 'No instanced resource'

        # Update the statistics based on the type of error for the current fault bit
        if is_defined and n_sptd in fb.failure or n_fail in fb.failure or n_inst in fb.failure:
            group_stats.stats['Non-Failure Fault Bits'] += 1
        elif 'CLB' in fb.tile and 'bit altered' in fb.failure:
            group_stats.stats['CLB Altered Bit Errors'] += 1
            group_stats.stats['Found Errors'] += 1
            error_in_group = True
        elif 'IOI3' in fb.tile and 'function(s) affected' in fb.failure:
            group_stats.stats['IOI3 Altered Bit Errors'] += 1
            group_stats.stats['Found Errors'] += 1
            error_in_group = True
        elif 'IOI3' in fb.tile and 'Faults occurred in net' in fb.failure:
            group_stats.stats['IOI3 Routing Errors'] += 1
            group_stats.stats['Found Errors'] += 1
            error_in_group = True
        elif 'Opens created' in fb.failure and 'Shorts formed' not in fb.failure:
            num_opens = 1 + fb.failure.count(',')
            group_stats.stats['PIP Open Errors'] += num_opens
            group_stats.stats['Found Errors'] += 1
            error_in_group = True
        elif 'Shorts formed' in fb.failure and 'Opens created' not in fb.failure:
            group_stats.stats['PIP Short Errors'] += 1
            group_stats.stats['Found Errors'] += 1
            error_in_group = True
        elif 'Opens created' in fb.failure and 'Shorts formed' in fb.failure:
            num_opens = 1 + fb.failure.count(',', 0, fb.failure.find(';'))
            group_stats.stats['PIP Open Errors'] += num_opens
            group_stats.stats['PIP Short Errors'] += 1
            group_stats.stats['Found Errors'] += 1
            error_in_group = True

    # If error was found in the bit group update the statistic
    if error_in_group:
        group_stats.stats['Bit Groups w/ Errors'] += 1
    
    if print_flag:
        print_bit_group_stats(outfile, group_stats)

    return group_stats

def print_bit_group_stats(outfile:TextIOWrapper, group_stats:Statistics):
    '''
        Prints out the statistics information related to the provided bit group
            Arguments: File object of the output file and a Statistics object for the bit group
    '''
    
    outfile.write(f'Bits: {group_stats.stats["Fault Bits"]}\n')

    # Count the errors found and calculate the rate of occurance as a percentage
    errors_found = 0
    errors_found += group_stats.stats['PIP Open Errors'] 
    errors_found += group_stats.stats['PIP Short Errors']
    errors_found += group_stats.stats['CLB Altered Bit Errors']
    errors_found += group_stats.stats['IOI3 Altered Bit Errors']
    errors_found += group_stats.stats['IOI3 Routing Errors']

    error_rate = round((errors_found/group_stats.stats['Fault Bits'])*100, 2)

    outfile.write(f'Errors Found: {errors_found} ({error_rate}%)\n')
    outfile.write('\n')
    
