#!/usr/bin/python3
import struct
import json
import os

LINE_LEN = 0xB4
START_OFFSET = 0x30
END_OFFSET = START_OFFSET + 1200 * LINE_LEN
OLD_AILMENTS = ['Bind', 'Charm', 'Daze', 'Mute', 'Panic', 'Poison', 'Sick', 'Sleep']

RESIST_LVLS = {
    0: '-',
    1: 'n',
    2: 'w',
    3: 'r',
    4: 'd',
    5: 's'
}

RESIST_MODS = {
    'd': 100,
    'r': 100,
    'n': 100,
    's': 50,
    '-': 100,
    'w': 125,
    'W': 200,
    'X': 300
}

AILMENTS = [
    'ELEM_009',
    'ELEM_010',
    'ELEM_011',
    'Poison',
    'Panic',
    'Sleep',
    'Bind',
    'Sick',
    'ELEM_017',
    'Charm',
    'Daze',
    'Mute',
    'ELEM_021'
]

AILMENT_ORDER = [AILMENTS.index(x) for x in OLD_AILMENTS]

with open('../../../megaten-fusion-tool/src/app/smt4f/data/demon-data.json') as jsonfile:
    OLD_DEMONS = json.load(jsonfile)
with open('data/demon-ids.tsv') as tsvfile:
    DEMON_IDS = ['BLANK\t0'] + [x.strip() for x in tsvfile]
with open('data/skill-ids.tsv') as tsvfile:
    SKILL_IDS = ['BLANK'] + [x.strip() for x in tsvfile]
with open('data/race-ids.tsv') as tsvfile:
    RACE_IDS = ['BLANK'] + [x.strip() for x in tsvfile]

SEEN_DEMONS = { x: False for x in OLD_DEMONS }

def printif_notequal(dname, field, lhs, rhs):
    if str(lhs) != str(rhs):
        print(dname, field, lhs, rhs)

def save_ordered_demons(demons, fname):
    for entry in demons.values():
        for stat_set in ['resmods', 'ailmods', 'affinities', 'stats']:
            if stat_set in entry:
                entry[stat_set] = '[' + ', '.join(str(x) for x in entry[stat_set]) + ']'
        if 'skills' in entry:
            nskills = sorted(entry['skills'].items(), key=lambda x: x[1])
            nskills = '{||      ' + ',||      '.join(f'|{x[0]}|: {x[1]}' for x in nskills) + '||    }'
            entry['skills'] = nskills

    jstring = json.dumps(demons, indent=2, sort_keys=True)
    jstring = jstring.replace('||', '\n').replace('|', '"')
    jstring = jstring.replace('"[', '[').replace(']"', ']').replace('"{', '{').replace('}"', '}')

    with open(fname, 'w+') as jsonfile:
        jsonfile.write(jstring)

def check_demon_data(fname, start_offset, end_offset, line_len):
    with open(fname, 'rb') as binfile:
        new_demons = binfile.read()
    is_dlc = end_offset == -1

    for d_id, line_start in enumerate(range(start_offset, len(new_demons) if is_dlc else end_offset, line_len)):
        line = new_demons[line_start:line_start + LINE_LEN]
        new_d_id = struct.unpack('<1H', line[0x00:0x02])[0]

        if is_dlc:
            d_id = new_d_id

        dname, in_comp = DEMON_IDS[d_id].split('\t')

        if not is_dlc and int(in_comp) != 1:
            continue
        if is_dlc and int(in_comp) != 2:
            break

        demon = OLD_DEMONS[dname]
        SEEN_DEMONS[dname] = True

        race_id = struct.unpack('<1L', line[0x02:0x06])[0]
        dlvl = struct.unpack('<1H', line[0x06:0x08])[0]
        stats = struct.unpack('<5H', line[0x1E:0x28])
        innate = struct.unpack('<8H', line[0x40:0x50])
        learned = struct.unpack('<16H', line[0x50:0x70])
        full_resists = struct.unpack('<8H', line[0x70:0x80])
        full_ailments = struct.unpack('<13H', line[0x80:0x9A])
        full_affinities = struct.unpack('<16b', line[0xA2:0xB2])

        printif_notequal(dname, 'd_id', d_id, new_d_id)
        printif_notequal(dname, 'race', demon['race'], RACE_IDS[race_id])
        printif_notequal(dname, 'lvl', demon['lvl'], dlvl)
        printif_notequal(dname, 'stats', demon['stats'][2:], list(stats))

        resists = ''.join(RESIST_LVLS[x >> 10] for x in full_resists)
        ailments = ''.join(RESIST_LVLS[full_ailments[x] >> 10] for x in AILMENT_ORDER)
        affinities = list(full_affinities[:8]) + [full_affinities[x] for x in (8, 12, 10, 14)]
        res_mods = [x & 0x3FF for x in full_resists]
        ail_mods = [full_ailments[x] & 0x3FF for x in AILMENT_ORDER]

        old_resists = demon['resists']
        old_ailments = demon.get('ailments', '--------')
        old_res_mods = demon.get('resmods', [0]*8).copy()
        old_ail_mods = demon.get('ailmods', [0]*8).copy()

        for i, res_mod in enumerate(old_res_mods):
            if res_mod == 0:
                old_res_mods[i] = RESIST_MODS[old_resists[i]]
        for i, ail_mod in enumerate(old_ail_mods):
            if ail_mod == 0:
                old_ail_mods[i] = RESIST_MODS[old_ailments[i]]

        old_resists = old_resists.replace('W', 'w').replace('X', 'w')
        old_ailments = old_ailments.replace('W', 'w').replace('X', 'w')

        printif_notequal(dname, 'resists', old_resists, resists)
        printif_notequal(dname, 'ailments', old_ailments, ailments)
        printif_notequal(dname, 'affinities', demon['affinities'], affinities)
        printif_notequal(dname, 'res_mods', old_res_mods, res_mods)
        printif_notequal(dname, 'ail_mods', old_ail_mods, ail_mods)

        skills = demon['skills']

        for i, s_id in enumerate(innate):
            sname = SKILL_IDS[s_id]
            if s_id == 0:
                continue
            if sname not in skills or skills[sname] > 1:
                print(dname, sname, 0, skills)
            else:
                skills[sname] = (i + 1) / 10

        for i in range(0, 16, 2):
            slvl, s_id = learned[i:i + 2]
            sname = SKILL_IDS[s_id]
            if s_id == 0:
                continue
            if sname not in skills or skills[sname] != slvl:
                print(dname, sname, slvl, skills)
            else:
                skills[sname] = slvl

check_demon_data('data/battle/NKMBaseTable.bin', START_OFFSET, END_OFFSET, LINE_LEN)

DLC_DIR = 'data/addon/testdata/'
DLC_FILES = [x for x in os.listdir(DLC_DIR) if x.endswith('-tbl-NKMBaseTable.bin')]

for fname in sorted(DLC_FILES):
    check_demon_data(DLC_DIR + fname, START_OFFSET, -1, LINE_LEN)

for dname, seen in SEEN_DEMONS.items():
    if not seen:
        print(dname)

save_ordered_demons(OLD_DEMONS, 'demon-data.json')
