#ifndef AEON_LIBRARY_MENU_H
#define AEON_LIBRARY_MENU_H
#include <stddef.h>
/* Returns 1 with a selected path, 0 on cancel, -1 on error. */
int aeon_library_menu(const char *app,const char *games,char *out,size_t size);
#endif
