#ifndef AEON_VOICE_INTENT_H
#define AEON_VOICE_INTENT_H
#include <errno.h>
#include <stdlib.h>
#include <limits.h>
#include <sys/socket.h>
#include <unistd.h>
#define AEON_VOICE_FD "AEON_VOICE_EDIT_FD"
static inline int aeon_voice_send(char source) {
    const char *s=getenv(AEON_VOICE_FD);
    char *end; long fd;
    if ((source!='M' && source!='C') || !s || !*s) return 0;
    errno=0;fd=strtol(s,&end,10);
    if(errno || *end || fd<3 || fd>INT_MAX) return 0;
    return send((int)fd,&source,1,MSG_DONTWAIT|MSG_NOSIGNAL)==1;
}
static inline int aeon_voice_receive(int fd,char *source) {
    char b[2]; ssize_t n=recv(fd,b,sizeof b,MSG_DONTWAIT);
    if(n<0)return 0;
    if(n!=1 || (b[0]!='M' && b[0]!='C'))return -1;
    *source=b[0];return 1;
}
#endif
