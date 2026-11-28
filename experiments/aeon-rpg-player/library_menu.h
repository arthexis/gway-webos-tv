#ifndef AEON_LIBRARY_MENU_H
#define AEON_LIBRARY_MENU_H
/* Runs a game while keeping the launcher surface alive. */
typedef int (*aeon_play_fn)(const char *content, void *context);
int aeon_library_menu(const char *app,const char *games,aeon_play_fn play,void *context);
#endif
