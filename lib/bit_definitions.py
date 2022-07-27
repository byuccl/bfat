'''
    bit_definitions.py
    BYU Configurable Computing Lab (CCL): BFAT project 2021-2022

    Supplementary python file for BFAT functions for defining individual
    bits in the bitstream and their corresponding roles/functions
'''

import copy
from lib.tile import Tile
from lib.design_query import DesignQuery

class FaultBit:
    '''
        Stores the information regarding a given fault bit
            Attributes:
                bit - the bit's name/bitstream address

                tile - the tile on the part that is influenced by the bit

                addr - the bit's address within the tile

                resource - the physical resource influenced by the bit

                design_name - the name of the resource in the design

                function - the function/role of the bit in the resource

                type - the type of Single Bit Upset (SBU) caused by the fault bit (driven high/low)

                fault - description of the fault in the design caused by the bit

                affected_rsrcs - the design resources affected by this bit and the fault it causes
    '''

    def __init__(self, bit_name):
        # Define and set default values for each class attribute
        self.bit = bit_name
        self.tile = 'NA'
        self.addr = 'NA'
        self.resource = 'NA'
        self.design_name = 'NA'
        self.function = 'NA'
        self.type = 'NA'
        self.fault = 'fault evaluation not yet supported for this bit'
        self.affected_rsrcs = ['No affected resources found']
        self.affected_pips = ['No affected pips found']

##################################################
#       Functions for Defining Fault Bits        #
##################################################

def def_fault_bits(bit_groups:dict, tilegrid:dict, tile_imgs:dict, design_bits:list, design:DesignQuery):
    '''
        Defines given fault bits in each bit group
            Arguments: Bit group information, dict of the part's tilegrid and the tile images,
                       a list of design bits, and a query for the design's data
            Returns: Dict storing the results of the fault bit evaluation
    '''

    fault_bits = {}

    # Iterate through each bit group
    for bit_group in bit_groups:
        int_tiles = {}
        # Get the information on each fault bit in the current bit group
        for fault_bit in bit_groups[bit_group]:
            # Create a new FaultBit object for the current fault bit
            bit_name = f'bit_{fault_bit[0]}_{fault_bit[1]}_{fault_bit[2]}'
            new_bit = FaultBit(bit_name)

            # Set the basic fault bit values based on the converted bit address if possible
            tile_addr = bit_tile_addr(fault_bit, tilegrid, tile_imgs)
            if tile_addr:
                new_bit = set_fault_bit_values(new_bit, tile_addr, tile_imgs, design_bits, design)

            # Add any fault bits for INT tiles a dictionary under its tile
            if 'INT_L' in new_bit.tile or 'INT_R' in new_bit.tile:
                try:
                    int_tiles[new_bit.tile].append(new_bit)
                except KeyError:
                    int_tiles[new_bit.tile] = []
                    int_tiles[new_bit.tile].append(new_bit)

            # Set the bit's fault description for CLB tiles
            if 'CLB' in new_bit.tile:
                if new_bit.design_name == 'NA':
                    new_bit.fault = 'No instanced resource found for this bit'
                else:
                    new_bit.fault = f'{new_bit.function} bit altered for {new_bit.design_name}'

            # Add the new bit to the collection of fault bits
            fault_bits[new_bit.bit] = copy.deepcopy(new_bit)
            del new_bit

        # Evaluate the faults occurring in each affected INT tile
        for tile in int_tiles:
            tile_obj = copy.deepcopy(tile_imgs[tile[0:tile.find('_X')]])
            tile_obj.name = tile
            affected_muxes = set()
            # Add each affected routing mux to a list
            for f_bit in int_tiles[tile]:
                affected_muxes.add(f_bit.resource.split(' ')[0])

            # Set each config bit in each routing mux to its original value in the design
            for mux in affected_muxes:
                # Set each config bit in each PIP in the current routing mux to its original value
                for mux_source in tile_obj.pips[mux]:
                    # Set each config bit in the PIP to its original value
                    for pip_bit in tile_obj.pips[mux][mux_source]:
                        cur_pip_bit = ''
                        # Get PIP config bit name independent of required value
                        if pip_bit[0] == '!':
                            cur_pip_bit = pip_bit[1:]
                        else:
                            cur_pip_bit = pip_bit

                        bitstream_addr = bit_bitstream_addr([tile, cur_pip_bit, 0], tilegrid)

                        # Set the current PIP bit's value to be 1 if it is in the design bits
                        if bitstream_addr in design_bits:
                            tile_obj.change_bit(cur_pip_bit, 1)

            tile_errors = eval_tile_errors(tile_obj, affected_muxes, int_tiles, design_bits, tilegrid, design)

            # Set the fault description of each fault bit associated with the current tile to the
            # message generated for its routing mux
            for tile_fbit in tile_errors:
                fault_bits[tile_fbit].fault = tile_errors[tile_fbit]['fault_desc']
                fault_bits[tile_fbit].affected_pips = tile_errors[tile_fbit]['affected_pips']

            del tile_obj

    fault_report = {}

    # Generate fault report with data from fault bit definitions
    for bit_group, group_bits in bit_groups.items():
        fault_report[bit_group] = {}

        # Add each fault bit in the bit group and its stored data to the fault report
        for fault_bit in group_bits:
            fbit_name = f'bit_{fault_bit[0]}_{fault_bit[1]}_{fault_bit[2]}'
            fbit = fault_bits[fbit_name]
            fault_report[bit_group][fbit_name] = [fbit.tile, fbit.resource, fbit.function, 
                                              fbit.design_name, fbit.type, fbit.fault,
                                              fbit.affected_rsrcs, fbit.affected_pips]

    return fault_report

