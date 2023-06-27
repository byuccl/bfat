The `bfat/reports` directory is where the tool will write fault reports when using the `scaffold` subcommand. This scaffold is intended to help with organization when working with many designs and/or fault bit lists.

When running `bfat.py` with the `scaffold` subcommand, a new folder will be created in this directory for the design if one has not been created already. The name of this folder will match the name of the design folders in the `designs` and `fault_bits` directories. The name of the fault report will match the fault bit list `.json` file by default, but can be manually specified with the `-of` optional argument when running `bfat.py`.

For more information on what fault reports will look like, see [here](../docs/fault_report.md).