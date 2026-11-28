#include <assert.h>
#include "select_hold.h"
int main(void) {
    struct aeon_select_hold s={0};
    assert(!aeon_select_update(&s,true,100));
    assert(!aeon_select_update(&s,true,3000099));
    assert(aeon_select_update(&s,true,3000100));
    assert(!aeon_select_update(&s,true,9000000));
    assert(!aeon_select_update(&s,false,9000100));
    assert(!aeon_select_update(&s,true,9000200));
    assert(!aeon_select_update(&s,false,10000200));
    assert(!aeon_select_update(&s,true,11000000));
    assert(!aeon_select_update(&s,true,13999999));
    assert(aeon_select_update(&s,true,14000000));
    assert(!aeon_select_update(&s,true,14000001));
    return 0;
}