def set_fault_bit_values(bit:FaultBit, tile_addr:list, tile_imgs:dict, design_bits:list, design:DesignQuery):
    '''
        Evaluates a fault bit and all the surrounding information to set its values except
        for its description. Takes in the fault_bit and returns an updated version of it.
            Arguments: FaultBit object, list of converted bit info, dict of tile images,
                       list of design bits, and a query for the design's data
            Returns: Updated fault bit object
    '''

    bit.tile, bit.addr, _ = tile_addr
    bit.resource, bit.function = associate_bit(tile_imgs, bit.tile[0:bit.tile.find('_X')], bit.addr)

    # Set the fault change depending on if the bit is included in the design bits
    if bit.bit in design_bits:
        bit.type = '1->0'
    else:
        bit.type = '0->1'

    bit.affected_rsrcs = []
    # Separate evaluation of fault values for bits from INT tiles and bits from other tiles
    if 'INT_L' in bit.tile or 'INT_R' in bit.tile:
        mux_name = bit.resource.split(' ')[0]
        bit.design_name = f'{bit.tile}/{mux_name}'
        net = design.get_net(bit.tile, mux_name)

        # Find the resources affected by the bit's net if it has one
        if net and net != 'NA':
            bit.affected_rsrcs.extend(design.get_affected_rsrcs(net, bit.tile, mux_name))
        else:
            bit.affected_rsrcs.append('No affected resources found')
    else:
        bit.design_name = get_bit_cell(bit.tile, bit.resource, design)
        bit.affected_rsrcs.append(bit.design_name)

    # Give default value for affected resources if no specific resources are found
    if not bit.affected_rsrcs or (len(bit.affected_rsrcs) <= 1 and 'NA' in bit.affected_rsrcs):
        bit.affected_rsrcs = ['No affected resources found']
    
    return bit

def associate_bit(tiles:dict, tile_name:str, addr:str):
    '''
        Associates the given bit with its tile, resources, and function if available.
            Arguments: Dict of tiles in the design and strings of the bit's tile
                       and the bit's address in the tile
            Returns: Strings of the bit's resource and its function within that resource
    '''

    rsrc = 'NA'
    fctn = 'NA'

    # Separate association of bits for INT tiles from bits from other tiles
    if 'INT_L' in tile_name or 'INT_R' in tile_name:
        # Check each routing mux in the tile for the given bit
        for mux in tiles[tile_name].resources:
            # Check if the bit is in the row bits or column bits for the routing mux
            # and set information accordingly
            if addr in tiles[tile_name].resources[mux].row_bits:
                rsrc = f'{mux} {tiles[tile_name].resources[mux].mux_type} Routing Mux'
                fctn = 'Row Bit'
                break
            elif addr in tiles[tile_name].resources[mux].col_bits:
                rsrc = f'{mux} {tiles[tile_name].resources[mux].mux_type} Routing Mux'
                fctn = 'Column Bit'
                break

    else:
        # Search for the bit in each resource for the given tile
        for curr_rsrc, rsrc_bits in tiles[tile_name].resources.items():
            # Search for the bit in the config bits of the current resource
            for curr_bit in rsrc_bits:
                # Check if the bit matches the given bit and set the information accordingly
                if curr_bit[0] == '!' and curr_bit[1:] == addr:
                    rsrc_elements = curr_rsrc.split('.')
                    rsrc = '.'.join(rsrc_elements[:-1])
                    fctn = rsrc_elements[-1]
                    break
                elif curr_bit[0] != '!' and curr_bit == addr:
                    rsrc_elements = curr_rsrc.split('.')
                    rsrc = '.'.join(rsrc_elements[:-1])
                    fctn = rsrc_elements[-1]
                    break

    return rsrc, fctn

