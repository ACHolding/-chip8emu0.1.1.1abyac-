import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import random
import time
import sys
import os
import pickle
import threading

# ------------------------------
# CHIP-8 CORE (all 35 opcodes)
# ------------------------------

class Chip8:
    def __init__(self):
        self.memory = [0] * 4096
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.stack = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = [0] * (64 * 32)
        self.keys = [0] * 16
        self.draw_flag = True
        self.running = True
        self.load_font()

    def load_font(self):
        font = [
            0xF0, 0x90, 0x90, 0x90, 0xF0,
            0x20, 0x60, 0x20, 0x20, 0x70,
            0xF0, 0x10, 0xF0, 0x80, 0xF0,
            0xF0, 0x10, 0xF0, 0x10, 0xF0,
            0x90, 0x90, 0xF0, 0x10, 0x10,
            0xF0, 0x80, 0xF0, 0x10, 0xF0,
            0xF0, 0x80, 0xF0, 0x90, 0xF0,
            0xF0, 0x10, 0x20, 0x40, 0x40,
            0xF0, 0x90, 0xF0, 0x90, 0xF0,
            0xF0, 0x90, 0xF0, 0x10, 0xF0,
            0xF0, 0x90, 0xF0, 0x90, 0x90,
            0xE0, 0x90, 0xE0, 0x90, 0xE0,
            0xF0, 0x80, 0x80, 0x80, 0xF0,
            0xE0, 0x90, 0x90, 0x90, 0xE0,
            0xF0, 0x80, 0xF0, 0x80, 0xF0,
            0xF0, 0x80, 0xF0, 0x80, 0x80
        ]
        for i, b in enumerate(font):
            self.memory[i] = b

    def load_rom(self, path):
        with open(path, 'rb') as f:
            data = f.read()
        for i, b in enumerate(data):
            if 0x200 + i < 4096:
                self.memory[0x200 + i] = b

    def reset(self):
        self.__init__()

    def emulate_cycle(self):
        if not self.running:
            return

        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2

        x = (opcode >> 8) & 0x0F
        y = (opcode >> 4) & 0x0F
        nnn = opcode & 0x0FFF
        nn = opcode & 0x00FF
        n = opcode & 0x000F

        if opcode == 0x00E0:
            self.display = [0] * (64 * 32)
            self.draw_flag = True

        elif opcode == 0x00EE:
            if self.stack:
                self.pc = self.stack.pop()

        elif (opcode & 0xF000) == 0x1000:
            self.pc = nnn

        elif (opcode & 0xF000) == 0x2000:
            self.stack.append(self.pc)
            self.pc = nnn

        elif (opcode & 0xF000) == 0x3000:
            if self.v[x] == nn:
                self.pc += 2

        elif (opcode & 0xF000) == 0x4000:
            if self.v[x] != nn:
                self.pc += 2

        elif (opcode & 0xF000) == 0x5000:
            if n == 0 and self.v[x] == self.v[y]:
                self.pc += 2

        elif (opcode & 0xF000) == 0x6000:
            self.v[x] = nn

        elif (opcode & 0xF000) == 0x7000:
            self.v[x] = (self.v[x] + nn) & 0xFF

        elif (opcode & 0xF000) == 0x8000:
            if n == 0:
                self.v[x] = self.v[y]
            elif n == 1:
                self.v[x] |= self.v[y]
            elif n == 2:
                self.v[x] &= self.v[y]
            elif n == 3:
                self.v[x] ^= self.v[y]
            elif n == 4:
                result = self.v[x] + self.v[y]
                self.v[0xF] = 1 if result > 255 else 0
                self.v[x] = result & 0xFF
            elif n == 5:
                self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
            elif n == 6:
                self.v[0xF] = self.v[x] & 1
                self.v[x] >>= 1
            elif n == 7:
                self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
            elif n == 0xE:
                self.v[0xF] = (self.v[x] & 0x80) >> 7
                self.v[x] = (self.v[x] << 1) & 0xFF

        elif (opcode & 0xF000) == 0x9000:
            if n == 0 and self.v[x] != self.v[y]:
                self.pc += 2

        elif (opcode & 0xF000) == 0xA000:
            self.i = nnn

        elif (opcode & 0xF000) == 0xB000:
            self.pc = (nnn + self.v[0])

        elif (opcode & 0xF000) == 0xC000:
            self.v[x] = random.randint(0, 255) & nn

        elif (opcode & 0xF000) == 0xD000:
            self.v[0xF] = 0
            for row in range(n):
                byte = self.memory[(self.i + row) & 0xFFF]
                for bit in range(8):
                    if byte & (0x80 >> bit):
                        px = (self.v[x] + bit) % 64
                        py = (self.v[y] + row) % 32
                        idx = py * 64 + px
                        if self.display[idx]:
                            self.v[0xF] = 1
                        self.display[idx] ^= 1
            self.draw_flag = True

        elif (opcode & 0xF000) == 0xE000:
            key = self.v[x] & 0xF
            if nn == 0x9E:
                if self.keys[key]:
                    self.pc += 2
            elif nn == 0xA1:
                if not self.keys[key]:
                    self.pc += 2

        elif (opcode & 0xF000) == 0xF000:
            if nn == 0x07:
                self.v[x] = self.delay_timer
            elif nn == 0x0A:
                pressed = -1
                for i in range(16):
                    if self.keys[i]:
                        pressed = i
                        break
                if pressed == -1:
                    self.pc -= 2
                else:
                    self.v[x] = pressed
            elif nn == 0x15:
                self.delay_timer = self.v[x]
            elif nn == 0x18:
                self.sound_timer = self.v[x]
            elif nn == 0x1E:
                self.i = (self.i + self.v[x]) & 0x0FFF
            elif nn == 0x29:
                self.i = self.v[x] * 5
            elif nn == 0x33:
                self.memory[self.i] = self.v[x] // 100
                self.memory[self.i + 1] = (self.v[x] // 10) % 10
                self.memory[self.i + 2] = self.v[x] % 10
            elif nn == 0x55:
                for i in range(x + 1):
                    self.memory[self.i + i] = self.v[i]
            elif nn == 0x65:
                for i in range(x + 1):
                    self.v[i] = self.memory[self.i + i]

        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

    def get_state(self):
        return {
            'memory': self.memory[:],
            'v': self.v[:],
            'i': self.i,
            'pc': self.pc,
            'stack': self.stack[:],
            'delay_timer': self.delay_timer,
            'sound_timer': self.sound_timer,
            'display': self.display[:],
        }

    def set_state(self, state):
        self.memory = state['memory'][:]
        self.v = state['v'][:]
        self.i = state['i']
        self.pc = state['pc']
        self.stack = state['stack'][:]
        self.delay_timer = state['delay_timer']
        self.sound_timer = state['sound_timer']
        self.display = state['display'][:]
        self.draw_flag = True

    def apply_cheat(self, address, value):
        if 0 <= address < 4096:
            self.memory[address] = value & 0xFF


# ------------------------------
# SOUND
# ------------------------------

def beep_thread():
    try:
        import winsound
        winsound.Beep(440, 80)
    except:
        pass


def play_beep():
    t = threading.Thread(target=beep_thread, daemon=True)
    t.start()


# ------------------------------
# KEY MAP
# ------------------------------

KEY_MAP = {
    '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
    'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
    'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
    'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF,
}

KEY_NAMES = {v: k for k, v in KEY_MAP.items()}

# ------------------------------
# FCEUX-STYLE GUI
# ------------------------------

class Chip8GUI:
    SCALE = 10

    def __init__(self, root):
        self.root = root
        self.root.title("CHIP-8 Emulator [FCEUX-Style]")
        self.root.configure(bg='#0a0a1a')
        self.root.resizable(False, False)

        self.chip = Chip8()
        self.is_running = False
        self.prev_sound = 0

        self.cheat_list = []
        self.state_slot = 0

        self.build_menu()
        self.build_ui()
        self.bind_keys()
        self.update_status()

    def build_menu(self):
        menubar = tk.Menu(self.root, bg='#1a1a2e', fg='#4a9eff',
                          activebackground='#2a2a4a', activeforeground='#6ab0ff')

        file_menu = tk.Menu(menubar, tearoff=0, bg='#1a1a2e', fg='#4a9eff',
                            activebackground='#2a2a4a', activeforeground='#6ab0ff')
        file_menu.add_command(label='Load ROM', command=self.load_rom, accelerator='Ctrl+O')
        file_menu.add_command(label='Reset', command=self.reset, accelerator='Ctrl+R')
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.root.quit, accelerator='Alt+F4')
        menubar.add_cascade(label='File', menu=file_menu)

        emu_menu = tk.Menu(menubar, tearoff=0, bg='#1a1a2e', fg='#4a9eff',
                           activebackground='#2a2a4a', activeforeground='#6ab0ff')
        emu_menu.add_command(label='Run', command=self.run, accelerator='F5')
        emu_menu.add_command(label='Pause', command=self.pause, accelerator='F6')
        emu_menu.add_command(label='Reset', command=self.reset, accelerator='F7')
        emu_menu.add_separator()
        emu_menu.add_command(label='Save State', command=self.save_state, accelerator='F9')
        emu_menu.add_command(label='Load State', command=self.load_state, accelerator='F10')
        menubar.add_cascade(label='Emulator', menu=emu_menu)

        cheat_menu = tk.Menu(menubar, tearoff=0, bg='#1a1a2e', fg='#4a9eff',
                             activebackground='#2a2a4a', activeforeground='#6ab0ff')
        cheat_menu.add_command(label='Add Cheat...', command=self.add_cheat, accelerator='Ctrl+C')
        cheat_menu.add_command(label='Clear Cheats', command=self.clear_cheats)
        cheat_menu.add_command(label='View Cheats', command=self.view_cheats, accelerator='Ctrl+Shift+C')
        menubar.add_cascade(label='Cheats', menu=cheat_menu)

        self.root.config(menu=menubar)

    def build_ui(self):
        main_frame = tk.Frame(self.root, bg='#0a0a1a')
        main_frame.pack(padx=10, pady=5)

        display_frame = tk.Frame(main_frame, bg='#0a0a1a', highlightbackground='#1a1a3a',
                                 highlightthickness=2)
        display_frame.pack()

        self.canvas = tk.Canvas(
            display_frame,
            width=64 * self.SCALE,
            height=32 * self.SCALE,
            bg='#050510',
            highlightthickness=0
        )
        self.canvas.pack()
        self.pixels = []
        for y in range(32):
            row = []
            for x in range(64):
                rect = self.canvas.create_rectangle(
                    x * self.SCALE, y * self.SCALE,
                    (x + 1) * self.SCALE, (y + 1) * self.SCALE,
                    fill='#050510', outline=''
                )
                row.append(rect)
            self.pixels.append(row)

        ctrl_frame = tk.Frame(main_frame, bg='#0a0a1a')
        ctrl_frame.pack(fill='x', pady=6)

        btn_style = {
            'bg': '#111122', 'fg': '#4a9eff',
            'activebackground': '#222244',
            'activeforeground': '#6ab0ff',
            'relief': 'raised', 'bd': 2,
            'font': ('Courier', 9, 'bold'), 'width': 8
        }

        tk.Button(ctrl_frame, text='Load ROM', command=self.load_rom, **btn_style).pack(side='left', padx=3)
        tk.Button(ctrl_frame, text='Run [F5]', command=self.run, **btn_style).pack(side='left', padx=3)
        tk.Button(ctrl_frame, text='Pause [F6]', command=self.pause, **btn_style).pack(side='left', padx=3)
        tk.Button(ctrl_frame, text='Reset [F7]', command=self.reset, **btn_style).pack(side='left', padx=3)
        tk.Button(ctrl_frame, text='Save [F9]', command=self.save_state, **btn_style).pack(side='left', padx=3)
        tk.Button(ctrl_frame, text='Load [F10]', command=self.load_state, **btn_style).pack(side='left', padx=3)

        info_frame = tk.Frame(main_frame, bg='#0a0a1a')
        info_frame.pack(fill='x', pady=2)

        self.status_label = tk.Label(
            info_frame, text='No ROM loaded',
            bg='#0a0a1a', fg='#4a9eff',
            font=('Courier', 9), anchor='w'
        )
        self.status_label.pack(side='left', padx=5)

        self.fps_label = tk.Label(
            info_frame, text='0 FPS',
            bg='#0a0a1a', fg='#4a9eff',
            font=('Courier', 9), anchor='e'
        )
        self.fps_label.pack(side='right', padx=5)

        self.speed_label = tk.Label(
            info_frame, text='CHIP-8',
            bg='#0a0a1a', fg='#4a9eff',
            font=('Courier', 9), anchor='e'
        )
        self.speed_label.pack(side='right', padx=5)

        self.keys_label = tk.Label(
            self.root, text='',
            bg='#0a0a1a', fg='#4a9eff',
            font=('Courier', 8)
        )
        self.keys_label.pack(pady=2)

    def build_key_hint(self):
        rows = [
            ('1', '2', '3', '4'),
            ('Q', 'W', 'E', 'R'),
            ('A', 'S', 'D', 'F'),
            ('Z', 'X', 'C', 'V'),
        ]
        keys_frame = tk.Frame(self.root, bg='#0a0a1a')
        keys_frame.pack(pady=2)
        lbl = tk.Label(keys_frame, text='Keys:', bg='#0a0a1a', fg='#4a9eff',
                       font=('Courier', 8, 'bold'))
        lbl.pack(side='left', padx=5)
        text = ''
        for row in rows:
            text += '  '.join(row) + '    '
        tk.Label(keys_frame, text=text.strip(),
                 bg='#0a0a1a', fg='#6a6a9a',
                 font=('Courier', 8)).pack(side='left')

    def bind_keys(self):
        self.root.bind('<KeyPress>', self.key_down)
        self.root.bind('<KeyRelease>', self.key_up)
        self.root.bind('<F5>', lambda e: self.run())
        self.root.bind('<F6>', lambda e: self.pause())
        self.root.bind('<F7>', lambda e: self.reset())
        self.root.bind('<F9>', lambda e: self.save_state())
        self.root.bind('<F10>', lambda e: self.load_state())
        self.root.bind('<Control-o>', lambda e: self.load_rom())
        self.root.bind('<Control-r>', lambda e: self.reset())
        self.root.bind('<Control-c>', lambda e: self.add_cheat())
        self.root.bind('<Control-Shift-C>', lambda e: self.view_cheats())

    def key_down(self, e):
        if e.keysym in KEY_MAP:
            self.chip.keys[KEY_MAP[e.keysym]] = 1

    def key_up(self, e):
        if e.keysym in KEY_MAP:
            self.chip.keys[KEY_MAP[e.keysym]] = 0

    def load_rom(self):
        path = filedialog.askopenfilename(
            title='Select CHIP-8 ROM',
            filetypes=[('CHIP-8 ROMs', '*.ch8 *.rom *.bin *.c8'), ('All', '*.*')]
        )
        if path:
            try:
                self.loaded_rom_path = path
                self.chip.load_rom(path)
                rom_name = os.path.basename(path)
                size = os.path.getsize(path)
                self.rom_name = rom_name
                self.rom_size = size
                self.status_label.config(text=f'Loaded: {rom_name} ({size}B)')
                self.reset()
            except Exception as ex:
                messagebox.showerror('Error', f'Failed to load ROM:\n{ex}')

    def run(self):
        if not self.is_running:
            self.is_running = True
            self.last_time = time.time()
            self.frame_count = 0
            self.fps_time = time.time()
            self.emulate_loop()

    def pause(self):
        self.is_running = False

    def reset(self):
        self.chip = Chip8()
        if hasattr(self, 'loaded_rom_path'):
            self.chip.load_rom(self.loaded_rom_path)
        self.is_running = False
        self.render()
        if hasattr(self, 'rom_name'):
            self.status_label.config(text=f'Loaded: {self.rom_name} ({self.rom_size}B)')
        else:
            self.status_label.config(text='No ROM loaded')

    def emulate_loop(self):
        if not self.is_running:
            return

        for _ in range(10):
            self.chip.emulate_cycle()

        if self.chip.draw_flag:
            self.render()
            self.chip.draw_flag = False

        for cheat_addr, cheat_val in self.cheat_list:
            self.chip.apply_cheat(cheat_addr, cheat_val)

        if self.chip.sound_timer > 0 and self.prev_sound == 0:
            play_beep()
        self.prev_sound = self.chip.sound_timer

        self.frame_count += 1
        elapsed = time.time() - self.fps_time
        if elapsed >= 1.0:
            fps = self.frame_count / elapsed
            self.fps_label.config(text=f'{fps:.0f} FPS')
            self.frame_count = 0
            self.fps_time = time.time()

        now = time.time()
        target_dt = 1.0 / 60.0
        elapsed = now - self.last_time
        self.last_time = now

        wait_ms = max(1, int((target_dt - elapsed) * 1000))
        self.root.after(wait_ms, self.emulate_loop)

    def render(self):
        for y in range(32):
            for x in range(64):
                if self.chip.display[y * 64 + x]:
                    color = '#00aaff'
                else:
                    color = '#050510'
                self.canvas.itemconfig(self.pixels[y][x], fill=color)

    def update_status(self):
        self.root.after(500, self.update_status)

    # --- Save States ---

    def save_state(self):
        state = self.chip.get_state()
        path = filedialog.asksaveasfilename(
            title='Save State',
            defaultextension='.chst',
            filetypes=[('CHIP-8 State', '*.chst'), ('All', '*.*')]
        )
        if path:
            try:
                with open(path, 'wb') as f:
                    pickle.dump(state, f)
                self.status_label.config(text=f'State saved to {os.path.basename(path)}')
            except Exception as ex:
                messagebox.showerror('Error', f'Failed to save state:\n{ex}')

    def load_state(self):
        path = filedialog.askopenfilename(
            title='Load State',
            filetypes=[('CHIP-8 State', '*.chst'), ('All', '*.*')]
        )
        if path:
            try:
                with open(path, 'rb') as f:
                    state = pickle.load(f)
                self.chip.set_state(state)
                self.status_label.config(text=f'State loaded from {os.path.basename(path)}')
                self.render()
            except Exception as ex:
                messagebox.showerror('Error', f'Failed to load state:\n{ex}')

    # --- Cheats ---

    def add_cheat(self):
        addr_str = simpledialog.askstring('Add Cheat', 'Memory address (hex, e.g. 200):',
                                          parent=self.root)
        if addr_str is None:
            return
        val_str = simpledialog.askstring('Add Cheat', 'Value (hex, e.g. A5):',
                                         parent=self.root)
        if val_str is None:
            return
        try:
            addr = int(addr_str, 16)
            val = int(val_str, 16)
            if 0 <= addr < 4096 and 0 <= val < 256:
                self.cheat_list.append((addr, val))
                self.chip.apply_cheat(addr, val)
                self.status_label.config(text=f'Cheat: ${addr:03X} = ${val:02X}')
            else:
                messagebox.showerror('Error', 'Address: 0-0xFFF, Value: 0-0xFF')
        except ValueError:
            messagebox.showerror('Error', 'Invalid hex values')

    def clear_cheats(self):
        self.cheat_list.clear()
        self.status_label.config(text='All cheats cleared')

    def view_cheats(self):
        if not self.cheat_list:
            messagebox.showinfo('Active Cheats', 'No cheats active')
            return
        text = '\n'.join(f'${addr:03X} = ${val:02X}' for addr, val in self.cheat_list)
        messagebox.showinfo('Active Cheats', text)


# ------------------------------
# LAUNCH
# ------------------------------

if __name__ == '__main__':
    root = tk.Tk()
    app = Chip8GUI(root)
    root.mainloop()
