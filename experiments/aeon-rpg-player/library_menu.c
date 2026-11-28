#define _POSIX_C_SOURCE 200809L
#include <SDL.h>
#include <ctype.h>
#include <dirent.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "library_menu.h"
#include "menu_font.h"
#define MAX_GAMES 64
typedef struct { char title[96]; char path[PATH_MAX]; } Entry;
static Entry entries[MAX_GAMES];
static int count;
static int regular(const char *p) { struct stat s; return !lstat(p,&s)&&S_ISREG(s.st_mode); }
static int add(const char *base,const char *name,const char *title) {
    if(count==MAX_GAMES)return 0;
    Entry *e=&entries[count];
    int n=snprintf(e->path,sizeof e->path,"%s/%s",base,name);
    if(n<0 || (size_t)n>=sizeof e->path || !regular(e->path))return 0;
    for(int i=0;i<count;i++)if(!strcmp(entries[i].path,e->path))return 0;
    snprintf(e->title,sizeof e->title,"%s",title);
    count++;return 1;
}
static int cmp(const void *a,const void *b) { return strcmp(((const Entry*)a)->title,((const Entry*)b)->title); }
static void scan(const char *base) {
    DIR *d=opendir(base); if(!d)return;
    struct dirent *e;
    while((e=readdir(d)) && count<MAX_GAMES){
        size_t n=strlen(e->d_name);
        if(n<7 || e->d_name[0]=='.' || strcmp(e->d_name+n-6,".mkxpz"))continue;
        char title[96]; size_t len=n-6;if(len>=sizeof title)len=sizeof title-1;
        memcpy(title,e->d_name,len);title[len]=0;
        for(size_t i=0;i<len;i++)if(title[i]=='_'||title[i]=='-')title[i]=' ';
        add(base,e->d_name,title);
    }
    closedir(d);
}
static void rect(SDL_Renderer*r,int x,int y,int w,int h,int red,int green,int blue) {
    SDL_Rect p={x,y,w,h};SDL_SetRenderDrawColor(r,red,green,blue,255);SDL_RenderFillRect(r,&p);
}
static void label(SDL_Renderer*r,int x,int y,const char *s,int k,int red,int green,int blue) {
    for(;*s && x<910; s++,x+=6*k){
        unsigned char c=(unsigned char)toupper((unsigned char)*s);
        if(c>127)c=' ';
        for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(font[c][j]&(1<<(4-i)))rect(r,x+i*k,y+j*k,k,k,red,green,blue);
    }
}
static void draw(SDL_Renderer*r,int selected) {
    rect(r,0,0,960,540,13,22,38);
    label(r,48,35,"AEON RPG PLAYER",4,111,228,187);
    label(r,48,79,"CHOOSE YOUR ADVENTURE",2,196,209,224);
    int start=selected<4?0:selected-3;
    for(int i=start;i<count&&i<start+5;i++){
        int y=125+(i-start)*65;
        rect(r,48,y,864,56,i==selected?47:29,i==selected?105:44,i==selected?108:65);
        if(i==selected)rect(r,48,y,5,56,111,228,187);
        label(r,72,y+17,entries[i].title,3,237,243,248);
    }
    if(!count)label(r,48,160,"NO GAMES AVAILABLE",3,220,220,220);
    label(r,48,488,"D-PAD MOVE   A SELECT   B EXIT",2,181,204,220);
    SDL_RenderPresent(r);
}
static SDL_GameController *open_pad(void) {
    for(int i=0;i<SDL_NumJoysticks();i++)if(SDL_IsGameController(i)){
        SDL_GameController *p=SDL_GameControllerOpen(i);
        if(p)return p;
    }
    return NULL;
}
static int move(int pos,int delta) {
    return count?(pos+delta+count)%count:0;
}
int aeon_library_menu(const char *app,const char *games,aeon_play_fn play,void *context) {
    char built[PATH_MAX];
    count=0;
    add(app,"fixture/Game.ini","VX ACE TEST");
    int n=snprintf(built,sizeof built,"%s/library",app);
    if(n>0&&(size_t)n<sizeof built)scan(built);
    scan(games);
    qsort(entries,count,sizeof entries[0],cmp);
    if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMECONTROLLER)<0)return -1;
    SDL_Window *w=SDL_CreateWindow("AEon RPG Player",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,960,540,SDL_WINDOW_FULLSCREEN_DESKTOP);
    SDL_Renderer *r=w?SDL_CreateRenderer(w,-1,0):NULL;
    if(!r){if(w)SDL_DestroyWindow(w);SDL_Quit();return -1;}
    SDL_RenderSetLogicalSize(r,960,540);
    SDL_GameController *pad=open_pad();
    int selected=0,action=-1,focus=1,axis=0,dirty=1,failed=0;
    Uint32 last_scan=SDL_GetTicks();
