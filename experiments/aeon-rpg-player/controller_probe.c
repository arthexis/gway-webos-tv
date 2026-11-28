#include <SDL.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include "menu_font.h"
#include "probe_events.h"
static void rect(SDL_Renderer*r,int x,int y,int w,int h,int red,int green,int blue) {
    SDL_Rect p={x,y,w,h};SDL_SetRenderDrawColor(r,red,green,blue,255);SDL_RenderFillRect(r,&p);
}
static void label(SDL_Renderer*r,int x,int y,const char*s,int k,int red,int green,int blue){
    for(;*s&&x<940;s++,x+=6*k){
        unsigned char c=(unsigned char)toupper((unsigned char)*s);if(c>127)c=' ';
        for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(font[c][j]&(1<<(4-i)))rect(r,x+i*k,y+j*k,k,k,red,green,blue);
    }
}
static int matches(int i){
    const char*n=SDL_JoystickNameForIndex(i);
    return n && SDL_strcasecmp(n,"8Bitdo SN30 Pro")==0;
}
static void draw(SDL_Renderer*r,probe_history*h,SDL_Joystick*j,int mapped,int focus,Uint32 elapsed){
    char line[128];rect(r,0,0,960,540,16,22,35);
    label(r,32,22,"AEON CONTROLLER PROBE",3,90,230,160);
    snprintf(line,sizeof line,"SN30 PRO: %s",j?"CONNECTED":"NOT FOUND");
    label(r,32,58,line,2,230,240,250);
    if(j){snprintf(line,sizeof line,"RAW BUTTONS: %d   SDL MAPPED: %s",SDL_JoystickNumButtons(j),mapped?"YES":"NO");label(r,32,84,line,2,185,205,220);}
    snprintf(line,sizeof line,"EVENTS: %u   %s",h->total,elapsed>=PROBE_WINDOW_MS?"CAPTURE COMPLETE":focus?"CAPTURE ACTIVE":"NOT FOCUSED");
    label(r,32,112,line,2,90,230,160);
    label(r,32,145,"PRESS STAR THEN HEART SEPARATELY",2,235,230,180);
    for(unsigned i=0;i<h->count;i++){
        probe_edge e=h->rows[i];const char*n=e.mapped?SDL_GameControllerGetStringForButton((SDL_GameControllerButton)e.button):NULL;
        snprintf(line,sizeof line,"%s %d %s %s",e.mapped?"MAP":"RAW",e.button,n?n:"",e.down?"DOWN":"UP");
        label(r,42,180+35*(int)i,line,2,e.down?90:185,e.down?230:205,e.down?160:220);
    }
    label(r,32,495,"180 SECOND SESSION - REOPEN TO RESET",2,175,195,215);
    SDL_RenderPresent(r);
}
int main(int argc,char**argv){
    int smoke=argc>1&&!strcmp(argv[1],"--smoke");
    if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMECONTROLLER|SDL_INIT_JOYSTICK)<0)return 1;
    SDL_Window*w=SDL_CreateWindow("AEon Input Probe",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,960,540,SDL_WINDOW_FULLSCREEN_DESKTOP);
    SDL_Renderer*r=w?SDL_CreateRenderer(w,-1,0):NULL;
    if(!r){if(w)SDL_DestroyWindow(w);SDL_Quit();return 1;}
    SDL_RenderSetLogicalSize(r,960,540);
    SDL_JoystickEventState(SDL_ENABLE);SDL_GameControllerEventState(SDL_ENABLE);
    SDL_GameController*p=NULL;SDL_Joystick*j=NULL;SDL_JoystickID id=-1;
    probe_history h={0};
    int running=1,focus=1,frames=0;Uint32 start=SDL_GetTicks(),scan=0;
    while(running){
        Uint32 elapsed=SDL_GetTicks()-start;
        if(j&&!SDL_JoystickGetAttached(j)){
            if(p)SDL_GameControllerClose(p);else SDL_JoystickClose(j);
            p=NULL;j=NULL;id=-1;
        }
        if(!j&&elapsed<PROBE_WINDOW_MS&&(scan==0||elapsed-scan>=1000)){
            scan=elapsed?elapsed:1;
            for(int i=0;i<SDL_NumJoysticks();i++)if(matches(i)){
                if(SDL_IsGameController(i)){p=SDL_GameControllerOpen(i);if(p)j=SDL_GameControllerGetJoystick(p);}
                if(!j)j=SDL_JoystickOpen(i);
                if(j){id=SDL_JoystickInstanceID(j);break;}
            }
        }
        SDL_Event e;
        while(SDL_PollEvent(&e)){
            if(e.type==SDL_QUIT)running=0;
            if(e.type==SDL_WINDOWEVENT){
                if(e.window.event==SDL_WINDOWEVENT_FOCUS_LOST)focus=0;
                if(e.window.event==SDL_WINDOWEVENT_FOCUS_GAINED)focus=1;
            }
            if(e.type==SDL_JOYBUTTONDOWN||e.type==SDL_JOYBUTTONUP)
                probe_record(&h,id,e.jbutton.which,focus,elapsed,0,e.jbutton.button,e.type==SDL_JOYBUTTONDOWN);
            if(e.type==SDL_CONTROLLERBUTTONDOWN||e.type==SDL_CONTROLLERBUTTONUP)
                probe_record(&h,id,e.cbutton.which,focus,elapsed,1,e.cbutton.button,e.type==SDL_CONTROLLERBUTTONDOWN);
        }
        draw(r,&h,j,p!=NULL,focus,elapsed);
        SDL_Delay(50);
        if(smoke&&++frames==3)running=0;
    }
    if(p)SDL_GameControllerClose(p);else if(j)SDL_JoystickClose(j);
    SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();return 0;
}
