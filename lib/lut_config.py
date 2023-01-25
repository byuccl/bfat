'''
    fault_analysis.py
    BYU Configurable Computing Lab (CCL): BFAT project 2022

    Supplementary python file for BFAT functions for analyzing how
    individual LUT configuration memories are affected by bit upsets
'''

from lib.design_query import DesignQuery
from math import log

class LUT:
    '''
        Stores configuration information for a given instanced LUT and how it
        changes given an upset in its INIT string
            Attributes:
                cell - string of the cell's name

                pins - dict that maps the BEL pins to cell pins

                init_str - string of the hex init word for the cell

                upset_bits - list of indices in the init string to upset

                init_str_upset - string of the binary init word for the cell, post-upset
    '''

    def __init__(self, cell:str, design:DesignQuery):
        self.cell = cell
        self.num_bel_inputs = 0
        self.pins = {}
        self.cell_init_str = 'NA'
        self.bel_init_str = 'NA'
        self.upset_bits = []
        self.cell_init_str_upset = 'NA'
        self.bel_init_str_upset = 'NA'
        self.populate_lut(design)

    def populate_lut(self, design:DesignQuery):
        '''
            Populates object with basic information about the cell and the LUT it
            is mapped to using design information
                Arguments: design query object
        '''

        self.cell_init_str = design.get_cell_init_str(self.cell)
        self.retrieve_pin_info(design)
        self.calculate_bel_init()

    def retrieve_pin_info(self, design:DesignQuery):
        '''
            Populates members related to the BEL pins and cell pins
                Arguments: design query object
        '''

        self.pins = design.get_cell_pins(self.cell)
        sibling_cell = 'NA'

        # Search the cells database for the current cell and retrieve its
        # sibling cell (if it exists). A sibling cell is the cell that is
        # placed on the same LUT structure as the original cell, but the
        # not the same BEL (e.g. a cell on the LUT5 vs. a cell on the LUT6)
        for tile, sites in design.cells.items():
            for site, bels in sites.items():
                for bel, cell in bels.items():
                    if cell == self.cell and 'LUT' in bel:
                        self.num_bel_inputs = int(bel[1])

                        # Determine the current cell's sibling BEL
                        sibling_bel = list(bel)
                        sibling_bel[1] = '5' if bel[1] == '6' else '6'
                        sibling_bel = "".join(sibling_bel)
                        
                        # Get the sibling BEL's cell if it has one
                        if sibling_bel in bels:
                            sibling_cell = bels[sibling_bel]
                        break
                else:
                    continue
                break
            else:
                continue
            break

        # If a sibling cell was found, note its used BEL pins
        if sibling_cell != 'NA':
            sibling_cell_pins = design.get_cell_pins(sibling_cell)

            # Add sibling used input bel pins to current cell bell pins
            for sibling_bp in sibling_cell_pins:
                if sibling_bp not in self.pins and 'O' not in sibling_bp:
                    self.pins[sibling_bp] = 'USED_BY_SIBLING'

    def calculate_bel_init(self):
        '''
            Populates "bel_init_str" member by inferring the LUT memory configuration
            from the used BEL pins and the cell initialization string
                * "pins" and "cell_init_str" members must already be populated
        '''

        # The value in the bel init string with a given combination of high BEL
        # inputs is equal to the value in the cell init string with the
        # corresponding cell inputs being high

        # Int representation of the init strings
        cell_init_int, _ = init_str_to_int(self.cell_init_str)
        bel_init_int = 0

        # Iterate through the value of each possible input combinations to the BEL
        for bel_init_index in range(2**self.num_bel_inputs):
            cell_init_index = 0

            # Calculate the index of the cell init string that this index of the
            # BEL init string corresponds to
            for bel_pin in self.pins:
                # Ignore output pins
                if 'O' in bel_pin:
                    continue

                # Ignore pins only used by the sibling cell
                if self.pins[bel_pin] == 'USED_BY_SIBLING':
                    continue

                # If this BEL pin is high in this input combination, set the bit in
                # in the cell init index corresponding to this BEL pin
                if bel_init_index & (1 << (int(bel_pin[-1], 10) - 1)):
                    cell_init_index |= 1 << int(self.pins[bel_pin][-1], 10)

            # Modify the bel init string if the corresponding value in the cell
            # init string is high
            if cell_init_int & (1 << cell_init_index):
                bel_init_int |= 1 << bel_init_index

        # Format the init string and populate the member variable
        self.bel_init_str = int_to_init_str(bel_init_int, self.num_bel_inputs)

    def simulate_upset(self, upset_bits:list):
        '''
            Simulates upsets at the given indices of the BEL init string
            by populating the relevant member variables
                Arguments: list of indices in the init string to upset
        '''

        bel_init_int, _ = init_str_to_int(self.bel_init_str)
        cell_init_int, cell_num_inputs = init_str_to_int(self.cell_init_str)
        
        # LUT letter identifier in SLICE (A, B, C, or D)
        lut_id = list(self.pins.keys())[0][0]

        # Flip each upset bit in the BEL init string
        for bel_upset_bit in upset_bits:
            # Invert the bit if the index is valid
            if bel_upset_bit <= 2**self.num_bel_inputs:
                bel_init_int ^= 1 << bel_upset_bit

            # Configuration of input states corresponding to this bit
            bit_input_config = {}

            # Determine the state of each LUT input for this bit
            for bel_input_num in range(1,7):
                bel_pin = f'{lut_id}{bel_input_num}'
                input_mask = 1 << (bel_input_num - 1)
                bit_input_config[bel_pin] = (bel_upset_bit & input_mask) == input_mask

            # Flip the corresponding bit in the cell init string if the bit
            # has all unused inputs to be high (the default value)
            if all([bit_input_config[pin] for pin in bit_input_config if pin not in self.pins]):
                cell_upset_bit = 0

                # Construct the address for the corresponding bit in the cell init str
                for bel_pin in self.pins:
                    # Ignore output pins and pins only used by sibling cell
                    if 'O' in bel_pin or self.pins[bel_pin] == 'USED_BY_SIBLING':
                        continue
                    cell_input_num = int(self.pins[bel_pin][-1], 10)
                    cell_upset_bit |= bit_input_config[bel_pin] << cell_input_num

                # Invert the bit in the cell init string
                cell_init_int ^= 1 << cell_upset_bit

        self.upset_bits = upset_bits
        self.bel_init_str_upset = int_to_init_str(bel_init_int, self.num_bel_inputs)
        self.cell_init_str_upset = int_to_init_str(cell_init_int, cell_num_inputs)

############################################################
#   Functions for Conversion Between Init String Formats   #
############################################################

def init_str_to_int(init_str:str):
    '''
        Converts a hexadecimal init string to an integer
            Arguments: hexadecimal init string - "{num_bits}'h{hex_string}"
            Returns: int of the init string, int of the number of inputs
    '''

    init_str_int = int(init_str.split('h')[-1], 16)
    num_inputs = int(log(int(init_str.split("'")[0], 10), 2))

    return init_str_int, num_inputs

def int_to_init_str(init_str_int:int, num_inputs:int):
    '''
        Converts the integer representation of an init string to a hex string
            Arguments: int of the init string, int of the number of inputs
            Returns: hexadecimal init string - "{num_bits}'h{hex_string}"
    '''

    num_bits = 2**num_inputs
    return f"{num_bits}'h" + hex(init_str_int).replace('0x', '').rjust(int(num_bits/4), '0').upper()