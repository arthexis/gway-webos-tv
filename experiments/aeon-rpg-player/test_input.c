#include <assert.h>
#include "input.h"
int main(void) {
    uint16_t a = aeon_bit(A);
    assert(aeon_sample(a, 0, 0, 12000, 1, 1) == a);
    assert(aeon_sample(a, 12000, -12000, 12000, 1, 1) == a);
    assert(aeon_sample(a, 12001, -12001, 12000, 1, 1) == (a | aeon_bit(RIGHT) | aeon_bit(UP)));
    assert(aeon_sample(a, -32768, 32767, 12000, 1, 1) == (a | aeon_bit(LEFT) | aeon_bit(DOWN)));
    assert(aeon_sample(a, 32767, 32767, 12000, 0, 1) == 0);
    assert(aeon_sample(a, 32767, 32767, 12000, 1, 0) == 0);
    assert(aeon_edges(a, a) == 0);
    assert(aeon_edges(a, a | aeon_bit(B)) == aeon_bit(B));
    assert(aeon_sample(0xffff, 0, 0, 12000, 1, 1) == (1u << BUTTON_COUNT) - 1);
    return 0;
}
