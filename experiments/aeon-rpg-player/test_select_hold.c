#include <assert.h>
#include "select_hold.h"
int main(void) {
    struct aeon_select_hold s={0};
    assert(!aeon_select_update(&s,true,false,100));
    assert(!aeon_select_update(&s,true,false,3000099));
    assert(aeon_select_update(&s,true,false,3000100));
    /* Menu opens while Select is still held: neither hold nor release resumes. */
    assert(!aeon_select_update(&s,true,true,3000101));
    assert(!aeon_select_update(&s,true,true,9000000));
    assert(!aeon_select_update(&s,false,true,9000100));
    /* A fresh tap resumes immediately, once. */
    assert(aeon_select_update(&s,true,true,9000200));
    assert(!aeon_select_update(&s,true,true,9000201));
    assert(!aeon_select_update(&s,true,false,9000202));
    assert(!aeon_select_update(&s,true,false,13000202));
    assert(!aeon_select_update(&s,false,false,13000300));
    /* Short game press never opens the menu. */
    assert(!aeon_select_update(&s,true,false,14000000));
    assert(!aeon_select_update(&s,false,false,14100000));
    assert(!aeon_select_update(&s,true,false,15000000));
    assert(!aeon_select_update(&s,true,false,17999999));
    assert(aeon_select_update(&s,true,false,18000000));
    /* Opening by another action while held also requires release. */
    struct aeon_select_hold t={0};
    assert(!aeon_select_update(&t,true,false,10));
    assert(!aeon_select_update(&t,true,true,20));
    assert(!aeon_select_update(&t,false,true,30));
    assert(aeon_select_update(&t,true,true,40));
    return 0;
}
