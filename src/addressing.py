from typing import Optional
import cpu as c


class Addressing:
    data_length = 0
    add_cycle_from_page_cross = 0

    @classmethod
    def get_instruction_length(cls):
        return cls.data_length + 1

    @classmethod
    def get_offset(cls, cpu):
        return 0

    @classmethod
    def get_cycles(cls):
        return 0


class XRegOffset:
    @classmethod
    def get_offset(cls, cpu):
        return cpu.x_reg


class YRegOffset:
    @classmethod
    def get_offset(cls, cpu):
        return cpu.y_reg


class ImplicitAddressing(Addressing):
    """
    instructions that have no data passed
    example: CLD
    """
    data_length = 0

    @classmethod
    def get_address(cls, cpu, data_bytes) -> Optional[int]:
        return None

    @classmethod
    def get_cycles(cls):
        return 2


class ImmediateReadAddressing(Addressing):
    """
    read a value from the instruction data
    example: STA #7
    example: 8D 07
    """
    data_length = 1

    @classmethod
    def get_data(cls, cpu, memory_address, data_bytes):
        return data_bytes[0]

    @classmethod
    def get_cycles(cls):
        return 2


class AbsoluteAddressing(Addressing):
    """
    looks up an absolute memory address and returns the value
    example: STA $12 34
    example: 8D 34 12
    """
    data_length = 2

    @classmethod
    def get_address(cls, cpu, data_bytes: bytes) -> Optional[int]:
        offset = cls.get_offset(cpu)
        byte_addr = int.from_bytes(data_bytes, byteorder='little')
        addr = byte_addr + offset

        if ((byte_addr & 0xFF) + offset) > 0xFF:
            cls.add_cycle_from_page_cross = 1
        else:
            cls.add_cycle_from_page_cross = 0

        return addr & 0xFFFF

    @classmethod
    def get_cycles(cls):
        return 4 + cls.add_cycle_from_page_cross


class AbsoluteAddressingWithX(XRegOffset, AbsoluteAddressing):
    """
    adds the x reg offset to an absolute memory location
    """


class AbsoluteAddressingWithY(YRegOffset, AbsoluteAddressing):
    """
    adds the y reg offset to an absolute memory location
    """


class ZeroPageAddressing(Addressing):
    """
    look up an absolute memory address in the first 256 bytes
    example: STA $12
    memory_address: $12
    """
    data_length = 1

    @classmethod
    def get_address(cls, cpu, data_bytes: bytes) -> Optional[int]:
        address = int.from_bytes(
            data_bytes, byteorder='little') + cls.get_offset(cpu)

        return address & 0xFF

    @classmethod
    def get_cycles(cls):
        return 3


class ZeroPageAddressingWithX(XRegOffset, ZeroPageAddressing):
    """
    adds the x reg offset to an absolute memory address in the first 256 bytes
    """
    @classmethod
    def get_cycles(cls):
        return 4


class ZeroPageAddressingWithY(YRegOffset, ZeroPageAddressing):
    """
    adds the x reg offset to an absolute memory address in the first 256 bytes
    """
    @classmethod
    def get_cycles(cls):
        return 4


class RelativeAddressing(Addressing):
    """
    offset from current PC, can only jump 128 bytes in either direction
    """
    data_length = 1
    add_cycle_from_branch = 0

    @classmethod
    def get_cycles(cls):
        value = 2
        if cls.add_cycle_from_branch:
            value += cls.add_cycle_from_branch + cls.add_cycle_from_page_cross
        return value

    @classmethod
    def get_address(cls, cpu, data_bytes: bytes) -> int:
        # get the PC
        current_address = cpu.pc_reg

        # offset from the following instruction
        offset = int.from_bytes(data_bytes, byteorder='little')

        if offset > 127:
            offset = offset - 256

        cls.add_cycle_from_page_cross = (current_address & 0xFF) + offset > 0xFF

        return current_address + offset


class IndirectBase(Addressing):
    @classmethod
    def get_address(cls, cpu: 'c.CPU', data_bytes):
        original_location = super().get_address(cpu, data_bytes)
        return int.from_bytes(cpu.bus.read_memory_bytes(original_location, 2), byteorder='little')


class IndirectAddressing(AbsoluteAddressing):
    """
    indirect address
    """

    @classmethod
    def get_address(cls, cpu: 'c.CPU', data_bytes):
        original_location = super().get_address(cpu, data_bytes)

        lsb = cpu.bus.read_memory(original_location)

        if original_location & 0xFF == 0xFF:
            original_location = (original_location >> 8) << 8
            original_location -= 1

        msb = cpu.bus.read_memory(original_location + 1)

        return (msb << 8) + lsb


class IndexedIndirectAddressing(IndirectBase, ZeroPageAddressingWithX):
    """
    adds the x reg before indirection
    """
    @classmethod
    def get_cycles(cls):
        return 6


class IndirectIndexedAddressing(IndirectBase, ZeroPageAddressing):
    """
    adds the y reg after indirection
    """
    @classmethod
    def get_address(cls, cpu: 'c.CPU', data_bytes):
        original_addr = super().get_address(cpu, data_bytes)
        offset = cpu.y_reg

        cls.add_cycle_from_page_cross = (original_addr & 0xFF) + offset > 0xFF

        value = original_addr + offset
        return value & 0xFFFF
    
    @classmethod
    def get_cycles(cls):
        return 5 + cls.add_cycle_from_page_cross
