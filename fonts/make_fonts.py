#!/usr/bin/env python3
"""Make the Archivo subsets in fonts/ (run by hand; build_program.py only reads the results).

The page uses one family, Archivo (variable: weight and width axes, roman and italic), inlined as
base64 woff2 so it works offline. This script cuts the fontsource files down to what the page
needs:

    mkdir -p /tmp/archivo && cd /tmp/archivo && npm pack @fontsource-variable/archivo@5.3.0
    tar -xzf fontsource-variable-archivo-5.3.0.tgz
    python3 fonts/make_fonts.py /tmp/archivo/package/files

Needs fontTools and brotli (pip install fonttools brotli). For each style it limits the axes
(roman: wght 400-800, wdth 75-125; italic: wght 400-700 at wdth 100), then keeps only the
characters found in build_program.py, the page's source in src/ (page.html, styles.css and
js/*.js, as build_program.py joins them; not the READMEs) and aip2026-data.json plus Latin-1 and
typographic punctuation (other characters fall back to the system font, glyph by glyph), and the
OpenType features the page uses. fontsource splits the font into a "latin" and a "latin-ext"
file; both are kept, each with its own unicode-range, which build_program.py reads from
fonts/fonts.json.
"""
import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build_program import page_template  # noqa: E402
OUT = ROOT / 'fonts'
FEATURES = ['kern', 'liga', 'tnum', 'pnum', 'frac', 'numr', 'dnom', 'case', 'ccmp', 'locl',
            'mark', 'mkmk', 'rvrn']
STYLES = {
    'roman': dict(src='normal', axes={'wght': (400, 800), 'wdth': (75, 125)}),
    'italic': dict(src='italic', axes={'wght': (400, 700), 'wdth': 100}),
}


def wanted_codepoints():
    text = (ROOT / 'build_program.py').read_text(encoding='utf-8')
    text += page_template(ROOT)   # the page's HTML, CSS and JS, from src/ (not its READMEs)
    text += (ROOT / 'aip2026-data.json').read_text(encoding='utf-8')
    cps = {ord(c) for c in text}
    cps |= set(range(0x20, 0x7F)) | set(range(0xA0, 0x100))
    cps |= set(range(0x2010, 0x2028)) | set(range(0x2030, 0x203B))
    cps |= {0x2044, 0x20AC, 0x2122, 0x2212, 0x2190, 0x2192, 0x2215}
    return cps


def ranges(cps):
    """'U+20-7E,U+A0' style unicode-range for a sorted set of code points."""
    out, cps = [], sorted(cps)
    i = 0
    while i < len(cps):
        j = i
        while j + 1 < len(cps) and cps[j + 1] == cps[j] + 1:
            j += 1
        out.append('U+%X' % cps[i] if i == j else 'U+%X-%X' % (cps[i], cps[j]))
        i = j + 1
    return ','.join(out)


def main(src_dir):
    src_dir = Path(src_dir)
    want = wanted_codepoints()
    meta = []
    for style, cfg in STYLES.items():
        taken = set()
        for part in ('latin', 'latin-ext'):
            src = src_dir / f'archivo-{part}-standard-{cfg["src"]}.woff2'
            font = TTFont(src)
            cmap = set(font.getBestCmap())
            # the latin file wins any character both files have
            keep = (cmap & want) - taken
            if not keep:
                continue
            taken |= keep
            font = instancer.instantiateVariableFont(font, cfg['axes'])
            opts = subset.Options()
            opts.layout_features = FEATURES
            opts.flavor = 'woff2'
            opts.name_IDs = ['*']
            opts.notdef_outline = True
            opts.hinting = False
            opts.desubroutinize = True
            sub = subset.Subsetter(opts)
            sub.populate(unicodes=keep)
            sub.subset(font)
            name = f'archivo-{style}-{part}.woff2'
            font.flavor = 'woff2'
            font.save(OUT / name)
            size = (OUT / name).stat().st_size
            wght = cfg['axes']['wght']
            wdth = cfg['axes']['wdth']
            meta.append({
                'file': name,
                'style': 'italic' if style == 'italic' else 'normal',
                'weight': '%d %d' % wght,
                'stretch': '%d%% %d%%' % wdth if isinstance(wdth, tuple) else '%d%%' % wdth,
                'unicode_range': ranges(keep),
            })
            print(f'{name}: {len(keep)} characters, {size / 1024:.1f} KB')
    (OUT / 'fonts.json').write_text(json.dumps(meta, indent=1) + '\n', encoding='utf-8')
    total = sum((OUT / m['file']).stat().st_size for m in meta)
    print(f'total {total / 1024:.1f} KB')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
