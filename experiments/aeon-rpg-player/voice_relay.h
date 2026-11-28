#ifndef AEON_VOICE_RELAY_H
#define AEON_VOICE_RELAY_H
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <SDL.h>

extern char **environ;
struct voice_settings {
    char helper[PATH_MAX], ca[PATH_MAX], secret[PATH_MAX], base[512], host[254];
    int configured;
};
struct voice_relay { int fd; pid_t pid; };
static int voice_path(char *out,const char *dir,const char *name) {
    int n=snprintf(out,PATH_MAX,"%s/%s",dir,name);
    return n>0 && n<PATH_MAX;
}
static int voice_line(FILE *f,char *out,size_t len) {
    if(!fgets(out,(int)len,f))return 0;
    size_t n=strlen(out);
    if(n<2 || out[n-1]!='\n')return 0;
    out[n-1]=0;
    for(size_t i=0;i<n-1;i++)if((unsigned char)out[i]<=32 || (unsigned char)out[i]>=127)return 0;
    return 1;
}
static void voice_config(struct voice_settings *s,const char *app,const char *root) {
    char config[PATH_MAX];
    if(!voice_path(config,app,"voice-endpoint.txt") ||
       !voice_path(s->helper,app,"voice_client") || !voice_path(s->ca,app,"voice-ca.pem") ||
       !voice_path(s->secret,root,"aeon-voice.credential"))return;
    FILE *f=fopen(config,"r");
    if(!f)return;
    int ok=voice_line(f,s->base,sizeof s->base) && voice_line(f,s->host,sizeof s->host) && fgetc(f)==EOF;
    fclose(f);
    s->configured=ok && !strncmp(s->base,"wss://",6) && !strchr(s->base+6,'/') &&
        !strchr(s->base,'@') && !strchr(s->base,'?') && !strchr(s->base,'#') &&
        access(s->helper,X_OK)==0 && access(s->ca,R_OK)==0;
}
static int voice_secret(const struct voice_settings *s) {
    int fd=open(s->secret,O_RDONLY|O_NOFOLLOW);
    struct stat st;
    if(fd<0)return -1;
    if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_uid!=getuid() ||
       (st.st_mode&0077) || st.st_size!=43){close(fd);return -1;}
    return fd;
}
static int voice_spawn(struct voice_relay *r,const struct voice_settings *s,const char *content,const char *code) {
    if(!s->configured)return 0;
    int secret=-1, pair=code!=NULL, p[2], fd[2];
    if(pair){
        if(access(s->secret,F_OK)==0 || pipe(p))return 0;
        ssize_t n=write(p[1],code,6);close(p[1]);secret=p[0];
        if(n!=6){close(secret);return 0;}
    }else secret=voice_secret(s);
    if(secret<0)return 0;
    if(socketpair(AF_UNIX,SOCK_STREAM,0,fd)){close(secret);return 0;}
    char url[600],sockstr[24],secstr[24];
    snprintf(url,sizeof url,"%s/aeon/%s",s->base,pair?"pair":"voice");
    snprintf(sockstr,sizeof sockstr,"%d",fd[1]);snprintf(secstr,sizeof secstr,"%d",secret);
    char *args[]={(char*)s->helper,url,(char*)s->host,(char*)s->ca,sockstr,secstr,
        (char*)(pair?"--pair":content),pair?(char*)s->secret:NULL,NULL};
    int ok=fcntl(fd[0],F_SETFD,FD_CLOEXEC)==0 && fcntl(fd[0],F_SETFL,O_NONBLOCK)==0 &&
        posix_spawn(&r->pid,s->helper,NULL,NULL,args,environ)==0;
    close(secret);close(fd[1]);
    if(!ok){close(fd[0]);return 0;}
    r->fd=fd[0];return 1;
}
static void voice_close(struct voice_relay *r) {
    if(r->fd>=0){close(r->fd);r->fd=-1;}
    if(r->pid<=0)return;
    int status;pid_t result;
    for(int i=0;i<20;i++){
        result=waitpid(r->pid,&status,WNOHANG);
        if(result==r->pid || (result<0 && errno!=EINTR)){r->pid=0;return;}
        SDL_Delay(25);
    }
    kill(r->pid,SIGTERM);
    for(int i=0;i<20;i++){
        result=waitpid(r->pid,&status,WNOHANG);
        if(result==r->pid || (result<0 && errno!=EINTR)){r->pid=0;return;}
        SDL_Delay(25);
    }
    kill(r->pid,SIGKILL);
    while(waitpid(r->pid,&status,0)<0 && errno==EINTR){}
    r->pid=0;
}
static int voice_pair(const struct voice_settings *s,const char *code) {
    struct voice_relay r={.fd=-1};char state=0;
    if(!voice_spawn(&r,s,NULL,code))return 0;
    for(int i=0;i<480;i++){
        ssize_t n=recv(r.fd,&state,1,MSG_DONTWAIT);
        if(n==1 || n==0 || (n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR))break;
        SDL_Delay(25);
    }
    voice_close(&r);
    int fd=voice_secret(s);if(fd>=0)close(fd);
    return state=='S' && fd>=0;
}
#endif
