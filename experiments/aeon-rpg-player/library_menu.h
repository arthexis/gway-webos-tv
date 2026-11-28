#ifndef AEON_LIBRARY_MENU_H
#define AEON_LIBRARY_MENU_H
/* Runs a game while keeping the launcher surface alive. */
typedef int (*aeon_play_fn)(const char *content, void *context);
typedef int (*aeon_pair_fn)(const char *code, void *context);
int aeon_library_menu(const char *app,const char *games,aeon_play_fn play,aeon_pair_fn pair,void *context);
#endif
