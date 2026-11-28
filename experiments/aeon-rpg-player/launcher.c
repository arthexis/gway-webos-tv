/* Launch the bundled frontend in the normal webOS native app jail. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <spawn.h>
#include <sys/wait.h>
#include <signal.h>
#include <SDL.h>
#include <fcntl.h>
#include "voice_intent.h"
#include "library_menu.h"

static void die(const char *what) { perror(what); exit(1); }
static void path(char *out, const char *a, const char *b) {
    int n=snprintf(out,PATH_MAX,"%s/%s",a,b);
    if(n<0 || n>=PATH_MAX || strchr(out,'"') || strchr(out,'\n')) { errno=EINVAL; die("path"); }
}
static void directory(const char *p) {
    if(mkdir(p,0700)<0 && errno!=EEXIST) die(p);
    struct stat st;
    if(lstat(p,&st)<0 || !S_ISDIR(st.st_mode) || st.st_uid!=getuid() || (st.st_mode & 0077)) { errno=EACCES; die(p); }
}
extern char **environ;
struct playback { const char *frontend,*cfg,*core,*menu_cfg,*editable; };
static int play_game(const char *content,void *context) {
    struct playback *p=context;
    char *const args[]={(char *)p->frontend,"--config",(char *)p->cfg,"--appendconfig",(char *)p->menu_cfg,"-L",(char *)p->core,(char *)content,NULL};
    int channel[2]={-1,-1}, received=0;
    unsetenv(AEON_VOICE_FD);
    if (!strcmp(content,p->editable) && socketpair(AF_UNIX,SOCK_DGRAM,0,channel)==0) {
        char fdstr[32];
        snprintf(fdstr,sizeof fdstr,"%d",channel[1]);
        if (fcntl(channel[0],F_SETFD,FD_CLOEXEC)<0 || setenv(AEON_VOICE_FD,fdstr,1)<0) {
            close(channel[0]);close(channel[1]);channel[0]=channel[1]=-1;
        }
    }
    pid_t pid;
    int error=posix_spawn(&pid,p->frontend,NULL,NULL,args,environ);
    unsetenv(AEON_VOICE_FD);
    if(channel[1]>=0)close(channel[1]);
    if(error){if(channel[0]>=0)close(channel[0]);errno=error;perror("retroarch");return -1;}
    int status=0,closing=0;
    Uint32 started=0;
    for(;;){
        if(channel[0]>=0)for(int i=0;i<8;i++){
            char source;int event=aeon_voice_receive(channel[0],&source);
            if(!event)break;
            if(event==1 && received<16){
                received++;
                fprintf(stderr,"AEON VOICE DRY RUN game=lantern-gate source=%s sequence=%d\n",source=='M'?"menu":"chord",received);
            }
        }
        pid_t result=waitpid(pid,&status,WNOHANG);
        if(result==pid)break;
        if(result<0 && errno!=EINTR){if(channel[0]>=0)close(channel[0]);perror("waitpid");return -1;}
        SDL_Event e;
        while(SDL_PollEvent(&e)){
            if(e.type==SDL_QUIT && !closing){
                closing=1;started=SDL_GetTicks();kill(pid,SIGTERM);
            }
        }
        if(closing && SDL_GetTicks()-started>3000)kill(pid,SIGKILL);
        SDL_Delay(25);
    }
    if(channel[0]>=0)close(channel[0]);
    if(closing)return 1;
    if(!WIFEXITED(status)||WEXITSTATUS(status)!=0)return -1;
    return 0;
}
int main(void) {
    char app[PATH_MAX],root[PATH_MAX],cfg[PATH_MAX],system[PATH_MAX],saves[PATH_MAX],states[PATH_MAX],games[PATH_MAX],cores[PATH_MAX],core[PATH_MAX],frontend[PATH_MAX],lib[PATH_MAX],menu_cfg[PATH_MAX];
    ssize_t n=readlink("/proc/self/exe",app,sizeof app-1);
    if(n<1 || n>=PATH_MAX-1) die("app location");
    app[n]=0; char *slash=strrchr(app,'/'); if(!slash) die("app directory"); *slash=0;
    const char *home=access("/media/internal",W_OK)==0 ? "/media/internal" : getenv("HOME");
    if(!home || home[0]!='/') { errno=EINVAL; die("HOME"); }
    path(root,home,".aeon-rpg-player"); directory(root);
    path(system,root,"system"); directory(system);
    path(saves,root,"saves"); directory(saves);
    path(states,root,"states"); directory(states);
    path(games,root,"games"); directory(games);
    path(cfg,root,"retroarch.cfg"); path(cores,app,"cores");
    path(core,cores,"mkxp-z_libretro.so"); path(frontend,app,"retroarch");
    path(lib,app,"lib");
    FILE *f=fopen(cfg,"wx");
    if(f) {
        if(fprintf(f,"system_directory = \"%s\"\nsavefile_directory = \"%s\"\nsavestate_directory = \"%s\"\nrgui_browser_directory = \"%s\"\nlibretro_directory = \"%s\"\nvideo_driver = \"gl\"\nvideo_smooth = \"false\"\nvideo_fullscreen = \"true\"\nmenu_driver = \"rgui\"\nconfig_save_on_exit = \"true\"\n",system,saves,states,games,cores)<0 || fclose(f)!=0) die("config");
    } else if(errno!=EEXIST) die("config");
    if(setenv("LD_LIBRARY_PATH",lib,1)<0 || chdir(app)<0) die("frontend environment");
    path(menu_cfg,app,"aeon-menu.cfg");
    char editable[PATH_MAX]; path(editable,app,"library/AEon-Lantern-Gate.mkxpz");
    struct playback p={frontend,cfg,core,menu_cfg,editable};
    return aeon_library_menu(app,games,play_game,&p)<0?1:0;
}
