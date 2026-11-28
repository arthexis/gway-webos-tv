#ifndef AEON_PROBE_EVENTS_H
#define AEON_PROBE_EVENTS_H
#include <stddef.h>
#include <stdint.h>
#define PROBE_WINDOW_MS 180000u
#define PROBE_ROWS 8
typedef struct { int mapped, button, down; } probe_edge;
typedef struct { probe_edge rows[PROBE_ROWS]; unsigned count, total; } probe_history;
static inline int probe_record(probe_history *h,int32_t selected,int32_t source,
                              int focused,uint32_t elapsed,int mapped,int button,int down) {
    if(selected<0 || source!=selected || !focused || elapsed>=PROBE_WINDOW_MS || button<0 || button>255)return 0;
    for(unsigned i=PROBE_ROWS-1;i>0;i--)h->rows[i]=h->rows[i-1];
    h->rows[0]=(probe_edge){mapped,button,!!down};
    if(h->count<PROBE_ROWS)h->count++;
    h->total++;
    return 1;
}
#endif
