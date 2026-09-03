#!/usr/bin/env python3
"""Lista los msgstr vacios de un .po. Codigo 1 si queda alguno."""
import re
import sys

FIELD = re.compile(r'^(msgid|msgstr|msgid_plural)\s+"(.*)"\s*$')
CONT = re.compile(r'^"(.*)"\s*$')


def parse(path):
    entries = []
    comments, key, buf = [], None, {"msgid": "", "msgstr": ""}
    current = None

    def flush():
        if key is not None and buf["msgid"]:
            entries.append((buf["msgid"], buf["msgstr"], list(comments)))

    with open(path, encoding="utf-8") as fobj:
        for line in fobj:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                if current is not None:
                    flush()
                    comments, buf, current, key = [], {"msgid": "", "msgstr": ""}, None, None
                comments.append(line)
                continue
            match = FIELD.match(line)
            if match:
                name, value = match.group(1), match.group(2)
                if name == "msgid":
                    key = value
                current = name if name in buf else None
                if current:
                    buf[current] = value
                continue
            match = CONT.match(line)
            if match and current:
                buf[current] += match.group(1)
    flush()
    return entries


def main():
    if len(sys.argv) != 2:
        print("uso: report_untranslated.py <archivo.po>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    entries = parse(path)
    missing = [(msgid, comments) for msgid, msgstr, comments in entries if not msgstr]
    total = len(entries)

    for msgid, comments in missing:
        refs = [c for c in comments if c.startswith("#:")]
        where = refs[0][2:].strip() if refs else "?"
        text = msgid if len(msgid) <= 90 else msgid[:87] + "..."
        print('  - "%s"' % text.replace("\\n", " "))
        print("      %s" % where)

    if not total:
        print("  (el archivo no tiene terminos exportables)")
        return 0
    if missing:
        print("")
        print("  %d de %d sin traducir." % (len(missing), total))
        return 1
    print("  ninguno: %d de %d traducidos." % (total, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
