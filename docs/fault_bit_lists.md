# Fault Bit Lists

One of the required inputs for BFAT is a fault bit list. This file will contain the addresses of the bits in your design's bitstream that you want to analyze. BFAT will determine the effects of an upset occurring at each of these addresses, whether the value of the bit flips from a 1 to a 0 or vice versa.

The standard file format that BFAT accepts is `.json`. Here is what a sample fault bit list would look like, with some indicators to emphasize how the data structure is organized.

```
[                                    <<- Fault Bit List
    [                                                 |
        [                                             |
            "00402b22",                               |
            "007",                                    |
            "15"                                      |
        ]                                             |
],                                                    |
    [                                <<- Bit Group    |
        [              <<- Single Bit Address    |    |
            "00002486",                     |    |    |
            "077",                          |    |    |
            "14"                            |    |    |
        ],             <<- Single Bit Address    |    |
        [                                        |    |
            "00002483",                          |    |
            "077",                               |    |
            "14"                                 |    |
        ]                                        |    |
    ],                               <<- Bit Group    |
        [                                             |
            "00002482",                               |
            "077",                                    |
            "15"                                      |
        ]                                             |
    ]                                                 |
]                                    <<- Fault Bit List
```

The whitespace style does not need to be identical, but the data structure must be the same "list of nested lists" format
- The outermost scope is a list of "bit groups" which will be analyzed one at a time.
- The next scope is a bit group, which is simply a collection of bits that you wish to test at the same time.
    - Much of the time you will only need to examine the effects of one bit upset at a time, but BFAT can also catch multi-bit upsets. These are errors that do occur when two separate bits are flipped at the same time when an error might not occur if the bits are flipped individually.
- The innermost scope represents a single bit address, which is divided into the hexadecimal frame address, the word offset within that frame, and the bit offset within the word.

BFAT will then go through each bit group and simulate the effects of flipping all of the bits in the group at once. The tool will then output the results of its analysis in a fault report, which is detailed in `fault_report.md`.