#!/usr/bin/env python3
"""
Animated flashing-point Christmas tree.

Run: `python tree.py` (Windows: use PowerShell)

This script asks for your name, then renders a Christmas-tree-shaped
arrangement of points that appear with a flashing effect until the
tree is fully revealed.
"""
import sys
import time
import random
import shutil
from colorama import init as colorama_init


def clear_screen():
    # ANSI clear screen and move cursor to home
    sys.stdout.write("\033[2J\033[H")


def hide_cursor():
    sys.stdout.write("\033[?25l")


def show_cursor():
    sys.stdout.write("\033[?25h")


def get_terminal_width(default=80):
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default


def build_tree_positions(height):
    # Returns a list of (row, col, char) for the tree body (without trunk)
    positions = []
    for r in range(height):
        width = 2 * r + 1
        for c in range(width):
            positions.append((r, c, '*'))
    return positions


def render_frame(height, positions_set, revealed, trunk_width=3):
    # Build lines for the tree plus trunk
    lines = []
    for r in range(height):
        width = 2 * r + 1
        row_chars = []
        for c in range(width):
            key = (r, c)
            if key in revealed:
                row_chars.append('\033[92m*\033[0m')  # green
            else:
                # not revealed -> show dot sometimes to flash
                row_chars.append('\033[93m.\033[0m')
        # center the row; we'll center later in printing
        lines.append(''.join(row_chars))

    # trunk
    trunk_height = max(2, height // 4)
    trunk = []
    tw = trunk_width
    for _ in range(trunk_height):
        trunk.append('\033[33m' + ('|' * tw) + '\033[0m')

    return lines, trunk


def main():
    colorama_init()
    try:
        name = input('Type your name: ').strip()
    except (KeyboardInterrupt, EOFError):
        print('\nGoodbye!')
        return

    if not name:
        name = 'Friend'

    print(f'Hello, {name}! Preparing your animated tree...')
    time.sleep(0.8)

    # Parameters
    height = 12
    term_w = get_terminal_width()

    positions = [(r, c) for r in range(height) for c in range(2 * r + 1)]
    total = len(positions)
    revealed = set()

    hide_cursor()
    try:
        frame = 0
        clear_screen()
        # animate until fully revealed
        while len(revealed) < total:
            # progressively reveal a few points each frame
            per_frame = max(1, total // (height * 10))
            # random selection of a few to reveal
            choices = random.sample([p for p in positions if p not in revealed],
                                     min(per_frame, total - len(revealed)))
            for ch in choices:
                revealed.add(ch)

            # Build visual lines with blinking effect
            lines = []
            for r in range(height):
                width = 2 * r + 1
                row_chars = []
                for c in range(width):
                    key = (r, c)
                    if key in revealed:
                        ch = '\033[92m*\033[0m'  # green
                    else:
                        # flash: on alternating frames show a yellow dot, otherwise space
                        if (frame + r + c) % 6 < 3:
                            ch = '\033[93m.\033[0m'
                        else:
                            ch = ' '
                    row_chars.append(ch)
                lines.append(''.join(row_chars))

            # trunk
            trunk_height = max(2, height // 4)
            trunk_width = 3
            trunk_lines = ['\033[33m' + ('|' * trunk_width) + '\033[0m' for _ in range(trunk_height)]

            # draw
            clear_screen()
            # center and print
            for r, row in enumerate(lines):
                text = row
                text_len = len(remove_ansi(text))
                pad = max(0, (term_w - text_len) // 2)
                sys.stdout.write(' ' * pad + text + '\n')

            # blank line between tree and trunk
            sys.stdout.write('\n')
            for t in trunk_lines:
                text_len = len(remove_ansi(t))
                pad = max(0, (term_w - text_len) // 2)
                sys.stdout.write(' ' * pad + t + '\n')

            sys.stdout.flush()
            frame += 1
            time.sleep(0.08)

        # final full tree with a star on top
        clear_screen()
        for r in range(height):
            width = 2 * r + 1
            row_chars = []
            for c in range(width):
                key = (r, c)
                if r == 0 and c == 0:
                    ch = '\033[93m\u2728\033[0m'  # sparkle star
                else:
                    ch = '\033[92m*\033[0m'
                row_chars.append(ch)
            row = ''.join(row_chars)
            pad = max(0, (term_w - len(remove_ansi(row))) // 2)
            sys.stdout.write(' ' * pad + row + '\n')

        sys.stdout.write('\n')
        trunk_height = max(2, height // 4)
        trunk_width = 3
        for _ in range(trunk_height):
            t = '\033[33m' + ('|' * trunk_width) + '\033[0m'
            pad = max(0, (term_w - len(remove_ansi(t))) // 2)
            sys.stdout.write(' ' * pad + t + '\n')

        sys.stdout.write('\n')
        sys.stdout.write(f"Merry Christmas, {name}!\n")
        sys.stdout.flush()
        time.sleep(1.0)

    finally:
        show_cursor()


def remove_ansi(s):
    # crude removal of ANSI sequences for length calculations
    import re

    return re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', s)


if __name__ == '__main__':
    main()
