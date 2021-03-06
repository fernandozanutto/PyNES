from typing import Dict
from time import time_ns
from bus import Bus
from instructions.generic_instructions import Instruction
from rom import ROM
from status import Status

import instructions.instructions as i_file
import instructions.jump_instructions as j_file
import instructions.load_instructions as l_file
import instructions.store_instructions as s_file
import instructions.stack_instructions as t_file
import instructions.arithmetic_instructions as a_file
import instructions.logical_instructions as log_file
import instructions.nop_instructions as n_file
import instructions.unofficial_instructions as u_file


class CPU:
    def __init__(self, bus: Bus, debug: bool = False):
        self.rom = None
        self.bus = bus
        self.debug = debug
        self.cycle = 7 # TODO check it, starting in 7 cause nestes.log
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
        self.instructions: Dict[bytes, Instruction] = {}
        for instruction in instructions_list:
            if instruction.identifier_byte in self.instructions.keys():
                raise Exception('Duplicate instruction identifier bytes ' + instruction.identifier_byte.hex())
            self.instructions[instruction.identifier_byte] = instruction

    def start_up(self, callback):
        """
        set the initial values of cpu registers
        status reg: 000100 (irqs disabled)
        x, y, a regs: 0
        stack pointer: $FD
        $4017: 0 (frame irq disabled)
        $4015: 0 (sound channels disabled)
        $4000-$400F: 0 (sound registers)
        """

        self.callback = callback

        self.pc_reg = 0
        self.status_reg = Status()  # know as 'P' on NesDev Wiki
        self.sp_reg = 0xFD

        self.x_reg = 0
        self.y_reg = 0
        self.a_reg = 0

        # TODO implement memory sets

        self.bus.write_memory(0x4015, 0, num_bytes=2)
        self.bus.write_memory(0x4017, 0, num_bytes=2)

    def push_to_stack(self, value, size):
        for i in range(size):
            self.bus.write_memory(0x0100 + self.sp_reg, (value >> (8 * (size - i - 1))) & 255, num_bytes=1)
            self.sp_reg -= 1

    def pull_from_stack(self, size):
        value = 0

        for i in range(size):
            self.sp_reg += 1
            value += self.bus.read_memory(0x0100 + self.sp_reg) << (8 * i)

        return value

    def find_instructions(self, cls) -> list[Instruction]:
        """
        find all available instructions
        """

        subclasses = [subc for subc in cls.__subclasses__() if subc.identifier_byte is not None]
        return subclasses + [g for s in cls.__subclasses__() for g in self.find_instructions(s)]

    def run_rom(self, rom: ROM):
        # load rom
        self.rom = rom
        self.pc_reg = 0xC000  # first rom address

        if rom.is_snake_rom:
            self.pc_reg = 0x0600
            self.rom.memory_start_location = 0
            for i in range(len(rom.get_memory())):
                self.bus.write_memory(0x0600 + i, int.from_bytes(rom.get(i), 'little'))

        # run program
        self.running = True
        i = 0
        last_time = time_ns()
        while self.running:
            i += 1

            if self.bus.get_nmi_status():
                self.push_to_stack(self.pc, 2)

                status_reg_copy = self.status_reg.copy()
                status_reg_copy.bits[Status.StatusTypes.break1] = 0
                status_reg_copy.bits[Status.StatusTypes.break2] = 1

                self.push_to_stack(status_reg_copy.to_int(), 1)

                self.status_reg.bits[Status.StatusTypes.interrupt] = 1

                self.bus.tick(2)
                self.pc = self.bus.read_memory(0xFFFA)

                continue

            # get the current byte at pc
            identifier_byte = self.bus.read_memory(self.pc_reg)

            if type(identifier_byte) == int:
                identifier_byte = bytes([identifier_byte])

            # turn the byte into an Instruction
            instruction = self.instructions.get(identifier_byte)

            if instruction is None:
                raise Exception('PC: {} Instruction not found: {}'.format(hex(self.pc_reg), identifier_byte))

            # get the data bytes
            data_bytes = self.bus.read_memory_bytes(self.pc_reg + 1, instruction.data_length)

            if self.debug:
                self.debug_print(self.pc_reg, identifier_byte, data_bytes, instruction)

            self.pc_reg += instruction.get_instruction_length()

            value = instruction.execute(self, data_bytes)

            instr_cycles = instruction.get_cycles()

            self.cycle += instr_cycles

            self.status_reg.update(instruction, value)

            cur_time = time_ns()

            if self.debug and cur_time - last_time > 0:
                print('time for running instruction', cur_time - last_time, identifier_byte)

            last_time = cur_time

            self.bus.tick(instr_cycles)

            self.callback()

            cur_time = time_ns()

            if self.debug and cur_time - last_time > 0:
                print('time for running ui', cur_time - last_time)

            last_time = cur_time

    def debug_print(self, pc_reg: int, identifier_byte, data_bytes, instruction):
        # print out diagnostic information
        # example: C000  4C F5 C5  JMP $C5F5      A:00 X:00 Y:00 P:24 SP:FD PPU:  0,  0 CYC:

        registers_state = [
            hex(self.a_reg)[2:].upper(),
            hex(self.x_reg)[2:].upper(),
            hex(self.y_reg)[2:].upper(),
            hex(self.status_reg.to_int())[2:].upper(),
            hex(self.sp_reg)[2:].upper()
        ]

        inst_bytes = (identifier_byte + data_bytes).hex().upper()
        rng = range(0, len(inst_bytes), 2)
        inst_hexes = [inst_bytes[i:i + 2] for i in rng]

        print("{:0>4}  {:<8}  {:<31} A:{:0>2} X:{:0>2} Y:{:0>2} P:{:0>2} SP:{} CYC:{}".format(
            hex(pc_reg)[2:].upper(),
            ' '.join(inst_hexes),
            instruction.__name__[0:3].upper(),
            *registers_state,
            self.cycle
        ))
