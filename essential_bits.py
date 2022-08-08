'''
    essential_bits.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    Parses a 

    Arguments:
        - 

    Returns:
        - output file (.json) of the generated fault bit list
'''

from pickle import FRAME
from bitread import get_frame_list
import json
import random


def parse_ebd_file(eb_file:str):
    '''
        Parses in bit address information from the given essential bits file
            Arguments: path to the essential bits file
            Returns: list of all bits in the file
    '''

    essential_bits = []
    part = 'NA'

    # Open the essential bits file
    with open(eb_file) as eb_f:

        in_header = True
        # Read through the header of the file
        while in_header:
            # Keep track of previous line
            prev_line = eb_f.tell()

            # Read one line from the file
            line = eb_f.readline()

            # Get the part name from the header
            if line.split()[0] == 'Part:':
                part = 'xc' + line.split()[-1] + '-1'

            # Exit loop when binary section of file is reached
            if line.strip().isnumeric():
                # Move back one line so first binary line is not missed in next loop
                eb_f.seek(prev_line)
                in_header = False
        


        # Make sure part was found in the header
        if part == 'NA':
            print('Unrecognized file format, part name could not be found in header')
            return []

        frame_list = get_frame_list(part)

        # The number of words in a frame
        FRAME_LENGTH = 101

        # Keep track of the previous frame so a row change can be detected
        prev_frame = frame_list[0].copy()

        # The first frame in a .ebd file is a dummy frame, skip it
        for _ in range(FRAME_LENGTH):
            eb_f.readline()

        # Iterate through each frame in the frame list
        for frame in frame_list:

            # Skip 2 frames worth of bits whenever the row changes
            if prev_frame[1][17:23] != frame[1][17:23]:
                for _ in range(FRAME_LENGTH*2):
                    eb_f.readline()

             # Iterate for the number of words specified for this architecture's frame
            for word_offset in range(FRAME_LENGTH):

                word = eb_f.readline().strip()[::-1]
                # Iterate through each bit in the word
                for bit_offset, bit in enumerate(word):
                    # The first 13 bits of the 51st word per frame are reserved in series-7
                    in_clock_row_bits = (word_offset == 50 and bit_offset <= 12)

                    # Add every high bit to the bits list
                    if bit == '1' and not in_clock_row_bits:
                        word_offset_str = str(word_offset).rjust(3, "0")
                        bit_offset_str = str(bit_offset).rjust(2, "0")
                        essential_bits.append([frame[0], word_offset_str, bit_offset_str])

            prev_frame = frame.copy()

    return essential_bits




# TODO: Remove references to "ll"
def write_bit_list(essential_bits:list, num_bits:int, ebd_file:str):
    '''
        Writes a file containing the specified number of bits from the .ebd file
            Arguments: list of bits addresses from file, number of bits to include, file
                       path of the essential bits file
            Returns: Output .json file with the fault bit addresses
    '''

    fault_bits = []

    # Check that there is more bits in the ll file than the specified number
    if num_bits > len(essential_bits):
        print(f"There is less than {num_bits} useable bits in the provided .ll file.")
        num_bits = len(essential_bits)

    # Add the specified number of bits to the fault bits list
    while len(fault_bits) < num_bits: 
        # Get a random bit and add it to the fault bit list
        rand_bit = random.choice(essential_bits)
        fault_bits.append([rand_bit])

        # Remove the bit to avoid duplicates
        essential_bits.remove(rand_bit)

    fault_bits_json = json.dumps(fault_bits, indent=4)   

    # Generate file name for the fault bit list
    ebd_filename = ebd_file.split('/')[-1].split('.')[0]
    fault_bits_path = f'{ebd_filename}_ebd_sample_bits.json'

    # Write the fault bit list in a json format
    with open(fault_bits_path, 'w') as bits_f:
        bits_f.write(fault_bits_json)


def main():
    '''
        Main function: Creates a fault bit list based on the bits in the provided .ebd file
    '''

    # Gathers all bits from the .ebd file
    essential_bits = parse_ebd_file(ARGS.ebd_file)

    # Write the specified number of bits to a .json file
    write_bit_list(essential_bits, ARGS.num_bits, ARGS.ebd_file)

    


if __name__ == '__main__':
    import argparse

    PARSER = argparse.ArgumentParser(description='Parses in an essential bits file (.ebd) '
                                    + 'and populates a fault bit list with bits from the file')
    PARSER.add_argument('ebd_file', help='Essential bits file from Vivado')
    PARSER.add_argument('num_bits', type=int, help='The number of randomly selected bits from '
                        + 'the file to include in the fault bit list')
    ARGS = PARSER.parse_args()

    main()