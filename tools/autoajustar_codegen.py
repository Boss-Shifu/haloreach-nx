#!/usr/bin/env python3
"""Arregla solo los errores "target not in any function" del codegen (perfil generico de xbox2switch).

Corre `rexglue codegen` sobre el manifiesto; si la validacion se queja de saltos a direcciones que no pertenecen a ninguna
funcion, calcula el tamano de cada una leyendo la imagen del juego (REXGLUE_DUMP_IMAGE), la agrega a project/overrides.toml
y vuelve a correr (hasta MAX vueltas). Las vueltas que fallan son rapidas (la validacion ocurre antes de generar codigo).

uso: autoajustar_codegen.py <rexglue> <carpeta project> [manifiesto]
"""
import glob, os, re, struct, subprocess, sys, tempfile

MAX = 12
LIM = 0x4000  # bytes maximos que se miran por funcion


def tam_funcion(img, base, ini):
    """Tamano en bytes de la funcion que empieza en `ini` (heuristica: hasta el primer blr/bctr/salto que no vuelve a ella)."""
    off = ini - base
    fin_img = len(img)
    fwd = ini
    a = ini
    while a - ini < LIM and (a - base) + 4 <= fin_img:
        w = struct.unpack_from('>I', img, a - base)[0]
        op = w >> 26
        if w in (0x4E800020, 0x4E800420):  # blr, bctr
            if a >= fwd:
                return a + 4 - ini
        elif op == 18:  # b / bl / ba
            li = w & 0x03FFFFFC
            if li & 0x02000000:
                li -= 0x04000000
            tgt = li if (w & 2) else a + li
            if not (w & 1):  # salto sin enlace
                if ini <= tgt <= a:
                    pass  # bucle dentro de la funcion
                elif a >= fwd:
                    return a + 4 - ini  # cola: salta a otra funcion
        elif op == 16:  # bc
            bd = w & 0xFFFC
            if bd & 0x8000:
                bd -= 0x10000
            tgt = bd if (w & 2) else a + bd
            if not (w & 1) and tgt > a:
                fwd = max(fwd, tgt)
        a += 4
    return None


def imagenes(carpeta):
    out = []
    for f in glob.glob(os.path.join(carpeta, 'image_*.bin')):
        base = int(re.search(r'image_([0-9A-Fa-f]+)\.bin', f).group(1), 16)
        out.append((base, open(f, 'rb').read()))
    return out


def main():
    rex, proy = sys.argv[1], sys.argv[2]
    man = sys.argv[3] if len(sys.argv) > 3 else 'fh2_manifest.toml'
    ov = os.path.join(proy, 'overrides.toml')
    agregadas = {}
    for vuelta in range(1, MAX + 1):
        dump = tempfile.mkdtemp()
        env = dict(os.environ, REXGLUE_DUMP_IMAGE=dump)
        r = subprocess.run([rex, 'codegen', man], cwd=proy, env=env, capture_output=True, text=True)
        texto = (r.stdout or '') + (r.stderr or '')
        faltan = sorted({int(m, 16) for m in re.findall(r'0x([0-9A-Fa-f]{8}) from 0x[0-9A-Fa-f]{8}[^\n]*target not in any function', texto)})
        nuevos = [t for t in faltan if t not in agregadas]
        print(f'[auto] vuelta {vuelta}: codigo {r.returncode}, {len(faltan)} direcciones sin funcion ({len(nuevos)} nuevas)')
        if r.returncode == 0:
            print('[auto] el codegen paso. Ajustes agregados:', len(agregadas))
            return 0
        if not nuevos:
            print(texto[-4000:])
            print('[auto] el error no es de funciones faltantes (o ya se intento arreglar). No puedo seguir solo.')
            return 1
        imgs = imagenes(dump)
        lineas = []
        for t in nuevos:
            tam = None
            for base, img in imgs:
                if base <= t < base + len(img):
                    tam = tam_funcion(img, base, t)
                    break
            if tam is None:
                print(f'[auto] no pude medir 0x{t:08X}; se deja sin arreglar')
                continue
            agregadas[t] = tam
            lineas.append(f'"0x{t:08X}" = {{ size = 0x{tam:X} }}')
        if not lineas:
            print(texto[-4000:])
            return 1
        txt = open(ov, encoding='utf-8').read() if os.path.exists(ov) else ''
        if not re.search(r'^\[functions\]', txt, re.M):
            txt += '\n[functions]\n'
        txt += f'\n# --- agregado solo por autoajustar_codegen.py (vuelta {vuelta}) ---\n' + '\n'.join(lineas) + '\n'
        open(ov, 'w', encoding='utf-8').write(txt)
    print('[auto] se acabaron las vueltas')
    return 1


if __name__ == '__main__':
    sys.exit(main())
