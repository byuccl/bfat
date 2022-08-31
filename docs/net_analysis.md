# Net Sensitivity Analysis

In the `utils` directory you will find a script called `net_analysis.py` which can be used to retrieve all bits which affect the routing of the given net(s). This information can give users insight about which signals in the design are likely to be affected by bit upsets that cause opens and shorts in interconnect tiles.

---

## Input file format

The format that this script accepts as input is a simple line-seperated `.txt` file. Include the hierarchical names of each net to be anyalzed on seperate lines, like so:

```
module/net_1
module/net_2
```

A design checkpoint `.dcp` post-implementation is also required as an input to the script.

---

## How to use

1. Activate the BFAT virtual environment and source Vivado
2. Run the script with the following command:

```
python3 analyze_nets.py <dcp_file> <nets_file> 
```
* The `-of` flag can be optionally used to specify the filename and path of the output file

A `.txt` file containing the results of the analysis will be generated in the same directory that the script was run in with a generated name (or with the name specified with the `-of` flag)

---

## Output file format

Here is an example entry in the analysis report for a net:

```
clk_IBUF_BUFG
Pips: (2)
	INT_R_X3Y13/INT_R.GCLK_B11->>CLK0 - CLK0 5-16 Routing Mux:
		Row Bits: ['bit_00400180_026_26', 'bit_00400181_026_28', 'bit_00400180_026_21', 'bit_00400180_026_22']
		Column Bits: ['bit_00400180_026_25', 'bit_00400181_026_20', 'bit_00400181_026_21', 'bit_00400181_026_24']

	INT_R_X3Y12/INT_R.GCLK_B11->>CLK1 - CLK1 5-16 Routing Mux:
		Row Bits: ['bit_00400180_024_30', 'bit_00400180_024_23', 'bit_00400181_024_22', 'bit_00400181_024_25']
		Column Bits: ['bit_00400180_024_27', 'bit_00400180_024_29', 'bit_00400181_024_26', 'bit_00400181_024_29']

Total config bits: 16
```

The net given is a clock signal which uses two interconnect pips in total. Included in the analysis is the name of each pip, along with the name and type of the pip's routing mux. Lastly, the relevant configuration bits for the routing mux are given, sorted by their row/column encoding.

At the end of the net's section in the report, the total number of unique bits which affect the net's routing is given.