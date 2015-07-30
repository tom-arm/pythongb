# Reference: http://imrannazar.com/GameBoy-Emulation-in-JavaScript:-GPU-Timings
from .utils import *
from math import floor


class GPU(object):
    def __init__(self, mem_controller):
        # It needs to have access to main memory
        self.memory = mem_controller

        self.clock = 0

        # Holds the current mode for the CPU defined below:
        # 0 - HBlank, drawing of a line (51 Clocks)
        # 1 - VBlank, when all the lines are drawn, in this case, the image will be pushed to the screen (114 Clocks)
        # 2 - Scanline (Accessing OAM) (20 Clocks)
        # 3 - Scanline (Accessing VRAM) (43 Clocks)
        self.mode = 0
        self.interrupt_type = 0

        # Holds the current line that would be drawn to
        self.line = 0

        # Create a 256 x 256 map for the bitmap
        #self.map = Image.new("RGB", (160, 144), "white")

        # Palette to colour map
        self.palette_map = {
            0: (255, 255, 255),
            1: (192, 192, 192),
            2: (96, 96, 96),
            3: (0, 0, 0)
        }

        # A GPU internal set of tiles 128 + 255 tiles with y and x coords
        self.tiles = [[[0 for x in range(8)] for y in range(8)] for i in range(128 + 255 + 1)]

        # GPU Register locations in memory
        self.LCD_CONTROL = 0xFF40
        self.LCD_STATUS = 0xFF41

        self.SCROLL_Y = 0xFF42
        self.SCROLL_X = 0xFF43

        self.LCD_Y_LINE = 0xFF44
        self.LY_COMPARE = 0xFF45

        self.WINDOW_Y = 0xFF4A

        # The X position - 7
        self.WINDOW_X = 0xFF4B

        self.PALETTE = 0xFF47
        self.PALETTE0_DATA = 0xFF48
        self.PALETTE1_DATA = 0xFF49

        self.DMA_CONTROL = 0xFF46

        self.build_tile_data()

    # Creates the tile map from the set of tile held in the memory of the gameboy
    def build_tile_data(self):
        tiles_start = 0x8000
        tiles_end = 0x9800
        y = 0

        tile = 0

        for i in range(0, tiles_end - tiles_start, 2):
            line1 = self.memory.read(tiles_start + i)
            line2 = self.memory.read(tiles_start + i + 1)

            for x in range(8):
                self.tiles[tile][y][x] = (line1 >> 7 - x) & 0x1 | ((line2 >> 7 - x) & 0x1) << 1

            y += 1

            if y == 8:
                y = 0
                tile += 1

    # This a function that is called that updates a particular tile when a write
    # is issued to the VRAM in memory
    def update_tile(self, write_location):
        # Find the tile it belongs to in memory
        tile_location = int(floor(write_location / 16) * 16)

        y = int(round((write_location - tile_location) / 2))
        tile = tile_location - 0x8000

        # Now update this whole line
        line1 = self.memory.read(tile_location + y * 2)
        line2 = self.memory.read(tile_location + y * 2 + 1)

        for x in range(8):
            self.tiles[tile][y][x] = (line1 >> 7 - x) & 0x1 | ((line2 >> 7 - x) & 0x1) << 1

    # This function syncs the GPU with the CPUs clock
    def sync(self, cycles):
        self.clock += cycles

        self.line = self.memory.read(self.LCD_Y_LINE)
        if self.memory.tiles_outdated:
            #self.update_tile(self.memory.outdated_location)
            pass

        # OAM Access
        if self.mode == 2:
            if self.clock >= 20:
                # Move to OAM access mode
                self.mode = 3

                # Write that it is switching to a OAM interrupt
                self.interrupt_type &= 0b11000000

                self.interrupt_type |= 0b00100000
                self.interrupt_type |= self.mode

                self.memory.write(self.LCD_STATUS, self.interrupt_type)

                self.clock = 0

        # VRAM Mode
        elif self.mode == 3:
            if self.clock >= 43:
                self.mode = 0

                # Write a line to the frame buffer
                self.clock = 0

                # Write that it is switching to a H-blank interrupt
                self.interrupt_type &= 0b11000000

                self.interrupt_type |= 0b00001000
                self.interrupt_type |= self.mode

                self.memory.write(self.LCD_STATUS, self.interrupt_type)

        # H-Blank
        elif self.mode == 0:
            if self.clock >= 51:
                self.clock = 0

                self.line += 1

                self.memory.write(self.LCD_Y_LINE, self.line)

                if self.line == 143:
                    # Perform a VBlank
                    self.mode = 1

                    # Write that it is switching to a v-blank interrupt
                    self.interrupt_type &= 0b11000000

                    self.interrupt_type |= 0b00010000
                    self.interrupt_type |= self.mode

                    # Push the image to be rendered
                    # For testing purposes, just place it in a PIL container
                    # map.show()
                else:
                    # Move to VRAM access
                    self.mode = 2

                    self.interrupt_type &= 0b11000000

                    self.interrupt_type |= 0b00010000
                    self.interrupt_type |= self.mode

                    self.memory.write(self.LCD_STATUS, self.interrupt_type)

        # V-Blank
        else:
            if self.clock >= 114:
                self.clock = 0

                self.line += 1

                self.memory.write(self.LCD_Y_LINE, 144)

                if self.line > 153:
                    self.line = 0
                    self.mode = 2

                    self.interrupt_type &= 0b11000000

                    self.interrupt_type |= 0b00010000
                    self.interrupt_type |= self.mode

                    self.memory.write(self.LCD_STATUS, self.interrupt_type)
                    self.memory.write(self.LCD_Y_LINE, self.line)