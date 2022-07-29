'''
    file_processing.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Supplementary python file for BFAT functions for processing
    the input files from the design and part database.
'''

import json
from lib.tile import XRAY_DB

#####################################################
#   Finding and Parsing in the Part tilegrid.json   #
#####################################################

def parse_tilegrid(part:str):
    '''
        Parses tilegrid.json file for FPGA parts from part database
            Arguments: String of part name
            Returns: Dict storing tilegrid info from part database
    '''

    part_file = get_part_tilegrid(part)

    tile_info = {}

    # Open part file and iterate through each line parsing in relevant data
    with open(part_file) as p_f:
        first_line = True
        start_tile = False
        curr_scope = 0
        bits_scope = -1
        tile_name = ''
        data = {'baseaddr' : [], 'frames' : [], 'offset' : [], 'words' : []}
        TILE_SCOPE = 2
        EXCLUDED_TILES = ['_UTURN', 'MONITOR_BOT', '_SING']

        # Pull relevant information out of each line and store it when necessary
        for line in p_f:          
            # Get tile name from first line of tile scope
            if start_tile:
                tile_name = line.strip().split(':')[0]
                tile_name = tile_name[1:-1]
                start_tile = False
            
            # Raise start_tile flag on first line
            if first_line:
                start_tile = True
                first_line = False
            
            # Increment curr_scope counter when scope changes
            if '{' in line:
                curr_scope += 1
            # Decrement curr_scope counter when scope changes
            if '}' in line:
                curr_scope -= 1
            
            # Save tile information to data structure and
            # reset bits_scope when bits data block ends
            if curr_scope < bits_scope:
                keep_parse = True
                # Iterate through each excluded tile indicator segment and lower flag
                # if any match current tile
                for ex_tl_seg in EXCLUDED_TILES:
                    if ex_tl_seg in tile_name:
                        keep_parse = False
                        break
                
                # Save parsed tile information if not denied by excluded tile segments
                if keep_parse:
                    tile_info[tile_name] = data
                bits_scope = -1

            # Update bits_scope when "bits" block found
            if '"bits"' in line and curr_scope > TILE_SCOPE:
                bits_scope = curr_scope

            # Get data from address data block opening inside bits block
            if bits_scope > TILE_SCOPE and curr_scope > bits_scope:
                # Store cooresponding data from line in data dict
                if 'baseaddr' in line:
                    data['baseaddr'].append(int(get_tilegrid_val(line)[2:], 16))
                elif 'frames' in line:
                    data['frames'].append(int(get_tilegrid_val(line)))
                elif 'offset' in line:
                    data['offset'].append(int(get_tilegrid_val(line)))
                elif 'words' in line:
                    data['words'].append(int(get_tilegrid_val(line)))
            
            # Tile block has ended. Reset variables to init values and raise start_tile flag
            if curr_scope < TILE_SCOPE:
                bits_scope = -1
                data = {'baseaddr' : [], 'frames' : [], 'offset' : [], 'words' : []}
                tile_name = ''
                start_tile = True

    return tile_info

def get_part_tilegrid(part:str):
    '''
        Gets the tilegrid file path for the respective part
            Arguments: String of the part used to implement the design
            Returns: String of the file path to the tilegrid.json of the given part
    '''

    # Determine the architecture family and get the path to the part's tilegrid.json
    if 'xc7' in part:
        # Determine the family of the series 7 part
        if 'xc7a' in part:
            arch = "artix7"
        if 'xc7k' in part:
            arch = "kintex7"
        if 'xc7s' in part:
            arch = "spartan7"
        if 'xc7z' in part:
            arch = "zynq7"

        part_fam = part[0:4]
        # Iterate through each character in the part name to get the part size number
        for char in part[4:]:
            # Break loop before adding first non-numeric character if spartan7 or zynq7
            if (arch == "spartan7" or arch == "zynq7") and not str.isnumeric(char):
                break
            part_fam += char
            # Break loop after adding first non-numeric character if artix7 or kintex7
            if (arch == "artix7" or arch == "kintex7") and not str.isnumeric(char):
                break

        return f'{XRAY_DB}/{arch}/{part_fam}/tilegrid.json'

    else:
        raise ValueError

def get_tilegrid_val(line:str):
    '''
        Parses in the value for the element described on the current line of the
        tilegrid.json file.
            Arguments: String of the current line of the tilegrid.json file
            Returns: String or int of the value found on the line
    '''

    val_seg = line.split(':')[1].strip()

    # Remove comma at end of line if there is one
    if ',' in val_seg:
        val_seg = val_seg[0:-1]

    # Determine if the value is a string or int and get the information accordingly
    if '"' in val_seg:
        value = val_seg[1:-1]
    else:
        value = val_seg.strip()

    return value


####################################
#   Parsing Fault Bit List Files   #
####################################

def parse_fault_bits(json_file:str):
    '''
        Fault bit parsing from a json file
            Arguments: String of file path to .json file
            Returns: Dict storing fault bits passed in organized by bit group
    '''

    # Load json file
    with open(json_file) as f:
        bit_groups_json = json.load(f)

    # Convert to dictionary 
    bit_groups = {}
    for index, bit_group in enumerate(bit_groups_json, 1):
        # Convert bit addresses to all lowercase
        lower_bit_group = [[num.lower() for num in bit] for bit in bit_group]
        bit_groups[index] = lower_bit_group

    return bit_groups


####################################
#    Parsing Design Bits Files     #
####################################

def parse_design_bits(bits_file:str):
    '''
        Parses in the design's .bits file
            Arguments: The .bits file path provided to the program
            Returns: List of all bits in the .bits file as arrays of separated address elements
    '''

    bits = []

    # Open the .bits file for the design bits
    with open(bits_file) as b_f:
        # Iterate through each line of the .bits file to get the bit information
        for line in b_f:
            bits.append(line.strip())

    return bits