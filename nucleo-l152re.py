
import os
import signal
from sys import exit
from time import time, sleep 
import re
import subprocess

from avatar.emulators.s2e import init_s2e_emulator
from avatar.system import System
from avatar.targets.gdbserver_target import *
from avatar.targets.openocd_jig import *
from avatar.targets.openocd_target import *

BIN_FILE = "../project/led_blink/build/led_blink.bin"

configuration = {
    'output_directory': '/tmp/avatar_nucleo/',
    'configuration_directory': os.getcwd(),
    "s2e": {
        "emulator_gdb_path": "/home/avatar/projects/gdb-build/gdb/gdb",
        "emulator_gdb_additional_arguments": ["--data-directory=/home/avatar/projects/gdb-build/gdb/data-directory/"],
        's2e_binary': '/home/avatar/projects/s2e-build/qemu-release/arm-s2e-softmmu/qemu-system-arm',
        "klee": {
        },
        "plugins": {
            "BaseInstructions": {},
            "Initializer": {},
            "MemoryInterceptor": "",
            "RemoteMemory": {
                "verbose": True,
                "writeBack": False,
                "listen_address": "localhost:9998",
                "ranges":  {
                    "peripherals": {
                        "address": 0x40000000,
                        "size":    0x10000000,
                        "access": ["read", "write", "execute", "io", "memory", "concrete_value", "concrete_address"]
                    },
                    "flash": {
                        "address": 0x20000000, # SRAM (mbed DigitalOut instance comes hore)
                        "size": 0x1000,
                        "access": ["read", "write", "execute", "io", "memory", "concrete_value", "concrete_address"]
                    },
                },
            },
            "RawMonitor": """
                kernelStart = 0,
                -- we consider RAM
                ram_module = {
                    delay      = false,      
                    name       = "ram_module",
                    start      = 0x400000,
                    size       = 0x018000,
                    nativebase = 0x400000,
                    kernelmode = false
                },
                rom_module = {
                    delay      = false,      
                    name       = "rom_module",
                    start      = 0x0,
                    size       = 0x3FFFFF,
                    nativebase = 0x0,
                    kernelmode = false
                },
                bin_module = {
		    delay      = false,
		    name       = "bin_module",
		    start      = 0x8000000,
		    size       = 0x100000,
		    nativebase = 0x8000000,
		    kernelmode = false
                } 
                """,
            "ModuleExecutionDetector": """
                trackAllModules = true,
                configureAllModules = true,
                ram_module = {
                  moduleName = "ram_module",
                  kernelMode = true,
                },
                rom_module = {
                  moduleName = "rom_module",
                  kernelMode = true,
                },
		bin_module = {
		  moduleName = "bin_module",
		  kernelMode = true
		}
                """,
            "Annotation": """
                a_start_measure = {
                  module  = "bin_module",
                  active  = true,
                  address = 0x8001c40,   -- start mem write
                  instructionAnnotation = "start_measure",
                  beforeInstruction = true,
                  switchInstructionToSymbolic = false,
                },
                a_stop_measure = {
                  module  = "bin_module",
                  active  = true,
                  address = 0x8001c44,    -- after mem write (start+4)
                  instructionAnnotation = "stop_measure",
                  beforeInstruction = true,
                  switchInstructionToSymbolic = false,
		}
            """,
        },
        "include" : ["lua/util.lua", "lua/common.lua"],
    },

    "qemu_configuration": {
        "gdbserver": False,
        "halt_processor_on_startup": True,
        "trace_instructions": True,
        "trace_microops": False,
        "append": ["-serial", "tcp::8888,server,nowait","-S"]
    },

    'machine_configuration': {
        'architecture': 'arm',
        'cpu_model': 'cortex-m3',
        'entry_address': 0x00,
        "memory_map": [
            {
                "size": 0x1000000,
                "name": "rom",
                # "file": "./Nucleo_printf_NUCLEO_L152RE.bin",
                "file": BIN_FILE,
                "map": [
                    {"address": 0x8000000, # Flash Memory (Bank 1)
                     "type": "code",
                     "permissions": "rwx"}
                ]
            },
            {
                "size": 0x100000,
                "name": "sram",
                "file": "./sram_after_init.bin",
                "map": [
                    {"address": 0x20000000, # SRAM
                     "type": "code",
                     "permissions": "rw"}
                ]
            },
        ],
    },

    "avatar_configuration": {
        "target_gdb_address": "tcp:localhost:3333",
        "target_gdb_additional_arguments": ["--data-directory=/home/avatar/projects/gdb-build/gdb/data-directory/"],
        "target_gdb_path": "/home/avatar/projects/gdb-build/gdb/gdb",
    },
    'openocd_configuration': {
        'config_file': 'nucleo-l152re.cfg'
    }
    }


