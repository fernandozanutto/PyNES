from io_registers import IO_Registers
from memory_owner import MemoryOwner
from ppu import PPU
from ram import RAM
from rom import ROM


class Bus:
    def __init__(self, ram: RAM, ppu: PPU, io_regs: IO_Registers, rom: ROM):
        self.ram = ram
        self.ppu = ppu
        self.io_regs = io_regs
        self.rom = rom

        self.memory_owners: list[MemoryOwner] = [
            self.ram,
            self.ppu,
            self.io_regs,
            self.rom
        ]

    def get_memory_owner(self, location: int):
        """
        return the owner of a memory location
        """
        # check if memory owner
        for memory_owner in self.memory_owners:
            if memory_owner.memory_start_location <= location <= memory_owner.memory_end_location:
                return memory_owner

        raise Exception('Cannot find memory owner', location)

    def read_memory(self, position: int):
        mem_owner = self.get_memory_owner(position)

        if type(mem_owner) is RAM:
            position &= ((1 << 11) - 1)

        elif type(mem_owner) is ROM:
            while position >= 0xC000:
                position -= 0x4000

        memory_start_location = mem_owner.memory_start_location
        return mem_owner.get_memory()[position - memory_start_location]

    def get_bytes(self, position: int, size: int = 1) -> bytes:
        mem_owner = self.get_memory_owner(position)

        if mem_owner is RAM:
            position &= ((1 << 11) - 1)

        elif mem_owner is ROM:
            while position >= 0xC000:
                position -= 0x4000

        initial_position = position - mem_owner.memory_start_location

        value = self.get_memory()[initial_position: initial_position + size]

        if type(value) is list and len(value) > 0 and type(value[0]) is bytes:
            value = b''.join(value)

        return bytes(value)

    def write_memory(self, position: int, value: int, size: int = 1):
        mem_owner = self.get_memory_owner(position)

        if mem_owner is RAM:
            position &= ((1 << 11) - 1)

        elif mem_owner is ROM:
            while position >= 0xC000:
                position -= 0x4000

        if mem_owner is RAM:
            position &= ((1 << 11) - 1)

        for i in range(size):
            mem_owner.get_memory()[position - mem_owner.memory_start_location + i] = (value >> (8*i)) & 255

    def write_memory_byte(self, position: int, value: bytes):
        mem_owner = self.get_memory_owner(position)

        if mem_owner is RAM:
            position &= ((1 << 11) - 1)

        elif mem_owner is ROM:
            while position >= 0xC000:
                position -= 0x4000

        self.get_memory()[position - mem_owner.memory_start_location] = value
