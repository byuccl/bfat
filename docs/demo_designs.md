# BFAT Demo Designs

As of this writing, there are currently two designs packaged in `.zip` files in the Releases section of BFAT's GitHub repository. These are intended to be used as a user's first experience through the BFAT flow before using the tool on their own designs.

## RISC-V Soft Processor

`bfat_demo_1.zip` includes the design bitstream and Vivado checkpoint for a fault-tolerant RISC-V soft processor on a Nexys Video board. This design has TMR (triple modular redundancy) implemented in order to make the design resistant to bit upsets from radiation in harsh environments such as space, and is the primary catalyst for BFAT's development at BYU.

Also included is a list of all the fault bits that we have found in testing so far which have caused the fault-mitigated design to fail.

If you wish to run these files through BFAT, unzip the file and follow the "Quickstart Guide" and "How to Use BFAT" instructions in the [README](../README.md). The bitstream, dcp, and fault bit list are all provided in the zipped folder.

## Simple Counter

`bfat_demo_2.zip` includes a simple counter design to be implemented on a Basys 3 board. This example includes the source SystemVerilog and XDC files instead of the bitstream and implemented design checkpoint in order to present a more start-to-finish example.

As the design bitstream, checkpoint, and a fault bit list is not included, some extra steps are required before the design can be run through BFAT:

1. Extract the source files from the zipped file.
2. Using Vivado, synthesize, place, and route the source files.
3. Generate a design bitstream and design checkpoint after running implementation.
4. See [these instructions](sample_bit_scripts.md) for multiple included methods for generating a set of sample fault bits.
5. Follow the "Quickstart Guide" and "How to Use BFAT" instructions in the [README](../README.md) to setup and run BFAT.