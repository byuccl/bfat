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
    test_bfat.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2022

    Collection of pytest unit tests for the BFAT tool and related functions.
'''

import os
import json
import subprocess

# Add bfat root directory to the module import path
import sys
sys.path.append('../bfat')

# Number of fault bits to generate for bit lists from essential_bits.py and ll_sample_bits.py
NUM_TEST_BITS = 6

##################################################
#                 Test Functions                 #
##################################################

def test_gen_design_files(dcp):
    '''
        Generates design files necessary to run all other tests
    '''

    # List design files to be generated
    gen_files = ['test.bit', 'test.ebd', 'test.ll']

    # Run tcl script for generating design files through subprocess of vivado
    subprocess.run(['vivado', '-mode', 'batch', '-source', 'test/gen_test_files.tcl', '-tclargs', dcp])

    # Get the contents of the test directory
    dir_files = os.listdir('./test/')

    # Check that each generated file is now in the test directory
    for gf in gen_files:
        assert gf in dir_files

def test_find_fault_bits(dcp):
    '''
        Tests the functionality of the find_fault_bits.py main function
    '''

    from utils.find_fault_bits import main as ffb_main

    # Create and set test args
    args = UnitTestArgs()
    args.bitstream = 'test/test.bit'
    args.dcp_file = dcp
    args.run = False
    args.rapidwright = True

    # Run main function of find_fault_bits util with test input args
    ffb_main(args)

    ffb_bit_list = 'test_sample_bits.json'

    # Check that the created fault bit list exists
    assert os.path.exists(ffb_bit_list)

    # Load the bit list as a 3D list
    with open(ffb_bit_list) as ffbf:
        ffb_list = json.load(ffbf)
    
    # Test that correct number of bits was generated
    assert len(ffb_list) == 6
    # Test that bit groups always only have 1 or 2 bits
    assert not any([len(grp) != 1 and len(grp) != 2 for grp in ffb_list])
    # Test that all bits have their 3 components
    assert not any([len(bit) != 3 for grp in ffb_list for bit in grp])

def test_essential_bits():
    '''
        Tests the functionality of the essential_bits.py main function
    '''

    from utils.essential_bits import main as ebd_main

    # Create and set test arg
    args = UnitTestArgs()
    args.ebd_file = 'test/test.ebd'
    args.num_bits = NUM_TEST_BITS

    # Run main function of essential_bits util with test input args
    ebd_main(args)

    ebd_bit_list = 'test_ebd_sample_bits.json'

    # Check that the created fault bit list is correct if one exists
    assert os.path.exists(ebd_bit_list)

    # Load the bit list as a 3D list
    with open(ebd_bit_list) as ebdf:
        ebd_list = json.load(ebdf)
    
    # Fail if correct number of bits not generated
    assert len(ebd_list) == NUM_TEST_BITS
    # Fail if >1 bit generated for any bit group
    assert not any([len(grp) != 1 for grp in ebd_list])
    # Fail if any bit doesn't have its 3 components
    assert not any([len(grp[0]) != 3 for grp in ebd_list])

def test_ll_sample_bits():
    '''
        Tests the functionality of the ll_sample_bits.py main function
    '''

    from utils.ll_sample_bits import main as ll_main

    # Create and set test args
    args = UnitTestArgs()
    args.ll_file = 'test/test.ll'
    args.num_bits = NUM_TEST_BITS

    # Run main function of ll_sample_bits util with test input args
    ll_main(args)

    ll_bit_list = 'test_ll_sample_bits.json'

    # Check that the created fault bit list is correct if one exists
    assert os.path.exists(ll_bit_list)

    # Load the bit list as a 3D list
    with open(ll_bit_list) as llf:
        ll_list = json.load(llf)
    
    # Fail if correct number of bits not generated
    assert len(ll_list) == NUM_TEST_BITS
    # Fail if >1 bit generated for any bit group
    assert not any([len(grp) != 1 for grp in ll_list])
    # Fail if any bit doesn't have its 3 components
    assert not any([len(grp[0]) != 3 for grp in ll_list])

def test_bitread():
    '''
        Tests the functionality of bitread.py converting a bitstream
        to a .bits file
    '''

    from bitread import main as bitread_main

    # Create and set test args
    args = UnitTestArgs()
    args.bitstream = 'test/test.bit'

    # Run main function of bitread tool with test input args
    bitread_main(args)

    # Check .bits file if it exists, fail test if it doesn't
    assert os.path.exists('test/test.bits')

    # Open generated .bits file to check if is correct
    with open('test/test.bits') as bits:
        # Check each line if they are a bit address or empty line
        for line in bits:
            assert 'bit_' in line or line == '\n'

def test_bfat(dcp):
    '''
        Tests the functionality of the BFAT tool using the Rapidwright
        interface for design querying
    '''

    from bfat import main as bfat_main

    # Load in the testing control fault report
    with open('test/ctrl_report.json') as cr:
        ctrl_report = json.load(cr)

    # Create and set test args for BFAR run using vivado
    viv_args = UnitTestArgs()
    viv_args.bitstream = 'test/test.bits'
    viv_args.dcp_file = dcp
    viv_args.fault_bits = 'test_sample_bits.json'
    viv_args.bits_file = True
    viv_args.rapidwright = False
    viv_args.out_file = 'test/viv_test_report.txt'

    # Create and set test args for BFAT run using rapidwright
    rpd_args = UnitTestArgs()
    rpd_args.bitstream = 'test/test.bits'
    rpd_args.dcp_file = dcp
    rpd_args.fault_bits = 'test_sample_bits.json'
    rpd_args.bits_file = True
    rpd_args.rapidwright = True
    rpd_args.out_file = 'test/rpd_test_report.txt'

    # Run BFAT test for both versions of the DesignQuery interface
    for args in [viv_args, rpd_args]:
        # Run main function of BFAT tool with test input args
        bfat_main(args)

        # Parse in relevant info from the run's output fault report
        test_report = parse_fault_report_contents(args.out_file)

        # Test each of the bit groups in the test report against the control
        for grp, grp_secs in test_report.items():
            assert grp in ctrl_report

            # Test each section in the curren bit group against the control
            for sec, sec_bits in grp_secs.items():
                assert sec in ctrl_report[grp]
                assert len(sec_bits) == ctrl_report[grp][sec]['num_bits']

                # Perform further evaluation on any section except Undefined Bits
                if sec != 'Undefined':
                    # Get the section attributes from the control excluding num_bits
                    sec_attrs = {k : v for k, v in ctrl_report[grp][sec].items() if k != 'num_bits'}
                    # Get any section attributes that have list type values
                    list_attrs = [k for k, v in sec_attrs.items() if type(v) == list]

                    # Evaluate attribute testing rules for single and multi-conditional rules
                    if not list_attrs:
                        # Evaluate each bit's attributes in the current section against the control
                        for bit_attrs in sec_bits.values():
                            for attr, rule in sec_attrs.items():
                                # Evaluate current bit attribute in section
                                eval_status = eval_attr_rule(bit_attrs, attr, rule)
                                assert eval_status
                    else:
                        # Get number of conditions to test in section
                        num_conds = len(sec_attrs[list_attrs[0]])

                        # Evaluate each condition for bits that fulfill it
                        for cond in range(num_conds):
                            eval_status = False

                            # Evaluate each bit's attributes against the current condition
                            for bit_attrs in sec_bits.values():
                                bit_status = True
                                for attr, rule in sec_attrs.items():
                                    # Evaluate rule provided by attribute or condition list
                                    if type(rule) == list:
                                        bit_status = eval_attr_rule(bit_attrs, attr, rule[cond])
                                    else:
                                        bit_status = eval_attr_rule(bit_attrs, attr, rule)

                                    # End evaluation of bit when incorrect evaluation found
                                    if not bit_status:
                                        break
                                
                                # End evaluation of condition when bit found that fulfills condition
                                if bit_status:
                                    eval_status = bit_status
                                    break
                            
                            assert eval_status

def test_remove_gen_files(keep_files):
    '''
        Removes generated design and report files used for testing
    '''

    if keep_files:
        assert True
    else:
        # List files to be removed
        rm_files = ['test/test.bit', 'test/test.bits', 'test/test.ebc', 'test/test.ebd',
                    'test/test.ll', 'test/*_test_report.txt', 'test*_sample_bits.json',
                    'latest_run.log', 'vivado*.log', 'vivado*.jou']

        # Get the contents of the BFAT root and test directories
        bfat_dir = os.listdir('.')
        test_dir = os.listdir('./test/')

        # Run a subprocess to remove each of the files
        for rmf in rm_files:
            # Remove files matching pattern if '*' in file, or single file if not
            if '*' in rmf:
                path = rmf.split('/')
                patterns = path[-1].split('*')
                path.pop()

                # Select dir to remove file from
                if 'test/' in rmf:
                    search_dir = test_dir
                else:
                    search_dir = bfat_dir
                
                for f in search_dir:
                    if not any([p not in f for p in patterns]):
                        path.append(f)
                        os.remove('/'.join(path))
                        path.pop()
            else:
                # Remove file only if it exists
                if os.path.exists(rmf):
                    os.remove(rmf)
        
        # Refresh the contents of the BFAT root and test directories
        bfat_dir = os.listdir('.')
        test_dir = os.listdir('./test/')

        # Check that each file has been properly removed
        for rmf in rm_files:
            # Fail the test if any file was not properly removed
            if 'test/' in rmf:
                assert rmf.split('/')[-1] not in test_dir
            else:
                assert rmf not in bfat_dir

##################################################
#            Helper Classes/Functions            #
##################################################

class UnitTestArgs():
    '''
        Basic script storing input args for BFAT tool runs
    '''

    def __init__(self):
        # File Paths
        self.bitstream = None
        self.dcp_file = None
        self.ebd_file = None
        self.ll_file = None
        self.fault_bits = None
        self.out_file = None

        # Run Flags
        self.run = None
        self.rapidwright = None
        self.bits_file = None

        self.num_bits = None

def parse_fault_report_contents(fault_report:str):
    '''
        Parses in the provided fault report from running the BFAT tool and gets the
        relevant content for verification of a correct output
            Arguments: String of path to fault report to interpret
            Returns: Dict of generalized fault_report content
    '''

    contents = {}

    # Open provided fault report file
    with open(fault_report) as fr:
        line = ''
        # Read in bit groups until the statistics footer starts
        while 'Design modelled' not in line:
            line = fr.readline()
            # Parse in info for bit group when one is found
            if 'Bit Group' in line:
                group = line.strip()
                contents[group] = {}
                section = ''
                # Read in lines of bit group report until it ends
                while 'Errors Found:' not in line:
                    line = fr.readline()

                    # Set bit group report section if new one found/entered
                    if ' Bits:' in line:
                        section = line.strip().split(' ')[0]

                        # Determine data class of last level based on current section
                        if section == 'Undefined':
                            contents[group][section] = []
                        else:
                            contents[group][section] = {}
                    
                    # Parse in any bit info found
                    if 'bit_' in line:
                        # Determine method of parsing in bit info by the current section
                        if section == 'Failure':
                            # Parse in bit info from the next few lines
                            bit, fault_type = line.strip().split(' ')
                            tile, resource, fctn = fr.readline().strip().split(' - ')
                            design_name = fr.readline().strip().split(': ')[1]
                            fault = fr.readline().strip()

                            line = fr.readline()
                            affected_pips = []
                            # Parse in affected PIPs if there are any
                            if 'PIPs' in line:
                                end_aff_pips = False

                                # Add affected pips to a list until affected pips ends
                                while not end_aff_pips:
                                    line = fr.readline().strip()

                                    # Add each line to a list if ending conditions not met
                                    if not line or line in ['NA', 'Affected Resources:']:
                                        end_aff_pips = True
                                    else:
                                        affected_pips.append(line)

                            end_aff_rsrcs = False
                            affected_resources = []
                            # Add affected resources to a list until affected resources ends
                            while not end_aff_rsrcs:
                                line = fr.readline().strip()

                                # Add each line to a list if ending conditions not met
                                if not line or line in ['NA', 'No affected resources found']:
                                    end_aff_rsrcs = True
                                else:
                                    affected_resources.append(line)
                            
                            # Add parsed bit info to data
                            contents[group][section][bit] = {}
                            contents[group][section][bit]['tile'] = tile
                            contents[group][section][bit]['resource'] = resource
                            contents[group][section][bit]['function'] = fctn
                            contents[group][section][bit]['design_name'] = design_name
                            contents[group][section][bit]['type'] = fault_type
                            contents[group][section][bit]['fault'] = fault
                            contents[group][section][bit]['affected PIPs'] = affected_pips
                            contents[group][section][bit]['affected resources'] = affected_resources
                        elif section == 'Non-Failure':
                            # Parse limited bit info from the line
                            bit, bit_info = line.strip().split(': ')
                            tile, resource, fctn, design_name = bit_info.split(' - ')

                            # Add parsed bit info to data
                            contents[group][section][bit] = {}
                            contents[group][section][bit]['tile'] = tile
                            contents[group][section][bit]['resource'] = resource
                            contents[group][section][bit]['function'] = fctn
                            contents[group][section][bit]['design_name'] = design_name
                        elif section == 'Undefined':
                            # Get bit from line and add it to data
                            contents[group][section].append(line.strip())
                        else:
                            print(f'ERROR: Bit found outside of any known sections ({section})')
                            raise ValueError
    
    return contents

def eval_attr_rule(report_bit:dict, attr:str, rule:str):
    '''
        Evaluates a rule provided from the control report for testing BFAT output reports
            Arguments: String of the attribute rule
            Returns: Bool of the rule's evaluation
    '''

    status = True

    # Evaluate the rules for checking exact values or presence in the attribute respectively
    if rule.replace('!', '') == 'EXISTS':
        inv = '!' in rule

        # Evaluate rules querying the existence of the attribute
        if report_bit[attr] and report_bit[attr] != 'NA':
            status = not inv
        else:
            status = inv
    else:
        conds = rule.split(',')
        status = True

        # Check that each condition is met by the test report bit's attribute
        for cond in conds:
            inv = '!' in cond
            val = cond.replace('!', '')

            # Evaluate the condition's presence in the bit's attribute
            if val in report_bit[attr]:
                status = not inv
            else:
                status = inv
            
            # End loop if any condition not met
            if not status:
                break
    return status