def get_bit_cell(tile:str, resource:str, design:DesignQuery):
    '''
        Searches through the data structure of the design's cells and retrieves the one 
        associated with the bit if any exist.
            Arguments: Strings of the bit's tile and resource, and a query for the design's data
            Returns: String of the cell associated with the given bit's tile and resource
    '''

    cell = 'NA'
    if tile not in design.cells:
        design.query_cells(tile)

    # Find the cell if it is in a tile used in the design
    if tile in design.cells:
        rsrc_elements = resource.split('.')
        try:
            rsrc_root, rsrc_offset = rsrc_elements[0].split('_')
        except ValueError:
            return 'NA'
        rsrc_bel = rsrc_elements[-1]

        # Simplify the root for SLICE* sites
        if 'SLICE' in rsrc_root:
            rsrc_root = 'SLICE'

        rel_sites = []
        # Add all sites matching the root to a list
        for site in design.cells[tile]:
            if rsrc_root in site:
                rel_sites.append(site)

        # Check for a matching cell if any related sites are found
        if rel_sites:
            # Check for any cells matching the tile's relative offset
            if 'X1' in rsrc_offset:
                # Check each related site to see if it contains the sought resource
                for site in rel_sites:
                    site_x = int(site[site.find('X') + 1:site.find('Y')])
                    # Check that the site's offset is correct
                    if (site_x % 2) > 0:
                        rel_cells = []
                        # Check each bel in the current site to see if it matches the resource
                        for bel in design.cells[tile][site]:
                            # Edit BEL name for LUT resources
                            lut = 'NOT A LUT'
                            if 'LUT' in bel:
                                lut = f'{bel[0]}{bel[2:]}'

                                # If the BEL matches add the related cell to a list
                                if rsrc_bel == lut:
                                    rel_cells.append(design.cells[tile][site][bel])
                            elif rsrc_bel == bel:
                                rel_cells.append(design.cells[tile][site][bel])
                        cell = ', '.join(rel_cells)

            elif 'X0' in rsrc_offset:
                # Check each related site to see if it contains the sought resource
                for site in rel_sites:
                    site_x = int(site[site.find('X') + 1:site.find('Y')])
                    # Check that the site's offset is correct
                    if (site_x % 2) == 0:
                        rel_cells = []
                        # Check each bel in the current site to see if it matches the resource
                        for bel in design.cells[tile][site]:
                            # Edit BEL name for LUT resources
                            lut = 'NOT A LUT'
                            if 'LUT' in bel:
                                lut = f'{bel[0]}{bel[2:]}'

                                # If the BEL matches add the related cell to a list
                                if rsrc_bel == lut:
                                    rel_cells.append(design.cells[tile][site][bel])
                            elif rsrc_bel == bel:
                                rel_cells.append(design.cells[tile][site][bel])
                        cell = ', '.join(rel_cells)

            elif 'Y' in rsrc_offset:
                try:
                    tile_y = int(tile[tile.find('Y', tile.find('_X')) + 1:])
                except ValueError:
                    print(f'Faulty Resource Root: {rsrc_root}, Offset: {rsrc_offset}, Tile: {tile}')
                    tile_y = 0

                # Set y offset value
                y_off = 0
                if '1' in rsrc_offset:
                    y_off = 1

                # Check each related site for matches for the sought resource
                for site in rel_sites:
                    # Check the site's BELs if the Y address matches
                    if f'Y{tile_y + y_off}' in site:
                        rel_cells = []
                        # Check each bel in the current site to see if it matches the resource
                        for bel in design.cells[tile][site]:
                            # Edit BEL name for LUT resources
                            lut = 'NOT A LUT'
                            if 'LUT' in bel:
                                lut = f'{bel[0]}{bel[2:]}'

                                # If the BEL matches add the related cell to a list
                                if rsrc_bel == lut:
                                    rel_cells.append(design.cells[tile][site][bel])
                            elif rsrc_bel == bel:
                                rel_cells.append(design.cells[tile][site][bel])
                        cell = ', '.join(rel_cells)
    
    # Check that cell either has a name or is empty and return the cooresponding string
    if cell:
        return cell
    else:
        return 'NA'

