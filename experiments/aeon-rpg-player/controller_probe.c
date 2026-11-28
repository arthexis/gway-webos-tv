#include <SDL.h>
#include <stdio.h>
#include <string.h>
#include "input.h"
static const SDL_GameControllerButton pad[BUTTON_COUNT] = {
 SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_BUTTON_DPAD_DOWN,
 SDL_CONTROLLER_BUTTON_DPAD_LEFT, SDL_CONTROLLER_BUTTON_DPAD_RIGHT,
 SDL_CONTROLLER_BUTTON_B, SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_BUTTON_Y,
 SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_BUTTON_LEFTSHOULDER,
 SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, SDL_CONTROLLER_BUTTON_START, SDL_CONTROLLER_BUTTON_BACK
};
static const char *names[BUTTON_COUNT]={"UP","DOWN","LEFT","RIGHT","A","B","X","Y","L","R","START","SELECT"};
static const SDL_Scancode keys[BUTTON_COUNT]={SDL_SCANCODE_UP,SDL_SCANCODE_DOWN,SDL_SCANCODE_LEFT,SDL_SCANCODE_RIGHT,SDL_SCANCODE_RETURN,SDL_SCANCODE_BACKSPACE,SDL_SCANCODE_X,SDL_SCANCODE_Y,SDL_SCANCODE_L,SDL_SCANCODE_R,SDL_SCANCODE_S,SDL_SCANCODE_TAB};
static const SDL_Rect positions[BUTTON_COUNT]={{100,100,60,60},{100,220,60,60},{40,160,60,60},{160,160,60,60},{520,160,60,60},{460,220,60,60},{460,100,60,60},{400,160,60,60},{40,30,120,40},{460,30,120,40},{330,290,70,35},{230,290,70,35}};
int main(int argc, char **argv) {
 int smoke=argc>1 && !strcmp(argv[1],"--smoke");
 if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMECONTROLLER)<0){fprintf(stderr,"SDL: %s\n",SDL_GetError());return 1;}
 SDL_Window *w=SDL_CreateWindow("AEon input probe",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,640,360,0);
 SDL_Renderer *r=w?SDL_CreateRenderer(w,-1,0):NULL;
 if(!r){fprintf(stderr,"Renderer: %s\n",SDL_GetError());SDL_DestroyWindow(w);SDL_Quit();return 1;}
 SDL_RenderSetLogicalSize(r,640,360);
 SDL_GameController *p=NULL; uint16_t last=0; int running=1,focused=1,frames=0;
 while(running){
  SDL_Event e; while(SDL_PollEvent(&e)){
   if(e.type==SDL_QUIT)running=0;
   if(e.type==SDL_WINDOWEVENT){if(e.window.event==SDL_WINDOWEVENT_FOCUS_LOST)focused=0;if(e.window.event==SDL_WINDOWEVENT_FOCUS_GAINED)focused=1;}
   if(e.type==SDL_JOYDEVICEADDED)printf("Device added index=%d mapped=%d\n",e.jdevice.which,SDL_IsGameController(e.jdevice.which));
   if(e.type==SDL_JOYDEVICEREMOVED)printf("Device removed instance=%d\n",e.jdevice.which);
  }
  if(p&&!SDL_GameControllerGetAttached(p)){SDL_GameControllerClose(p);p=NULL;puts("Player 1 disconnected");}
  if(!p)for(int i=0;i<SDL_NumJoysticks();i++)if(SDL_IsGameController(i)&&(p=SDL_GameControllerOpen(i))){printf("Player 1: %s\n",SDL_GameControllerName(p));break;}
  uint16_t buttons=0;const Uint8 *k=SDL_GetKeyboardState(NULL);
  for(unsigned i=0;i<BUTTON_COUNT;i++)if(k[keys[i]]||(p&&SDL_GameControllerGetButton(p,pad[i])))buttons|=aeon_bit(i);
  uint16_t now=aeon_sample(buttons,p?SDL_GameControllerGetAxis(p,SDL_CONTROLLER_AXIS_LEFTX):0,p?SDL_GameControllerGetAxis(p,SDL_CONTROLLER_AXIS_LEFTY):0,12000,focused,1);
  for(unsigned i=0;i<BUTTON_COUNT;i++)if((now^last)&aeon_bit(i))printf("%s %s\n",names[i],now&aeon_bit(i)?"down":"up");
  last=now;SDL_SetRenderDrawColor(r,16,22,35,255);SDL_RenderClear(r);
  for(unsigned i=0;i<BUTTON_COUNT;i++){SDL_SetRenderDrawColor(r,now&aeon_bit(i)?90:48,now&aeon_bit(i)?230:65,now&aeon_bit(i)?130:88,255);SDL_RenderFillRect(r,&positions[i]);}
  SDL_RenderPresent(r);fflush(stdout);SDL_Delay(16);if(smoke&&++frames==3)running=0;
 }
 if(p) SDL_GameControllerClose(p);
 SDL_DestroyRenderer(r);SDL_DestroyWindow(w);SDL_Quit();return 0;
}
