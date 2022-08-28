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
} else {
    puts "Design checkpoint file not provided, or too many arguments provided"
}