def eval_tile_errors(tile:Tile, muxes:set, int_fault_bits:dict, design_bits:list, tilegrid:dict, design:DesignQuery):
    '''
        Evaluates a given tile associated with fault bits, determines any fault errors and
        the fault bits that caused them, and finds affected pips for the fault
            Arguments: Tile object for current tile, list of routing muxes affected by fault bits,
                       dicts of all fault bits in the tile, list of all high bits, the part's
                       tilegrid, and a query for the design data
            Returns: Dict storing fault bit information for the tile
    '''

    tile_report = {}
    init_cnctd_srcs = {}
    tile_fault_bits = int_fault_bits[tile.name]

    # Get the connected sources for each routing mux in the tile before bit upsets
    for mux in muxes:
        init_cnctd_srcs[mux] = get_connected_srcs(tile, mux, design)

    # Iterate through each of the fault bits and implement the bit upsets
    [tile.change_bit(fb.addr, {'1->0':0, '0->1':1}.get(fb.type)) for fb in tile_fault_bits]

    # Get the connected sources for each mux after bit upsets are applied and evalute changes made
    for mux in muxes:
        fault_cnctd_srcs = get_connected_srcs(tile, mux, design)

        open_srcs = set()
        short_srcs = set()

        # Add any initial sources that aren't connected post-faults to the open sources
        {open_srcs.add(src) for src in init_cnctd_srcs[mux] if src not in fault_cnctd_srcs}

        # Add sources connected post-fault to the short sources if multiple sources found
        if len(fault_cnctd_srcs) > 1:
            # Add all connected sources after the bit upsets to the list of shorted sources
            short_srcs = fault_cnctd_srcs

        # Get the affected pips for each fault bit related to the current mux
        mux_affected_pips = get_affected_pips(tile_fault_bits, mux, open_srcs, short_srcs, tile)

        fault_desc = 'Not able to find any errors caused by this fault'
        opens_msg = ''
        shorts_msg = ''

        # Generate fault message for any opened source found
        if open_srcs:
            opens_list = ', '.join(sorted(open_srcs))
            opens_msg =  f'Opens created for net(s): {opens_list}'
        else:
            opens_msg = ''

        # Generate fault message for any shorted sources found
        if short_srcs:
            shorts_list = ', '.join(sorted(short_srcs))
            shorts_msg = f'Shorts formed between net(s): {shorts_list}'
        else:
            shorts_msg = ''

        # Create fault message from open message and/or short message and replace node names with
        # their associated nets if they exist
        if opens_msg and not shorts_msg:
            fault_desc = sub_nodes_with_nets(open_srcs, tile.name, opens_msg, int_fault_bits, design_bits, tilegrid, design)
        elif shorts_msg and not opens_msg:
            fault_desc = sub_nodes_with_nets(short_srcs, tile.name, shorts_msg, int_fault_bits, design_bits, tilegrid, design)
        elif opens_msg and shorts_msg:
            fault_desc = f'{opens_msg}; {shorts_msg}'
            fault_desc = sub_nodes_with_nets(open_srcs, tile.name, fault_desc, int_fault_bits, design_bits, tilegrid, design)
            fault_desc = sub_nodes_with_nets(short_srcs, tile.name, fault_desc, int_fault_bits, design_bits, tilegrid, design)
        else:
            fault_desc = 'Not able to find any errors caused by this fault'

        # Apply the generated fault message to each related fault bit
        for bit in tile_fault_bits:
            # Check if each fault bit is associated with the current routing mux before
            # applying the fault message
            if mux in bit.resource:
                tile_report[bit.bit] = {'fault_desc' : fault_desc, 'affected_pips' : mux_affected_pips[bit.bit]}

    return tile_report


