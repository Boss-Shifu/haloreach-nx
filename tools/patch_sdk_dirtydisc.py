#!/usr/bin/env python3
"""Parche idempotente: XamShowDirtyDiscErrorUI no mata el proceso si existe <logs/rex>/sigue_disco.flag
(solo registra y regresa). Sirve para ver si el juego continua tras el 'Disc Read Error'.
Uso: patch_sdk_dirtydisc.py <xam_ui.cpp>"""
import sys
p = sys.argv[1]
s = open(p).read()
if 'FH2_DIRTYDISC' in s:
    print('dirtydisc ya parcheado'); sys.exit(0)
anchor = '''void XamShowDirtyDiscErrorUI_entry(u32 user_index) {
  REXKRNL_ERROR("XamShowDirtyDiscErrorUI called! user_index={}", uint32_t(user_index));
'''
assert s.count(anchor) == 1, s.count(anchor)
new = 'extern "C" const char* RexSwitchLogDir(void);\n' + anchor + '''  {  // FH2_DIRTYDISC
    std::string flag_fh2 = std::string(RexSwitchLogDir()) + "sigue_disco.flag";
    if (FILE* f_fh2 = std::fopen(flag_fh2.c_str(), "r")) {
      std::fclose(f_fh2);
      REXKRNL_ERROR("[fh2] XamShowDirtyDiscErrorUI ignorado (existe sigue_disco.flag): el juego sigue");
      return;
    }
  }
'''
s = s.replace(anchor, new)
for inc in ('#include <cstdio>', '#include <string>'):
    if inc not in s:
        s = inc + '\n' + s
open(p, 'w').write(s)
print('dirtydisc parcheado')
