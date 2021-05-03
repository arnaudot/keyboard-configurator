#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import List, Tuple, Dict

QMK_MAPPING = {
    'APPLICATION': 'APP',
    'AUDIO_MUTE': 'MUTE',
    'AUDIO_VOL_DOWN': 'VOLUME_DOWN',
    'AUDIO_VOL_UP': 'VOLUME_UP',
    'BSLASH': 'BACKSLASH',
    'BSPACE': 'BKSP',
    'CAPSLOCK': 'CAPS',
    'DELETE': 'DEL',
    'DOT': 'PERIOD',
    'EQUAL': 'EQUALS',
    'ESCAPE': 'ESC',
    'GRAVE': 'TICK',
    'KP_0': 'NUM_0',
    'KP_1': 'NUM_1',
    'KP_2': 'NUM_2',
    'KP_3': 'NUM_3',
    'KP_4': 'NUM_4',
    'KP_5': 'NUM_5',
    'KP_6': 'NUM_6',
    'KP_7': 'NUM_7',
    'KP_8': 'NUM_8',
    'KP_9': 'NUM_9',
    'KP_ASTERISK': 'NUM_ASTERISK',
    'KP_COMMA': 'NUM_COMMA',
    'KP_DOT': 'NUM_PERIOD',
    'KP_ENTER': 'NUM_ENTER',
    'KP_EQUAL': 'NUM_EQUALS',
    'KP_MINUS': 'NUM_MINUS',
    'KP_PLUS': 'NUM_PLUS',
    'KP_SLASH': 'NUM_SLASH',
    'LALT': 'LEFT_ALT',
    'LBRACKET': 'BRACE_OPEN',
    'LCTRL': 'LEFT_CTRL',
    'LGUI': 'LEFT_SUPER',
    'LSHIFT': 'LEFT_SHIFT',
    'NO': 'NONE',
    'MEDIA_NEXT_TRACK': 'MEDIA_NEXT',
    'MEDIA_PLAY_PAUSE': 'PLAY_PAUSE',
    'MEDIA_PREV_TRACK': 'MEDIA_PREV',
    'NUMLOCK': 'NUM_LOCK',
    'PGDOWN': 'PGDN',
    'PSCREEN': 'PRINT_SCREEN',
    'RALT': 'RIGHT_ALT',
    'RBRACKET': 'BRACE_CLOSE',
    'RCTRL': 'RIGHT_CTRL',
    'RGB_TOG': 'KBD_TOGGLE',
    'RGB_VAD': 'KBD_DOWN',
    'RGB_VAI': 'KBD_UP',
    'RGUI': 'RIGHT_SUPER',
    'RSHIFT': 'RIGHT_SHIFT',
    'SCOLON': 'SEMICOLON',
    'SYSTEM_SLEEP': 'SUSPEND',
    'TRANSPARENT': 'ROLL_OVER',
}

ALIAS_RE = '#define\s+KC_([A-Z_]*)\s+KC_([A-Z_]+]*)\s*$'

# keycode_h = open('tmk_core/common/keycode.h').read()
# [(i.group(1), i.group(2)) for i in (re.match('#define\s+KC_([A-Z_]*)\s+KC_([A-Z_]+]*)\s*$', i) for i in keycode_h.splitlines()) if i]

def call_preprocessor(path: str) -> str:
    return subprocess.check_output(["gcc", "-E", path], stderr=subprocess.DEVNULL, universal_newlines=True)