def get_affected_pips(tile_fault_bits, mux:str, opened_srcs:set, shorted_srcs:set, gen_tile:Tile):
    '''
        Retrieves all affected pips in the given routing mux and whether they have been
        activated or deactivated.
            Arguments: list of fault bits in the tile, the affected routing mux, set of
                       opened sources, set of closed sources, interconnect tile object
            Returns: dictionary including each bit and affected pips related to the bit
    '''

    srcs_dict = {'deactivated' : opened_srcs, 'activated' : shorted_srcs}

    # Initialize affected pips with values already associated with the bits
    affected_pips = {f_bit.bit : f_bit.affected_pips for f_bit in tile_fault_bits}

    # Iterate through both source types (deactivated and activated)
    for src_type, srcs in srcs_dict.items():
        for src in srcs:
            # Default seperator between source and sink in a pip
            separator = '->>'

            # Edge case for VCC and GND because they are not part of the tile pips dictionary
            if src == 'VCC_WIRE' or src == 'GND_WIRE':
                # Determine whether any of the fault bits are related to the routing mux
                for f_bit in tile_fault_bits:
                    # Check if the bit is either a row or column bit for the routing mux
                    is_row_bit = f_bit.addr in gen_tile.resources[mux].row_bits
                    is_col_bit = f_bit.addr in gen_tile.resources[mux].col_bits
                    
                    # If current bit is row or column bit for mux, this is an affected pip
                    if is_row_bit or is_col_bit:
                        # Add pip to the dictionary for the bit if a pip is found
                        if 'No affected pips found' in affected_pips[f_bit.bit]:
                            affected_pips[f_bit.bit] = [f'{src}{separator}{mux} ({src_type})']
                        else:
                            affected_pips[f_bit.bit].append(f'{src}{separator}{mux} ({src_type})')
                        
            else:
                # Get all related bits to the pip, independent of their required value
                pip_bits = [bit.replace('!', '') for bit in gen_tile.pips[mux][src]]

                # Determine which fault bits are part of the pip rule
                for f_bit in tile_fault_bits:
                    if f_bit.addr in pip_bits:
                        # Determine if the pip is standard or bidirectional
                        if src in gen_tile.pips and mux in gen_tile.pips[src]:
                            separator = '<<->>'
                        
                        # Add pip to the dictionary for the bit if a pip is found
                        if 'No affected pips found' in affected_pips[f_bit.bit]:
                            affected_pips[f_bit.bit] = [f'{src}{separator}{mux} ({src_type})']
                        else:
                            affected_pips[f_bit.bit].append(f'{src}{separator}{mux} ({src_type})')

    return affected_pips


def get_connected_srcs(tile:Tile, sink_nd:str, design:DesignQuery):
    '''
        Evaluates routing mux config bits and routing rules to determine which source nodes
        are connected to the sink node.
            Arguments: Tile object with updated config bits, string of the sink node, and a
                       query for the design's data
            Returns: Set of all connected source nodes
    '''

    connected_srcs = set()
    # Iterate through each source node of the current routing mux
    for src_nd in tile.pips[sink_nd]:
        
        connected = True
        # Iterate through and check the bit configuration for each config bit
        for pip_bit in tile.pips[sink_nd][src_nd]:
            # Set connected flag to false if any config bit value does not match configuration
            if pip_bit[0] == '!' and tile.config_bits[pip_bit[1:]] != 0:
                connected = False
                break
            elif pip_bit[0] != '!' and tile.config_bits[pip_bit] != 1:
                connected = False
                break
        # If connected flag remains true add it to the list of connected sources
        if connected:
            connected_srcs.add(src_nd)

    # Check if the sink node actually connects to VCC or GND
    if sink_nd in tile.special_pips:

        # Iterate through each source node of the current sink node in the special pips dictionary
        for src_nd in tile.special_pips[sink_nd]:

            # If the pip is marked as "default", make sure all config bits for the mux are off
            if tile.special_pips[sink_nd][src_nd] == 'default':
                # Gather related bits to the mux in a set and make sure all bits are off
                col_bits = set(tile.resources[sink_nd].col_bits)
                row_bits = set(tile.resources[sink_nd].row_bits)
                mux_bits = col_bits.union(row_bits)
                all_bits_are_off = all([tile.config_bits[bit] == 0 for bit in mux_bits])
                
                # Check if sink and source nodes have the same net routed through them
                try:
                    src_has_net = sink_nd in design.nets[tile.name]
                    sink_has_net = src_nd in design.nets[tile.name]
                except KeyError:
                    src_has_net = False
                    sink_has_net = False

                if src_has_net and sink_has_net:
                    nodes_share_net = design.nets[tile.name][src_nd] == design.nets[tile.name][sink_nd]
                else:
                    nodes_share_net = False

                # If both flags are set, add source to connected sources
                if all_bits_are_off and nodes_share_net:
                    connected_srcs.add(src_nd)

    return connected_srcs

