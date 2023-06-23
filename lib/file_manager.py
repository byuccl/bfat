import sys

# Add the parent directory of this file (bfat root) to the interpreter's path
sys.path.append(f'{"/".join(__file__.split("/")[:-1])}/..')

import os
import pathlib
import json
import bitread
from lib.design_query import DesignQuery, VivadoQuery
from rpd_query import RpdQuery

####################################
#        Getting file paths        #
####################################

def get_bitstream_path(design:str) -> pathlib.Path:
    """Retrieves the path to the bitstream for the given design. Bitstreams
    should be located in "bfat/designs/{DESIGN_NAME}/" and have the .bit
    extension

    Args:
        design (str): name of the design directory where the bitstream is stored

    Raises:
        Exception: Raised if no files with the .bit extension are found
        Exception: Raised if multiple files with the .bit extension are found

    Returns:
        pathlib.Path: path to the bitstream
    """
    
    design_dir = pathlib.Path(__file__).parent.parent / "designs" / design
    
    bitstreams = []
    
    for file in os.listdir(design_dir):
        if file.endswith(".bit"):
            bitstreams.append(file)
            
    if len(bitstreams) == 0:
        raise Exception(f"No files with the .bit extension in {design_dir}")
    if len(bitstreams) > 1:
        raise Exception(f"Multiple files with the .bit extension in {design_dir}: {bitstreams}")
    
    return design_dir / bitstreams[0]

def get_bits_file_path(design:str) -> pathlib.Path:
    """Retrieves the path to the bits file for the given design. A bits file
    is automatically generated after get_design_bits() is called on a
    design for the first time. The file is placed in
    "bfat/designs/{DESIGN_NAME}/" and will have the .bits extension

    Args:
        design (str): name of the design directory where the bits file is stored

    Raises:
        Exception: Raised if no files with the .bits extension are found
        Exception: Raised if multiple files with the .bits extension are found

    Returns:
        pathlib.Path: path to the bits file
    """
    
    design_dir = pathlib.Path(__file__).parent.parent / "designs" / design
    
    bits_files = []
    
    for file in os.listdir(design_dir):
        if file.endswith(".bit"):
            bits_files.append(file)
            
    if len(bits_files) == 0:
        raise Exception(f"No files with the .bits extension in {design_dir}")
    if len(bits_files) > 1:
        raise Exception(f"Multiple files with the .bits extension in {design_dir}: {bits_files}")

def get_checkpoint_path(design:str) -> pathlib.Path:
    """Retrieves the path to the Vivado checkpoint file for the given design.
    Checkpoints should be located in "bfat/designs/{DESIGN_NAME}/" and have the
    .dcp extension

    Args:
        design (str): name of the design directory where the checkpoint is stored

    Raises:
        Exception: Raised if no files with the .dcp extension are found
        Exception: Raised if multiple files with the .dcp extension are found

    Returns:
        pathlib.Path: path to the checkpoint
    """
    
    design_dir = pathlib.Path(__file__).parent.parent / "designs" / design
    
    dcps = []
    
    for file in os.listdir(design_dir):
        if file.endswith(".dcp"):
            dcps.append(file)
            
    if len(dcps) == 0:
        raise Exception(f"No files with the .dcp extension in {design_dir}")
    if len(dcps) > 1:
        raise Exception(f"Multiple files with the .dcp extension in {design_dir}: {dcps}")
    
    return design_dir / dcps[0]

def get_fault_bits_path(design:str, fault_bits_name:str) -> pathlib.Path:
    """Retrieves the path to the JSON fault bits file matching the given
    design and filename. The file should be located at
    bfat/fault_bits/{DESIGN_NAME}/{FAULT_BITS_FILENAME}.

    Args:
        design (str): name of the design directory where the file is stored
        fault_bits_name (str): name of the JSON file containing the fault bits

    Raises:
        Exception: Raised if the file is not found in the expected location

    Returns:
        pathlib.Path: path to the fault bits file
    """

    
    fault_bits_path = pathlib.Path(__file__).parent.parent / "fault_bits" / design / fault_bits_name
    
    if not os.path.exists(fault_bits_path):
        raise Exception(f"{fault_bits_path} not found")
    
    return fault_bits_path

####################################
#              Parsing             #
####################################

def get_design_bits(design:str) -> list:
    """Parses the design bitstream to get a list of all bit addresses
    whose value is "1". To save time on future runs of this function,
    a .bits file is written for the design containing this list of
    high bits. If a .bits file is found, that will be read instead
    of reading through the whole bitstream.
    
    Bitstreams and .bits files are expected to be found in
    "bfat/designs/{DESIGN_NAME}/"

    Args:
        design (str): name of the design directory where the bitstream is stored

    Returns:
        list: addresses of every bit whose value is "1"
    """
    
    design_bits : list = []

    # Attempt to parse a .bits file
    try:
        bits_file_path = get_bits_file_path(design)
        with open(bits_file_path) as b_f:
            # Iterate through each line of the .bits file to get the bit information
            for line in b_f:
                design_bits.append(line.strip())
    
    # .bits file doesn't exist, read the bitstream instead
    except:
        bitstream_path = get_bitstream_path(design)
        design_bits = bitread.get_high_bits(str(bitstream_path))
        
        # Write a .bits file for the future
        with open(f'{bitstream_path}s', "w") as bits_file:
            for bit in design_bits:
                bits_file.write(bit + "\n")
        
    return design_bits

def get_design_query(design:str, use_rpdquery:bool = False) -> DesignQuery:
    """Creates a DesignQuery from the Vivado checkpoint file for the given design.

    Args:
        design (str): name of the design directory where the dcp is stored
        use_rpdquery (bool, optional): flag indicating that RapidWright should be
        used for the design query instead of Vivado. Defaults to False.

    Returns:
        DesignQuery: DesignQuery (either VivadoQuery or RpdQuery) for the design
    """
    
    dcp_path = get_checkpoint_path(design)
    
    if use_rpdquery:
        design = RpdQuery(dcp_path)
    else:
        design = VivadoQuery(dcp_path)
        
    return design

def get_fault_bits(design:str, fault_bits_name:str) -> dict:
    """Retrieves the the JSON fault bits file matching the given design
    and filename. The file should be located at
    bfat/fault_bits/{DESIGN_NAME}/{FAULT_BITS_FILENAME}.

    Args:
        design (str): name of the design directory where the file is stored
        fault_bits_name (str): name of the JSON file containing the fault bits

    Returns:
        dict: stores fault bits passed in organized by bit group
    """
    
    fault_bits_path = get_fault_bits_path(design, fault_bits_name)

    # Load json file
    with open(fault_bits_path) as f:
        bit_groups_json = json.load(f)

    # Convert to dictionary 
    bit_groups = {}
    for index, bit_group in enumerate(bit_groups_json, 1):
        bit_group_format = []

        # Convert bit addresses to lowercase and zero fill
        for bit in bit_group:
            frame_addr = bit[0].lower().zfill(8)
            word_offset = bit[1].zfill(3)
            bit_offset = bit[2].zfill(2)

            bit_group_format.append([frame_addr, word_offset, bit_offset])

        # Add formatted bit group to the dictionary
        bit_groups[index] = bit_group_format

    return bit_groups
