#ifndef AEON_VOICE_CHORD_H
#define AEON_VOICE_CHORD_H
#include <stdbool.h>
#include <stdint.h>
#define AEON_VOICE_HOLD_US INT64_C(2000000)
struct aeon_voice_chord { int64_t start; bool timing, armed; };
/* Both buttons must be released before a fresh gesture, including after menu/focus loss. */
static inline bool aeon_voice_chord_update(struct aeon_voice_chord *s,
      bool left, bool right, bool gameplay, int64_t now)
{
    if (!gameplay) { s->timing=false; s->armed=false; return false; }
    if (!left && !right) { s->timing=false; s->armed=true; return false; }
    if (!left || !right) { s->timing=false; return false; }
    if (!s->armed) return false;
    if (!s->timing || now<s->start) { s->start=now; s->timing=true; return false; }
    if (now-s->start<AEON_VOICE_HOLD_US) return false;
    s->timing=false; s->armed=false; return true;
}
#endif