def sub_nodes_with_nets(node_list:list, tile:str, msg_str:str, fault_bits:dict, design_bits:list, tilegrid:dict, design:DesignQuery):
    '''
        Replace each node in the given list with its corresponding net in the fault message
            Arguments: List of nodes to be replaced, string of the tile name, the generated fault
                       message string, list of the design bits, dicts of the fault bits and the
                       part's tilegrid, and a query for the design's data
            Returns: Fault message string with node names swapped with cooresponding design net
                     names or a default placeholder for the node
    '''

    node_net_assoc = {}
    unconnected_nodes = []
    direct_nets = []

    # Populate association dict and update the dict items and unconnected node list
    for node in node_list:
        node_net_assoc[node] = set()
        assoc_net = design.get_net(tile, node)

        # Add associated net to dict item if exists, if not add node to unconnected node list
        if assoc_net != 'NA':
            node_net_assoc[node].add(assoc_net)
            direct_nets.append(assoc_net)
        else:
            unconnected_nodes.append(node)

    # Trace any unconnected nodes for any nets and update the association dict
    if unconnected_nodes:
        # Set the net associated with each unconnected net to the results of a net trace
        for uc_node in unconnected_nodes:
            node_net_assoc[uc_node] = find_connected_net(tile, node, fault_bits, design_bits, tilegrid, design)

        # Remove any nets found directly from each unconnected node's set if there are any
        for uc_node in unconnected_nodes:
            # Remove any direct nets from the current node's association
            for d_net in direct_nets:
                node_net_assoc[uc_node].discard(d_net)

            # Add placeholder if set is empty after removing direct nets
            if not node_net_assoc[uc_node]:
                node_net_assoc[uc_node].add(f'Unconnected Node({uc_node})')

    # Replace the association set for each node with a str and replace node in msg_str
    for node in node_net_assoc:
        node_net_assoc[node] = ', '.join(node_net_assoc[node])
        msg_str = msg_str.replace(node, node_net_assoc[node])
    
    return msg_str

def find_connected_net(tile_name:str, node:str, fault_bits:dict, design_bits:list, tilegrid:dict, design:DesignQuery):
    '''
        Wrapper function for the recursive trace_node_connection. Evaluates post-fault design
        to find any nets that could be connected to the given node.
            Arguments: Strings of the initial tile and node, list of design bits, dicts of the
                       fault bits and the part's tilegrid, and a query for the design's data
            Returns: Set of strings of net connected to the requested node
    '''

    tile_collection = {}
    found_nets = trace_node_connections(tile_name, node, fault_bits, design_bits,
                                        tilegrid, tile_collection, design)

    return found_nets

def trace_node_connections(tile_name:str, node:str, fault_bits:dict, design_bits:list, tilegrid:dict, tile_collection:dict, design:DesignQuery):
    '''
        Recursively traces back through the node connections and board wires to verify if any
        nets are connected to the given node after SBU's are applied to the design.
            Arguments: Strings of the tile and node; list of the design bits; dicts for the fault
                       bits, the part's tilegrid, and the tiles already evaluated for this trace;
                       and a query for the design's data
            Returns: Set of strings of nets connected to the requested node
    '''

    # Create and load a new tile object and save it if it hasn't been run yet
    try:
        tile = tile_collection[tile_name]
    except KeyError:
        tile_type = tile_name[:tile_name.find('_X')]
        tile = Tile(tile_name, tile_type, design.part)

        # Update tile config bits
        [tile.change_bit(bit, 1) for bit in tile.config_bits if bit_bitstream_addr([tile_name, bit, 0], tilegrid) in design_bits]

        # Check if there are any fault bits in the current tile
        if tile_name in fault_bits:
            # Apply changes from each fault bit
            for f_bit in fault_bits[tile_name]:
                # Invert the value for the fault bit if it is in the tile
                if f_bit.addr in tile.config_bits:
                    tile.change_bit(f_bit.addr, {0:1, 1:0}.get(tile.config_bits[f_bit.addr]))

        tile.eval_connections()
        tile_collection[tile_name] = tile

    connected_nodes = []

    # Determine if given node is a sink or src in a tile connection and get the nodes
    # connected to it accordingly
    if node in tile.cnxs:
        connected_nodes.extend(tile.cnxs[node])
    else:
        # Check each source node with connections for the given node
        for curr_src in tile.cnxs:
            # If the node is found 
            if node in tile.cnxs[curr_src]:
                # Add all other sinks to the list
                for curr_sink in tile.cnxs[curr_src]:
                    # Add all sink nodes to the list that aren't the given node
                    if curr_sink != node:
                        connected_nodes.append(curr_sink)

    # Remove targeted node from list
    if node in connected_nodes:
        connected_nodes.remove(node)

    found_nets = set()
    # Check each connected node for an associated net
    for connected_node in connected_nodes:
        found_net = design.get_net(tile_name, connected_node)

        # return the associated net if there is one. If not rerun trace on each
        # wire connection to an INT tile
        if found_net != 'NA':
            found_nets.add(found_net)
        else:
            wire_cnxs = design.get_wire_connections(tile_name, connected_node)
            # Remove all non-INT connections
            for wire_cnx in wire_cnxs:
                # Remove the current wire connection if it isn't to an INT tile
                if 'INT' not in wire_cnx:
                    wire_cnxs.remove(wire_cnx)

            # Trace the node at the end of each wire connection
            for wire_cnx in wire_cnxs:
                wire_tile, wire_node = wire_cnx.split('/')
                found_nets.update(trace_node_connections(wire_tile, wire_node, fault_bits,
                                                         design_bits, tilegrid,
                                                         tile_collection, design))

    return found_nets


