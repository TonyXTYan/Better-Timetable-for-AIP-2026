# Page source

`build_program.py` builds `index.html` and `aip-2026-program.html` from these files:

- `page.html`: the HTML, from `<!DOCTYPE html>` to `</html>`, with the small scripts and
  styles in `<head>` that must run before the first paint. Two lines in it,
  `@@INCLUDE styles.css@@` and `@@INCLUDE js/*.js@@`, stand for the other files.
- `styles.css`: the page's main `<style>`.
- `js/`: the page's main `<script>`, in parts by area (see `js/README.md`).

`page_template()` in `build_program.py` replaces each `@@INCLUDE name@@` line with that file's
text exactly as written, or for a pattern (`js/*.js`) with the text of every file it matches,
in name order, joined with nothing between them (each file ends with a newline, which becomes
the end of its last line), then `main()` fills the other `@@...@@` placeholders (data, dates,
fonts, dark-theme tokens), in the CSS and JS as in the HTML.

When code is only moved between these files and `build_program.py`, the built page must stay
byte-for-byte the same: build before and after and compare with `cmp`.
