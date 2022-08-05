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
bit_00001fa2_066_31 (0->1)
	CLBLM_R_X63Y182 - SLICEM_X0.DLUT - INIT[00]
	Resource Design Name: VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw128_Ood/cores_0_cpu_logic_cpu/IBusCachedPlugin_cache/decode_to_execute_SRC2[17]_i_6_TMR_2
	INIT[00] bit altered for VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw128_Ood/cores_0_cpu_logic_cpu/IBusCachedPlugin_cache/decode_to_execute_SRC2[17]_i_6_TMR_2
	Affected Resources:
		VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw128_Ood/cores_0_cpu_logic_cpu/IBusCachedPlugin_cache/decode_to_execute_SRC2[17]_i_6_TMR_2

	select_objects [get_cells {VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw128_Ood/cores_0_cpu_logic_cpu/IBusCachedPlugin_cache/decode_to_execute_SRC2[17]_i_6_TMR_2}]

Bits: 1
Errors Found: 1 (100.0%)
```

The header immediately tells us that this is the first bit group provided in the list of fault bits. The report then tells us that BFAT has determined that some of the bits in the bit group are "significant bits" which affect the design if they are flipped.


The report then lists the bitstream address of the bit that BFAT determined to be sensitive, and whether its value flipped from a 1 to a 0 or vice versa. In this case it flipped from a 1 to a 0. It then reports a lot of information about the fault, so let's go through it one line at a time:

1. The tile, BEL, and function of the bit within the BEL. We can see that the bit affected a LUT in a CLB tile.
2. The name of the resource in the design that is mapped onto this LUT
3. The fault message, stating that the initialization bit for the resource is affected by this bit upset. This fault message is different for different kinds of faults, which we will get to later.
4. The affected design resources from this bit upset. This will likely seem redundant as this was already stated in step 2, but for other kinds of faults this section can provide more useful information
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
bit_00421b8b_054_19 (1->0)
	INT_R_X55Y76 - WR1BEG_S0 2-20 Routing Mux - Column Bit
	Resource Design Name: INT_R_X55Y76/WR1BEG_S0
	Opens created for net(s): builder_sdcore_crc16inserter_state_TMR_2
	Affected PIPs:
		NR1END3->>WR1BEG_S0 (deactivated)
	Affected Resources:
		ODDR_6_i_4_TMR_2

	select_objects [get_pips {INT_R_X55Y76/INT_R.NR1END3->>WR1BEG_S0}]
	select_objects [get_nets {builder_sdcore_crc16inserter_state_TMR_2}]
	select_objects [get_cells {ODDR_6_i_4_TMR_2}]

Bits: 1
Errors Found: 1 (100.0%)
```

Once again, the header states we are now looking for information from bit group 2, and significant bits were found in the bit group. This is a different kind of fault though:

1. The affected tile is an INT (interconnect) tile. In this case, the affected part is not a BEL, but one of the routing muxes that controls which signals should be selected at an output node of a switchbox. Routing muxes in 7-Series parts use a column/row bit encoding for selecting input signals, so BFAT determined that this is a row bit.
2. The name of the routing mux
3. The fault message, stating that this bit upset created an open within the specified design net.
4. The pip which was deactivated by this bit upset, causing the open within the specified net
5. The affected resources from the net being cut off. BFAT will trace the path that the net would have taken through the FPGA in order to track which design resources were affected by this event.
6. Tcl command to select the pip which was deactivated
7. Tcl command to select the net which was opened
8. Tcl command to select all of the design elements which were found during the trace of this net

---

### Short between two nets:

```
======================================================================
                             Bit Group 3
======================================================================

Significant Bits:
------------------------------
bit_00421b88_054_18 (0->1)
	INT_R_X55Y76 - WR1BEG_S0 2-20 Routing Mux - Column Bit
	Resource Design Name: INT_R_X55Y76/WR1BEG_S0
	Shorts formed between net(s): builder_sdcore_crc16inserter_state_TMR_2, ODDR_6_i_8_n_0_TMR_0
	Affected PIPs:
		WR1END3->>WR1BEG_S0 (activated)
	Affected Resources:
		ODDR_6_i_4_TMR_2

	select_objects [get_pips {INT_R_X55Y76/INT_R.WR1END3->>WR1BEG_S0}]
	select_objects [get_nets {ODDR_6_i_8_n_0_TMR_0 builder_sdcore_crc16inserter_state_TMR_2}]
	select_objects [get_cells {ODDR_6_i_4_TMR_2}]

Bits: 1
Errors Found: 1 (100.0%)
```

This type of fault is similar to an open within a net. However, this bit being activated actually caused a routing mux to select two different, distinct signals at once, creating a short between two nets.

---

### Short between a net and an unconnected node:

```
======================================================================
                             Bit Group 4
======================================================================

Significant Bits:
------------------------------
bit_00421b8e_054_19 (0->1)
	INT_R_X55Y76 - WR1BEG_S0 2-20 Routing Mux - Row Bit
	Resource Design Name: INT_R_X55Y76/WR1BEG_S0
	Shorts formed between net(s): Unconnected Node(LOGIC_OUTS7), builder_sdcore_crc16inserter_state_TMR_2
	Affected PIPs:
		LOGIC_OUTS7->>WR1BEG_S0 (activated)
	Affected Resources:
		ODDR_6_i_4_TMR_2

	select_objects [get_pips {INT_R_X55Y76/INT_R.LOGIC_OUTS7->>WR1BEG_S0}]
	select_objects [get_nets {builder_sdcore_crc16inserter_state_TMR_2}]
	select_objects [get_cells {ODDR_6_i_4_TMR_2}]

Bits: 1
Errors Found: 1 (100.0%)
```

This is another example of a short in an interconnect tile. However, instead of a short between two nets, this upset caused a routing mux to select both a net and an input node without a net mapped onto it. These are referred to as "unconnected nodes".

---

### Undefined bit

```
======================================================================
                             Bit Group 5
======================================================================

Undefined Bits:
------------------------------
bit_0000002a_000_00

Bits: 1
Errors Found: 0 (0.0%)
```

In this bit group, a bitstream address was provided that does not exist, since the frame "0x0000002a" is not a defined frame address for the provided part. So, BFAT will classify it as an undefined bit and no analysis will be performed.

---

### Errorless bits

```
======================================================================
                             Bit Group 6
======================================================================

Errorless Bits:
------------------------------
bit_00000e9a_014_15: CLBLM_R_X29Y157 - SLICEL_X1.ALUT - INIT[00] - NA
bit_00000895_040_07: INT_R_X17Y170 - BYP_ALT0 5-24 Routing Mux - Row Bit - INT_R_X17Y170/BYP_ALT0

Bits: 2
Errors Found: 0 (0.0%)
```

In this last bit group, two bits were provided. However, BFAT has not detected that either of these bits will cause an error in the design. The first bit is an initialization bit for a LUT in a CLB tile but there are no cells placed onto the LUT, so that bit being upset is unlikely to affect the design. Similarly, the second bit is a routing bit in an interconnect tile, however no nets are present in the tile. BFAT detected that no net shorts or opens would occur if the bit was flipped, so it is also unlikely to affect the design.

---

### Statistics Footer

```
Bit Groups: 6
Bit Groups w/ Errors: 4 (66.67%)

Fault Bits: 7
Routing Fault Bits: 4 (57.14%)
CLB Fault Bits: 2 (28.57%)
Unsupported Fault Bits: 0 (0.0%)
Unknown Fault Bits: 1 (14.29%)
Bits Driven High: 5 (71.43%)
Bits Driven Low: 1 (14.29%)

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