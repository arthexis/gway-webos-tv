#include <assert.h>
#include "probe_events.h"
int main(void) {
    probe_history h={0};
    assert(!probe_record(&h,-1,-1,1,0,0,13,1));
    assert(!probe_record(&h,7,8,1,0,0,13,1));
    assert(!probe_record(&h,7,7,0,0,0,13,1));
    assert(!probe_record(&h,7,7,1,PROBE_WINDOW_MS,0,13,1));
    assert(probe_record(&h,7,7,1,0,0,13,1));
    assert(probe_record(&h,7,7,1,1,1,5,1));
    assert(probe_record(&h,7,7,1,2,0,13,0));
    assert(h.rows[0].button==13 && !h.rows[0].down);
    assert(h.rows[1].mapped && h.rows[1].button==5);
    assert(h.total==3 && h.count==3);
    for(int i=0;i<20;i++)assert(probe_record(&h,7,7,1,3,0,i,1));
    assert(h.count==PROBE_ROWS && h.total==23 && h.rows[0].button==19 && h.rows[7].button==12);
    return 0;
}