def get_symbol_addr(file_name, symbol):
    out = subprocess.check_output("readelf -s %s" % file_name, shell=True, universal_newlines=True)
    for line in out.split('\n'):
        line += "$"
        if line.find(" " + symbol + "$") >= 0:
            # print(line)
            # m = re.match(r'\d+: ([0-9a-f]+)\s+\d+ (\w+)\D+\d+ ([^\s@]+)', line)
            m = re.match(r'^\s+\d+\: ([0-9a-f]+)\s', line)
            return int("0x" + m.group(1), 16)
    return -1 # ERROR

REGISTERS = [
    'r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10', 'r11',
    'r12', 'sp', 'lr', 'pc', 'xPSR'
]

def get_regs(debuggable):
    regs = []
    for r in REGISTERS:
        regs.append(debuggable.get_register(r))
    return regs

def set_regs(debuggable, regs):
    for i in range(len(regs)):
        debuggable.set_register(REGISTERS[i], regs[i])

def main():

    elf_file = BIN_FILE.replace(r".bin", r".elf")

    # main_addr = 0x8001c28 # led_blink.elf <main>
    main_addr = get_symbol_addr(elf_file, "main") - 1 # anti 1 byte offset (readelf's bug?)
    timeout_addr = get_symbol_addr(elf_file, "_Z7timeoutv") - 1 # anti 1 byte offset
    if timeout_addr < 0:
        timeout_addr = get_symbol_addr(elf_file, "__libc_fini_array")
    print("[*] main = %#x, timeout = %#x" % (main_addr, timeout_addr))

    print("[!] Starting the Nucleo-L152RE demo")


    print("[+] Resetting target via openocd")
    hwmon = OpenocdJig(configuration)
    cmd = OpenocdTarget(hwmon.get_telnet_jigsock())
    cmd.raw_cmd("reset halt")


    print("[+] Initilializing avatar")
    ava = System(configuration, init_s2e_emulator, init_gdbserver_target)
    ava.init()
    ava.start()
    t = ava.get_target()
    e = ava.get_emulator()


    print("[+] Running initilization procedures on the target")
    print("first break point = %#x" % main_addr)
    main_bkt = t.set_breakpoint(main_addr)
    t.cont()
    main_bkt.wait()


    print("[+] Target arrived at main(). Transferring state to the emulator")
    set_regs(e, get_regs(t))
    print("pc = %#x" % e.get_register('pc'))

    #Cortex-M executes only in thumb-node, so the T-flag does not need to be set on these cpus.
    #However, qemu still needs to know the processore mode, so we are setting the flag manually.
    cpsr = e.get_register('cpsr')
    cpsr |= 0x20
    print("new cpsr = %#x" % cpsr)
    e.set_register('cpsr',cpsr)

    print("[+] Continuing execution in the emulator!")
    print("final break point = %#x" % timeout_addr)
    e_end_bp = e.set_breakpoint(timeout_addr)
    start = time.time()
    e.cont()
    e_end_bp.wait()
    duration = time.time() - start

    #Further analyses code goes here
    print("[+] analysis phase")
    print("elapsed time = %f sec" % duration)

    e.stop() # important
    t.stop() # important

if __name__ == '__main__':
    main()
    print("[*] finished")
    os.system("kill " + str(os.getpid()))
    exit()
