#!/usr/bin/env python3
"""Diagnostico: el error 'failed to find contiguous range' ahora dice cuanto se pidio y cuanto queda libre."""
import sys
p = sys.argv[1]
s = open(p).read()
old = 'REXSYS_ERROR("BaseHeap::Alloc failed to find contiguous range");'
new = '''{
      size_t free_pages_diag = 0, largest_run_diag = 0, run_diag = 0;
      for (size_t pi = 0; pi < page_table_.size(); ++pi) {
        if (page_table_[pi].state == 0) { ++free_pages_diag; ++run_diag; if (run_diag > largest_run_diag) largest_run_diag = run_diag; }
        else run_diag = 0;
      }
      REXSYS_ERROR("BaseHeap::Alloc failed to find contiguous range: heap_base=0x{:08X} page_size=0x{:X} pidio {} paginas (alineacion 0x{:X}, top_down={}), libres {} de {}, bloque libre mayor {} paginas",
                   heap_base_, page_size_, page_count, alignment, top_down, free_pages_diag, page_table_.size(), largest_run_diag);
    }'''
if 'pidio {} paginas' in s:
    print('ya parcheado'); sys.exit(0)
assert s.count(old) == 1, s.count(old)
open(p, 'w').write(s.replace(old, new))
print('parcheado')