def extract_scancodes(ecdir: str, is_qmk: bool) -> Tuple[List[Tuple[str, int]], Dict[str, str]]:
    "Extract mapping from scancode names to numbers"

    if is_qmk:
        includes = [f"{ecdir}/tmk_core/common/keycode.h", f"{ecdir}/quantum/quantum_keycodes.h"]
        common_keymap_h = call_preprocessor(includes[0])
        quantum_keycode_h = call_preprocessor(includes[1])
        scancode_defines = re.findall(
            '    (KC_[^,\s]+)', common_keymap_h)
        scancode_defines += re.findall(
            '    (RGB_[^,\s]+)', quantum_keycode_h)
        define_aliases = [(i.group(1), i.group(2)) for i in (re.match(ALIAS_RE, i) for i in open(includes[0])) if i]
        mapping = QMK_MAPPING
        mapping.update({alias: QMK_MAPPING.get(keycode, keycode) for alias, keycode in define_aliases})
        for (alias, keycode) in define_aliases:
            mapping[alias] = QMK_MAPPING.get(keycode, keycode)
    else:
        includes = [f"{ecdir}/src/common/include/common/keymap.h"]
        common_keymap_h = open(includes[0]).read()
        scancode_defines = re.findall(
            '#define.*((?:K_\S+)|(?:KT_FN))', common_keymap_h)
        mapping = {}

    tmpdir = tempfile.mkdtemp()
    with open(f'{tmpdir}/keysym-extract.c', 'w') as f:
        f.write('#include <stdio.h>\n')
        f.write('int main() {\n')
        for i in scancode_defines:
            f.write(f'printf("%d ", {i});\n')
        f.write('}\n')

    cmd = ['gcc']
    for i in includes:
        cmd.append('-include')
        cmd.append(i)
    cmd += ['-o', f'{tmpdir}/keysym-extract', f'{tmpdir}/keysym-extract.c']
    subprocess.check_call(cmd)

    output = subprocess.check_output(
        f'{tmpdir}/keysym-extract', universal_newlines=True)

    shutil.rmtree(tmpdir)

    scancode_names = []
    for i in scancode_defines:
        a, b = i.split('_', 1)
        if a in ['RGB']:
            scancode_names.append(i)
        else:
            scancode_names.append(b)
    if is_qmk:
        scancode_names = [mapping.get(i, i) for i in scancode_names]
    scancodes = (int(i) for i in output.split())
    scancode_list = list(zip(scancode_names, scancodes))

    if is_qmk:
        scancode_list.append(('LAYER_TOGGLE_1', 0x5300)) # TG(0)
        scancode_list.append(('LAYER_TOGGLE_2', 0x5301)) # TG(1)
        scancode_list.append(('LAYER_TOGGLE_3', 0x5302)) # TG(2)
        scancode_list.append(('LAYER_TOGGLE_4', 0x5303)) # TG(3)
        scancode_list.append(('LAYER_ACCESS_1', 0x5100)) # MO(0)
        scancode_list.append(('FN', 0x5101)) # MO(1)
        scancode_list.append(('LAYER_ACCESS_3', 0x5102)) # MO(2)
        scancode_list.append(('LAYER_ACCESS_4', 0x5103)) # MO(3)
        scancode_list.append(('RESET', 0x5C00))
    else:
        scancode_list.append(('NONE', 0x0000))

    scancode_list = [(name, code) for (name, code) in scancode_list if name not in ('INT_1', 'INT_2')]

    # Make sure scancodes are unique
    assert len(scancode_list) == len(set(i for _, i in scancode_list))

    return scancode_list, mapping


def parse_layout_define(keymap_h: str, is_qmk) -> Tuple[List[str], List[List[str]]]:
    keymap_h = re.sub(r'/\*.*?\*/', '', keymap_h)
    # XXX split up regex?
    m = re.search(
        r'LAYOUT\((.*?)\)[\s\\]*({[^{}]*({[^{}]*}[^{}]*)+)[^{}]*}', keymap_h, re.MULTILINE | re.DOTALL)
    assert m is not None
    physical = m.group(1).replace(',', ' ').replace('\\', '').split()
    # XXX name?
    physical2 = [i.replace('\\', '').replace(',', '').split()
                 for i in m.group(2).replace('{', '').split('}')[:-1]]
    assert is_qmk or all(len(i) == len(physical2[0]) for i in physical2)
    return physical, physical2

def parse_led_config(led_c: str, physical: List[str]) -> Dict[str, List[int]]:
    led_c = re.sub(r'//.*', '', led_c)
    led_c = re.sub(r'/\*.*?\*/', '', led_c)
    m = re.search(r'LAYOUT\((.*?)\)', led_c, re.MULTILINE | re.DOTALL)
    leds: Dict[str, List[int]] = {}
    if m is None:
        return leds
    led_indexes = m.group(1).replace(',', ' ').replace('\\', '').split()
    for i, physical_name in enumerate(physical):
        leds[physical_name] = [int(led_indexes[i])]
    return leds

