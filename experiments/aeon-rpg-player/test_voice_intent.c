#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include "voice_intent.h"
int main(void) {
    int fd[2]; char buf[32],source=0;
    unsetenv(AEON_VOICE_FD);
    assert(!aeon_voice_send('M'));
    assert(socketpair(AF_UNIX,SOCK_DGRAM,0,fd)==0);
    snprintf(buf,sizeof buf,"%d",fd[1]);assert(!setenv(AEON_VOICE_FD,buf,1));
    assert(!aeon_voice_send('X'));
    assert(aeon_voice_send('M')); assert(aeon_voice_receive(fd[0],&source)==1 && source=='M');
    assert(aeon_voice_send('C')); assert(aeon_voice_receive(fd[0],&source)==1 && source=='C');
    assert(send(fd[1],"MC",2,0)==2); assert(aeon_voice_receive(fd[0],&source)==-1);
    assert(aeon_voice_receive(fd[0],&source)==0);
    close(fd[0]);close(fd[1]);assert(!aeon_voice_send('M'));
    return 0;
}
