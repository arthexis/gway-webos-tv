#ifndef AEON_INPUT_H
#define AEON_INPUT_H
#include <stdint.h>
/* Physical SNES labels, not SDL's position-based face-button names. */
enum aeon_button { UP, DOWN, LEFT, RIGHT, A, B, X, Y, L, R, START, SELECT, BUTTON_COUNT };
static inline uint16_t aeon_bit(unsigned button) { return (uint16_t)(1u << button); }
static inline uint16_t aeon_sample(uint16_t buttons, int x, int y, int deadzone, int focused, int connected) {
    if (!focused || !connected) return 0;
    if (deadzone < 1 || deadzone > 32767) deadzone = 12000;
    if (x < -deadzone) buttons |= aeon_bit(LEFT);
    if (x > deadzone) buttons |= aeon_bit(RIGHT);
    if (y < -deadzone) buttons |= aeon_bit(UP);
    if (y > deadzone) buttons |= aeon_bit(DOWN);
    return buttons & (uint16_t)((1u << BUTTON_COUNT) - 1);
}
static inline uint16_t aeon_edges(uint16_t previous, uint16_t current) {
    return (uint16_t)(current & ~previous);
}
#endif
