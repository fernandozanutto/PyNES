from typing import List

from instructions.generic_instructions import Instruction
from memory_owner import MemoryOwnerMixin
from ppu import PPU
from ram import RAM
from rom import ROM
from status import Status

import instructions.instructions as i_file
import instructions.jump_instructions as j_file
import instructions.load_instructions as l_file
import instructions.store_instructions as s_file
import instructions.transfer_instructions as t_file


class CPU(object):
    def __init__(self, ram: RAM, ppu: PPU):
        self.ram = ram
        self.ppu = ppu
        self.rom = None

        self.memory_owners: List[MemoryOwnerMixin] = [
            self.ram,
            self.ppu
        ]

        # status registers: store a single byte
        self.status_reg: Status = None

        # counter registers: store a single byte
        self.pc_reg: int = None  # program counter
        self.sp_reg: int = None  # stack pointer

        # data registers: store a single byte
        self.x_reg: int = None  # x register
        self.y_reg: int = None  # y register
        self.a_reg: int = None  # a register

        # program counter stores current execution point
        self.running: bool = True

        # create the instructions that the cpu can interpret
        instructions_list = self.find_instructions(Instruction)
        print(instructions_list)
        self.instructions = {}
        for instruction in instructions_list:
            if instruction in self.instructions:
                raise Exception('Duplicate instruction identifier bytes')
            self.instructions[instruction.identifier_byte] = instruction

    def start_up(self):
        """
        set the initial values of cpu registers
        status reg: 000100 (irqs disabled)
        x, y, a regs: 0
        stack pointer: $FD
        $4017: 0 (frame irq disabled)
        $4015: 0 (sound channels disabled)
        $4000-$400F: 0 (sound registers)
        """
        # TODO Hex vs binary
        self.pc_reg = 0
        self.status_reg = Status()
        self.sp_reg = 0xFD

        self.x_reg = 0
        self.y_reg = 0
        self.a_reg = 0

        # TODO implement memory sets

    def get_memory(self, location: int) -> int:
        """
        returns a byte from a given memory location
        """
        memory_owner = self.get_memory_owner(location)
        return memory_owner.get(location)

    def get_memory_owner(self, location: int) -> MemoryOwnerMixin:
        """
        return the owner of a memory location
        """
        # check if memory owner
        for memory_owner in self.memory_owners:
            if memory_owner.memory_start_location <= location <= memory_owner.memory_end_location:
                return memory_owner

        raise Exception('Cannot find memory owner')

    def set_memory(self, location: int, value: int, *, num_bytes: int = 1):
        """
        sets the memory at a location to a value
        """
        memory_owner = self.get_memory_owner(location)
        memory_owner.set(location, value, num_bytes)

    def increase_stack_size(self, size: int):
        self.sp_reg -= size

    def find_instructions(self, cls):
        """
        find all available instructions
        """
        subclasses = [subc for subc in cls.__subclasses__(
        ) if subc.identifier_byte is not None]
        return subclasses + [g for s in cls.__subclasses__() for g in self.find_instructions(s)]

    def run_rom(self, rom: ROM):
        # unload old rom
        if self.rom is not None:
            self.memory_owners.remove(self.rom)

        # load rom
        self.rom = rom
        self.pc_reg = 0xC000

        # load the rom program instruction into memory
        self.memory_owners.append(self.rom)

        # run program
        self.running = True
        while self.running:
            # get the current byte at pc
            identifier_byte = self.get_memory_owner(
                self.pc_reg).get(self.pc_reg)

            # turn the byte into an Instruction
            instruction: Instruction = self.instructions.get(
                identifier_byte, None)
            if instruction is None:
                raise Exception('Instruction not found: {}'.format(
                    identifier_byte.hex()))

            # get the data bytes
            data_bytes = self.rom.get(self.pc_reg + 1, instruction.data_length)

            # print out diagnostic information
            # example: C000  4C F5 C5  JMP $C5F5      A:00 X:00 Y:00 P:24 SP:FD PPU:  0,  0
            print("{}, {}, {}, A:{}, X:{}, Y:{}, P:{}, SP:{}".format(hex(self.pc_reg),
                                                                     (identifier_byte +
                                                                      data_bytes).hex(),
                                                                     instruction.__name__, self.a_reg, self.x_reg,
                                                                     self.y_reg, hex(
                                                                         self.status_reg.to_int()),
                                                                     hex(self.sp_reg)))

            self.pc_reg += instruction.get_instruction_length()

            # we have a valid instruction class
            value = instruction.execute(self, data_bytes)

            self.status_reg.update(instruction, value)
