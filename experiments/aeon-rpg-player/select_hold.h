#ifndef AEON_SELECT_HOLD_H
#define AEON_SELECT_HOLD_H
#include <stdbool.h>
#include <stdint.h>
#define AEON_SELECT_HOLD_US INT64_C(3000000)
struct aeon_select_hold { int64_t start; bool down; bool fired; bool menu_open; };
static inline bool aeon_select_update(struct aeon_select_hold *s, bool pressed, bool menu_open, int64_t now)
{
    if (s->menu_open != menu_open) {
        s->menu_open=menu_open;
        if (pressed) { s->down=true; s->fired=true; return false; }
    }
    if (!pressed) { s->down=false; s->fired=false; return false; }
    if (!s->down || now<s->start) {
        s->start=now; s->down=true; s->fired=menu_open; return menu_open;
    }
    if (!s->fired && now-s->start>=AEON_SELECT_HOLD_US) {
        s->fired=true; return true;
    }
    return false;
}
#endif
