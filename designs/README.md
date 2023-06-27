The `bfat/designs` directory is where the tool will search for design files such as bitstreams and design checkpoints when using the `scaffold` subcommand. This scaffold is intended to help with organization when working with many designs and/or fault bit lists.

To add a new design, create a new folder with the name of your design. Then add the following files into the directory:
* bitstream -- make sure the bitstream uses the .bit extension as other files will not be recognized
* Vivado checkpoint -- make sure the checkpoint uses the .dcp extension as other files will not be recognized

Both of these files MUST be located in a directory in the `bfat/designs` folder in order to run `bfat.py` with the `scaffold` subcommand.