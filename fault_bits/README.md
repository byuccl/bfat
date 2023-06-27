The `bfat/fault_bits` directory is where the tool will search for JSON fault bit lists to analyze when using the `scaffold` subcommand. This scaffold is intended to help with organization when working with many designs and/or fault bit lists.

To add a new fault bit list, create a new folder with the name of your design if one has not already been created. The name of this folder must match the name of the corresponding folder containing the bitstream and Vivado checkpoint in the `bfat/designs` directory.

In the new folder, add the JSON file containing the list of bit addresses. If you do not know what this file should like, more info can be found [here](../docs/fault_bit_lists.md).