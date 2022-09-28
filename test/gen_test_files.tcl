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

###########################################################
#
# gen_test_files.tcl
#
# PARAMS:
#   - Path to design checkpoint file
#
# Basic tcl script to run in Vivado batch mode for
#   generating the design files needed for testing
#
###########################################################

# Generate files if design checkpoint provided and report issue if not
if { $argc == 1 } {
    # Open the design checkpoint
    open_checkpoint [lindex $argv 0]

    # Set the property to create a essential bits file for the
    # design on write bitstream as well
    set_property bitstream.seu.essentialbits yes [current_design]

    # Write the bitstream while also generating the additional
    # logic location and previously set essential bits files
    write_bitstream -logic_location_file test/test.bit

    # Get the list of all nets to select sample nets from
    set all_nets [get_nets -hier]

    # Flags to determine whether both sample nets have been found
    set short_net_found 0
    set long_net_found 0

    # Iterate through the list to find a net that uses 0 INT pips
    # and a net that uses at least one INT pip (but not too many)
    foreach curr_net $all_nets {
        set num_INT_pips 0

        # Count the number of INT tile pips that the net uses
        foreach pip [get_pips -of $curr_net] {
            set tile_type [string range $pip 0 4]
            if { ($tile_type == "INT_L") || ($tile_type == "INT_R") } {
                incr num_INT_pips
            }
        }

        # Check if the net uses 0 INT pips
        if { $num_INT_pips == 0 } {
            set short_net $curr_net
            set short_net_found 1
        }

        # Check if the net uses between 1 and 100 INT pips
        if { ($num_INT_pips >= 1) && ($num_INT_pips <= 100) } {
            set long_net $curr_net
            set long_net_found 1
        }
        
        # Do not continue if both sample nets have been found
        if { bool($short_net_found) && bool($long_net_found) } {
            break
        }
    }

    # Write the net names to a file
    set nets_file "test/test_nets.txt"
    set o_file [open $nets_file "w"]

    puts $o_file $short_net
    puts -nonewline $o_file $long_net

    close $o_file
} else {
    puts "Design checkpoint file not provided, or too many arguments provided"
}
