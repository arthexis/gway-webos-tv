#include <assert.h>
#include "voice_chord.h"
int main(void) {
    struct aeon_voice_chord s={0};
    assert(!aeon_voice_chord_update(&s,1,1,1,0));
    assert(!aeon_voice_chord_update(&s,0,0,1,1));
    assert(!aeon_voice_chord_update(&s,1,0,1,10));
    assert(!aeon_voice_chord_update(&s,1,1,1,20));
    assert(!aeon_voice_chord_update(&s,1,1,1,2000019));
    assert(aeon_voice_chord_update(&s,1,1,1,2000020));
    assert(!aeon_voice_chord_update(&s,1,1,1,9000000));
    assert(!aeon_voice_chord_update(&s,0,1,1,9000001));
    assert(!aeon_voice_chord_update(&s,1,1,1,12000000));
    assert(!aeon_voice_chord_update(&s,0,0,1,12000001));
    assert(!aeon_voice_chord_update(&s,1,1,1,12000002));
    assert(!aeon_voice_chord_update(&s,1,1,0,15000000));
    assert(!aeon_voice_chord_update(&s,1,1,1,18000000));
    assert(!aeon_voice_chord_update(&s,0,0,1,18000001));
    assert(!aeon_voice_chord_update(&s,1,1,1,18000002));
    assert(!aeon_voice_chord_update(&s,1,0,1,19000000));
    assert(!aeon_voice_chord_update(&s,1,1,1,20000000));
    assert(aeon_voice_chord_update(&s,1,1,1,22000000));
    return 0;
}