####################################################
#   Functions for Conversion Between Bit Formats   #
####################################################

def bit_tile_addr(bitstream_addr:list, tilegrid:dict, tile_imgs:dict):
    '''
        Converts a bit's bitstream address to its tile and tile address
            Arguments: List of the bitstream address and dicts of the tilegrid and tile images
            Returns: 3-element list with strings of the bit's tile, tile address, and an int of the
                     tilegrid data index the bit's data is found at in its tile.
    '''

    bit_tiles = {}                          # {tile : dataset index}
    bit_frame = int(bitstream_addr[0], 16)
    word_offset = int(bitstream_addr[1])
    bit_offset = int(bitstream_addr[2])

    # Iterate through the tiles from the tilegrid to find which ones can potentially have the bit
    for curr_tile, info in tilegrid.items():

        # Check each dataset for the current tile to see if the base address can match
        for i, baseaddr in enumerate(info['baseaddr']):
            # Check if the bit frame address is in the range for the current tile
            if bit_frame >= baseaddr and bit_frame <= baseaddr + (info['frames'][i] - 1):
                # If the word offset is within the range for the current tile, add it to the list
                if word_offset >= info['offset'][i] and word_offset <= info['offset'][i] + (info['words'][i] - 1):
                    bit_tiles[curr_tile] = i

    # If any potential tiles are found check if they use the bit
    if bit_tiles:
        # Iterate through the potential tiles and check if they use the bit
        for bit_tile, i in bit_tiles.items():
            frame_addr = bit_frame - tilegrid[bit_tile]['baseaddr'][i]
            bit_addr = bit_offset + (32 * (word_offset - tilegrid[bit_tile]['offset'][i]))

            addr = '{:02}_{:02}'.format(frame_addr, bit_addr)
            ttp_name = bit_tile[:bit_tile.find('_X')]

            # Check the tile archetype's config bits for the bit
            if(addr in tile_imgs[ttp_name].config_bits):
                return [bit_tile, addr, i]
        return []
    return []

def bit_bitstream_addr(tile_addr:list, tilegrid:dict):
    '''
        Converts a bit's tile and tile address into its bitstream address
            Arguments: 2-element list of strings of the bit's tile and tile address and a dict
                       of the part's tilegrid
            Returns: String of the bit's bitstream address (bit_<frame(0x)>_<word(int)>_<bit(int)>)
    '''

    # Convert the bit back to its original format if one is provided
    if tile_addr:
        tile, addr, data_index = tile_addr
        frame_offset, bit = addr.split('_')
        baseaddr = tilegrid[tile]['baseaddr'][data_index]
        word_offset = tilegrid[tile]['offset'][data_index]

        frame = baseaddr + int(frame_offset)

        bit = int(bit)
        word = word_offset + int(bit / 32)
        bit = bit % 32

        return 'bit_{:08x}_{:03}_{:02}'.format(frame, word, bit)
    return ''
