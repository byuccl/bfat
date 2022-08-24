# Fault Report Description

---

## Overview:

Whenever BFAT is run on a set of fault bits, it will produce a fault report text file. There is a lot of information that is collected in these fault reports, so this guide aims to teach new users of BFAT how to interpret these reports.

The guide will be going through a sample fault report with some of the most common faults that can show up during fault analysis. The BFAT repository includes a `find_fault_bits.py` script which can allow any user to run the script on their own design in order to generate a sample list of fault bits:

```
    python3 find_fault_bits.py <design_bitstream_file> <design_checkpoint_file> -r
```

This command will generate a `.json` file of sample fault bits to apply to the design in the same directory that your bitstream is located in. It will then run those bits through BFAT, producing an example fault report with the exact same kinds of faults as the ones used in this guide. However, the fault reports will not be identical, since the design is different and will be placed on and routed through different tiles. Do note that `find_fault_bits.py` is non-deterministic and will produce a different output for the same set of input design files. This is because the script is only trying to generate certain types of faults (LUT fault, net open, net short, etc.), and there are usually many different bits that can cause each type of fault.

## Sample Fault Report:

Fault reports are organized into "bit groups", which divide fault bits into groups that we want to test at the same time. In this sample fault report, most of the bit groups only include one bit each, so BFAT will determine the effects of flipping each bit individually. However, the tool also supports simulating the effects of multiple bit upsets at the same time, which can be accomplished by including multiple bits in the same bit group.

---

### LUT Fault:

```
======================================================================
                             Bit Group 1
======================================================================

Significant Bits:
------------------------------
bit_004001a2_027_15 (1->0)
	CLBLM_R_X3Y13 - SLICEM_X0.CLUT - INIT[00]
	Resource Design Name: Counter/count[4]_i_5
	INIT[00] bit altered for Counter/count[4]_i_5
	Affected Resources:
		Counter/count[4]_i_5

	Vivado Tcl Commands:
		select_objects [get_cells {Counter/count[4]_i_5}]

Bits: 1
Errors Found: 1 (100.0%)
```

The header immediately tells us that this is the first bit group provided in the list of fault bits. The report then tells us that BFAT has determined that some of the bits in the bit group are "significant bits" which affect the design if they are flipped.


The report then lists the bitstream address of the bit that BFAT determined to be sensitive, and whether its value flipped from a 1 to a 0 or vice versa. In this case it flipped from a 1 to a 0. It then reports a lot of information about the fault, so let's go through it one line at a time:

1. The tile, BEL, and function of the bit within the BEL. We can see that the bit affected a LUT in a CLB tile.
2. The name of the resource in the design that is mapped onto this LUT
3. The fault message, stating that the initialization bit for the resource is affected by this bit upset. This fault message is different for different kinds of faults, which we will get to later.
4. The affected design resources from this bit upset. This may seem redundant as this was already stated in (2), but for other kinds of faults this section can provide more useful information
5. Tcl command to select the design resource in Vivado

The report then lists some basic statistics about the bits in the bit group (how many bits are in the group, the proportion of bits that cause errors)

---

### Open in a net:

```
======================================================================
                             Bit Group 2
======================================================================

Significant Bits:
------------------------------
bit_00400107_024_10 (1->0)
	INT_L_X2Y12 - ER1BEG1 2-20 Routing Mux - Column Bit
	Resource Design Name: INT_L_X2Y12/ER1BEG1
	Opens created for net(s): btnc_IBUF
	Affected PIPs:
		SL1END0->>ER1BEG1 (deactivated)
	Affected Resources:
		Counter/FSM_sequential_cs[0]_i_1
		Counter/FSM_sequential_cs[1]_i_1
		Counter/FSM_sequential_cs[2]_i_1
		Counter/FSM_sequential_cs_reg[0]
		Counter/FSM_sequential_cs_reg[1]
		Counter/FSM_sequential_cs_reg[2]
		Counter/count[7]_i_5

	Vivado Tcl Commands:
		select_objects [get_pips {INT_L_X2Y12/INT_L.SL1END0->>ER1BEG1}]
		select_objects [get_nets {btnc_IBUF}]
		select_objects [get_cells {Counter/FSM_sequential_cs[0]_i_1 Counter/FSM_sequential_cs[1]_i_1 Counter/FSM_sequential_cs[2]_i_1 Counter/FSM_sequential_cs_reg[0] Counter/FSM_sequential_cs_reg[1] Counter/FSM_sequential_cs_reg[2] Counter/count[7]_i_5}]

Bits: 1
Errors Found: 1 (100.0%)
```