def parse_keymap(keymap_c: str, mapping: Dict[str, str], physical: List[str], is_qmk: bool) -> Dict[str, List[str]]:
    # XXX for launch
    keymap_c = keymap_c.replace('MO(1)', 'FN')
    keymap_c = re.sub(r'/\*.*?\*/', '', keymap_c)

    layer_scancodes: List[List[str]] = []
    for layer in re.finditer(r'LAYOUT\((.*?)\)', keymap_c, re.MULTILINE | re.DOTALL):
        scancodes = layer.group(1).replace(',', ' ').split()
        assert len(scancodes) == len(physical)

        def scancode_map(x: int, code: str) -> str:
            if code == '0':
                return 'NONE'

            code = code.replace('K_', '').replace('KC_', '').replace('KT_', '')

            if is_qmk:
                code = mapping.get(code, code)

            return code

        scancodes = [scancode_map(x, i) for x, i in enumerate(scancodes)]
        layer_scancodes.append(scancodes)

    keymap = {}
    for i, physical_name in enumerate(physical):
        keymap[physical_name] = [j[i] for j in layer_scancodes]

    return keymap


def gen_layout_json(path: str, physical: List[str], physical2: List[List[str]]) -> None:
    "Generate layout.json file"

    layout = {}
    for p in physical:
        x, y = next((x, y) for x, i in enumerate(physical2)
                    for y, j in enumerate(i) if j == p)
        layout[p] = (x, y)

    with open(path, 'w') as f:
        json.dump(layout, f, indent=2)

def gen_keymap_json(path: str, scancodes: List[Tuple[str, int]]) -> None:
    "Generate keymap.json file"

    with open(path, 'w') as f:
       json.dump(scancodes, f, indent=2)

def gen_leds_json(path: str, leds: Dict[str, List[int]]) -> None:
    "Generate leds.json file"

    with open(path, 'w') as f:
       json.dump(leds, f, indent=2)

def gen_default_json(path: str, board: str, keymap: Dict[str, List[str]], is_qmk: bool) -> None:
    "Generate default.json file"

    with open(path, 'w') as f:
        if is_qmk:
            key_leds = {k: None for k in keymap.keys()}
            layers = [
                {"mode": (7, 127), "brightness": 176, "color": (142, 255)},
                {"mode": (13, 127), "brightness": 176, "color": (142, 255)},
                {"mode": (13, 127), "brightness": 176, "color": (142, 255)},
                {"mode": (13, 127), "brightness": 176, "color": (142, 255)},
            ]
        else:
            key_leds = {}
            layers = [{"mode": None, "brightness": 0, "color": (0, 0)}]
        json.dump({"model": board, "map": keymap, "key_leds": key_leds, "layers": layers}, f, indent=2)


def generate_layout_dir(ecdir: str, board: str, is_qmk: bool) -> None:
    layoutdir = f'layouts/{board}'
    print(f'Generating {layoutdir}...')

    if is_qmk:
        keymap_h = open(
            f"{ecdir}/keyboards/{board}/{board.split('/')[-1]}.h").read()
        default_c = open(
            f"{ecdir}/keyboards/{board}/keymaps/default/keymap.c").read()
        led_c = open(
            f"{ecdir}/keyboards/{board}/{board.split('/')[-1]}.c").read()
    else:
        keymap_h = open(
            f"{ecdir}/src/board/{board}/include/board/keymap.h").read()
        default_c = open(f"{ecdir}/src/board/{board}/keymap/default.c").read()
        led_c = ""

    os.makedirs(f'{layoutdir}', exist_ok=True)

    physical, physical2 = parse_layout_define(keymap_h, is_qmk)
    leds = parse_led_config(led_c, physical)
    scancodes, mapping = extract_scancodes(ecdir, is_qmk)
    default_keymap = parse_keymap(default_c, mapping, physical, is_qmk)
    gen_layout_json(f'{layoutdir}/layout.json', physical, physical2)
    gen_leds_json(f'{layoutdir}/leds.json', leds)
    gen_keymap_json(f'{layoutdir}/keymap.json', scancodes)
    gen_default_json(f'{layoutdir}/default.json', board, default_keymap, is_qmk)


parser = argparse.ArgumentParser()
parser.add_argument("ecdir")
parser.add_argument("board")
parser.add_argument("--qmk", action="store_true")
args = parser.parse_args()

if args.board == 'all':
    if args.qmk:
        boarddir = f'{args.ecdir}/keyboards/system76'
    else:
        boarddir = f'{args.ecdir}/src/board/system76'
    for i in os.listdir(boarddir):
        if i == 'common' or not os.path.isdir(f'{boarddir}/{i}'):
            continue
        generate_layout_dir(args.ecdir, f'system76/{i}', args.qmk)
else:
    generate_layout_dir(args.ecdir, args.board, args.qmk)