#ifdef AEON_MENU_TEST
    SDL_Event test={0};test.type=SDL_KEYDOWN;test.key.keysym.sym=SDLK_DOWN;SDL_PushEvent(&test);
    test.key.keysym.sym=SDLK_RETURN;SDL_PushEvent(&test);
#endif
    while(action<0){
        SDL_Event e;
        if(!pad && SDL_GetTicks()-last_scan>1000){pad=open_pad();last_scan=SDL_GetTicks();}
        if(dirty){
            draw(r,selected);
            if(failed){label(r,48,452,"GAME COULD NOT START - TRY AGAIN",2,244,149,141);SDL_RenderPresent(r);}
            dirty=0;
        }
        if(!SDL_WaitEventTimeout(&e,100))continue;
        if(e.type==SDL_QUIT)action=0;
        if(e.type==SDL_WINDOWEVENT){
            if(e.window.event==SDL_WINDOWEVENT_FOCUS_LOST){focus=0;axis=0;}
            if(e.window.event==SDL_WINDOWEVENT_FOCUS_GAINED){focus=1;dirty=1;}
            if(e.window.event==SDL_WINDOWEVENT_EXPOSED)dirty=1;
        }
        if(e.type==SDL_CONTROLLERDEVICEREMOVED && pad && !SDL_GameControllerGetAttached(pad)){
            SDL_GameControllerClose(pad);pad=NULL;axis=0;
        }
        if(e.type==SDL_CONTROLLERDEVICEADDED && !pad)pad=open_pad();
        if(!focus)continue;
        int delta=0,confirm=0,cancel=0;
        if(e.type==SDL_KEYDOWN){
            switch(e.key.keysym.sym){
            case SDLK_UP:case SDLK_LEFT:delta=-1;break;
            case SDLK_DOWN:case SDLK_RIGHT:delta=1;break;
            case SDLK_RETURN:case SDLK_SPACE:case SDLK_z:confirm=!e.key.repeat;break;
            case SDLK_ESCAPE:case SDLK_BACKSPACE:case SDLK_x:cancel=!e.key.repeat;break;
            default:break;
            }
        }
        if(pad && e.type==SDL_CONTROLLERBUTTONDOWN && e.cbutton.which==SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad))){
            switch(e.cbutton.button){
            case SDL_CONTROLLER_BUTTON_DPAD_UP:case SDL_CONTROLLER_BUTTON_DPAD_LEFT:delta=-1;break;
            case SDL_CONTROLLER_BUTTON_DPAD_DOWN:case SDL_CONTROLLER_BUTTON_DPAD_RIGHT:delta=1;break;
            case SDL_CONTROLLER_BUTTON_A:case SDL_CONTROLLER_BUTTON_B:confirm=e.cbutton.button==SDL_CONTROLLER_BUTTON_B;cancel=!confirm;break;
            default:break;
            }
        }
        if(pad && e.type==SDL_CONTROLLERAXISMOTION && e.caxis.which==SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad)) && e.caxis.axis==SDL_CONTROLLER_AXIS_LEFTY){
            int next=e.caxis.value>16000?1:e.caxis.value< -16000?-1:0;
            if(next && next!=axis)delta=next;
            if(next || abs(e.caxis.value)<8000)axis=next;
        }
        if(delta){selected=move(selected,delta);dirty=1;}
        if(cancel)action=0;
        if(confirm&&count){
            if(pad){SDL_GameControllerClose(pad);pad=NULL;}
            rect(r,0,0,960,540,13,22,38);
            label(r,48,35,"AEON RPG PLAYER",4,111,228,187);
            label(r,48,225,"LOADING GAME...",3,237,243,248);
            label(r,48,270,entries[selected].title,2,196,209,224);
            SDL_RenderPresent(r);
            int result=play(entries[selected].path,context);
#ifdef AEON_MENU_TEST
            action=result<0?-2:0;
            break;
#endif
            if(result==1){action=0;break;}
            failed=result<0;
            SDL_FlushEvents(SDL_KEYDOWN,SDL_KEYUP);
            SDL_FlushEvents(SDL_CONTROLLERAXISMOTION,SDL_CONTROLLERBUTTONUP);
            SDL_RaiseWindow(w);
            pad=open_pad();axis=0;focus=1;dirty=1;
        }
    }
    if(pad)SDL_GameControllerClose(pad);
    SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();
    return action<0?-1:0;
}