Once again, the header states we are now looking for information from bit group 2, and significant bits were found in the bit group. This is a different kind of fault though:

1. The affected tile is an INT (interconnect) tile. In this case, the affected part is not a BEL, but one of the routing muxes that controls which signals should be selected at an output node of a switchbox. Routing muxes in 7-Series parts use a column/row bit encoding for selecting input signals, so BFAT determined that this is a row bit.
2. The name of the routing mux
3. The fault message, stating that this bit upset created an open within the specified design net.
4. The pip which was deactivated by this bit upset, causing the open within the specified net
5. The affected resources from the net being cut off. BFAT will trace the path that the net would have taken through the FPGA in order to track which design resources were affected by this event.
6. Tcl commands to select the pip which was deactivated, the net which was opened, and the downstream affected resources

---

### Short between two nets:

```
======================================================================
                             Bit Group 3
======================================================================

Significant Bits:
------------------------------
bit_00400193_028_22 (0->1)
	INT_R_X3Y14 - BYP_ALT4 5-24 Routing Mux - Row Bit
	Resource Design Name: INT_R_X3Y14/BYP_ALT4
	Shorts formed between net(s): Counter/Q[5] (initially connected), Counter/Q[7]
	Affected PIPs:
		NR1END1->>BYP_ALT4 (activated)
	Affected Resources:
		Counter/count_reg[7]_i_7

	Vivado Tcl Commands:
		select_objects [get_pips {INT_R_X3Y14/INT_R.NR1END1->>BYP_ALT4}]
		select_objects [get_nets {Counter/Q[5] Counter/Q[7]}]
		select_objects [get_cells {Counter/count_reg[7]_i_7}]

Bits: 1
Errors Found: 1 (100.0%)
```

This type of fault is similar to an open within a net. However, this bit being activated actually caused a routing mux to select two different, distinct signals at once, creating a short between two nets.

BFAT will keep track of the net that was originally connected to the routing mux before the short caused by the bit upset with that "initially connected" marker.

---

### Short between a net and an unconnected node:

```
======================================================================
                             Bit Group 4
======================================================================

Significant Bits:
------------------------------
bit_0040010e_024_11 (0->1)
	INT_L_X2Y12 - ER1BEG1 2-20 Routing Mux - Row Bit
	Resource Design Name: INT_L_X2Y12/ER1BEG1
	Shorts formed between net(s): Unconnected Wire(LOGIC_OUTS_L4), btnc_IBUF (initially connected)
	Affected PIPs:
		LOGIC_OUTS_L4->>ER1BEG1 (activated)
	Affected Resources:
		Counter/FSM_sequential_cs[0]_i_1
		Counter/FSM_sequential_cs[1]_i_1
		Counter/FSM_sequential_cs[2]_i_1
		Counter/FSM_sequential_cs_reg[0]
		Counter/FSM_sequential_cs_reg[1]
		Counter/FSM_sequential_cs_reg[2]
		Counter/count[7]_i_5

	Vivado Tcl Commands:
		select_objects [get_pips {INT_L_X2Y12/INT_L.LOGIC_OUTS_L4->>ER1BEG1}]
		select_objects [get_nets {btnc_IBUF}]
		select_objects [get_cells {Counter/FSM_sequential_cs[0]_i_1 Counter/FSM_sequential_cs[1]_i_1 Counter/FSM_sequential_cs[2]_i_1 Counter/FSM_sequential_cs_reg[0] Counter/FSM_sequential_cs_reg[1] Counter/FSM_sequential_cs_reg[2] Counter/count[7]_i_5}]

Bits: 1
Errors Found: 1 (100.0%)
```

This is another example of a short in an interconnect tile. However, instead of a short between two nets, this upset caused a routing mux to select both a net and an input wire without a net mapped onto it. These are referred to as "unconnected wires".

---

### Undefined bit

```
======================================================================
                             Bit Group 5
======================================================================

Undefined Bits:
------------------------------
bit_0000002a_000_00
	Potential Affected Resources:
		No potential tiles found
Bits: 1
Errors Found: 0 (0.0%)
```

In this bit group, a bitstream address was provided for which a resource could not be found in the Project X-Ray database. BFAT classifies these as "undefined bits". Typical analysis cannot be performed for undefined bits, though BFAT will still attempt to find any tiles and resources that the bit *might* be related to. In this case no possible related tiles could be found, however.

---

### Errorless bits

```
======================================================================
                             Bit Group 6
======================================================================

Errorless Bits:
------------------------------
bit_0000051a_093_15: CLBLM_L_X10Y96 - SLICEL_X1.ALUT - INIT[00] - NA
bit_00000215_087_07: INT_L_X4Y93 - BYP_ALT0 5-24 Routing Mux - Row Bit - INT_L_X4Y93/BYP_ALT0

Bits: 2
Errors Found: 0 (0.0%)
```

In this last bit group, two bits were provided. However, BFAT has not detected that either of these bits will cause an error in the design. The first bit is an initialization bit for a LUT in a CLB tile but there are no cells placed onto the LUT, so that bit being upset is unlikely to affect the design. Similarly, the second bit is a routing bit in an interconnect tile, however no nets are present in the tile. BFAT detected that no net shorts or opens would occur if the bit was flipped, so it is also unlikely to affect the design.

---

### Statistics Footer

```
======================================================================
                   Design modelled: counter_top.dcp
				Total time elapsed: 2.29 sec	(0 min)
----------------------------------------------------------------------

Bit Groups: 6
Bit Groups w/ Errors: 4 (66.67%)

Fault Bits: 7
Routing Fault Bits: 4 (57.14%)
CLB Fault Bits: 2 (28.57%)
Unsupported Fault Bits: 0 (0.0%)
Unknown Fault Bits: 1 (14.29%)
Bits Driven High: 4 (57.14%)
Bits Driven Low: 2 (28.57%)

Found Errors: 4 (57.14%)
PIP Open Errors: 1 (14.29%)
PIP Short Errors: 2 (28.57%)
CLB Altered Bit Errors: 1 (14.29%)
```

At the bottom of the fault report, a list of statistics over the whole run of BFAT is given:
- `Bit Groups`: Number of bit groups in the input fault bit list
- `Bit Groups w/ Errors`: Number of bit groups which included bits for which an error was detected
- `Fault Bits`: Number of fault bits in the input fault bit list
- `Routing Fault Bits`: Number of fault bits which affected the routing switchboxes in INT tiles
- `CLB Fault Bits`: Number of fault bits which affected BELs in CLB tiles
- `Unsupported Fault Bits`: Number of bits for which further analysis is not supported by BFAT 
- `Unknown Fault Bits`: Number of fault bits whose function could not be determined
- `Bits Driven High`: Number of bits which, if flipped, change from a 0 to a 1
- `Bits Driven Low`: Number of bits which, if flipped, change from a 1 to a 0
- `Found Errors`: Number of bits which, if flipped, are likely to cause an error in the design
- `PIP Open Errors`: Number of errors which deactivated a PIP and created an open within a net
- `PIP Short Errors`: Number of errors which activated a PIP and created a short within two nets (or a net and an unconnected node)
- `CLB Altered Bit Errors`: Number of bits that affect CLB tiles which are likely to cause an error