#ifndef AEON_VOICE_PAIR_UI_H
#define AEON_VOICE_PAIR_UI_H
static void pairing_screen(SDL_Renderer *r,SDL_GameController *pad,aeon_pair_fn pair,void *context) {
    char code[7]="000000";int digit=0,done=0,result=-1;
    Uint32 until=SDL_GetTicks()+120000;
    while(!done && (Sint32)(until-SDL_GetTicks())>0){
        rect(r,0,0,960,540,13,22,38);
        label(r,48,35,"AEON VOICE PAIRING",3,111,228,187);
        label(r,48,110,"ON GWAY-001 RUN:",2,196,209,224);
        label(r,48,140,"GWAY-TV PAIR --CODE --APP AEON-PLAYER",2,196,209,224);
        label(r,48,175,"ENTER CODE FROM PRIVATE TERMINAL",2,196,209,224);
        for(int i=0;i<6;i++){
            char value[2]={code[i],0};
            rect(r,48+i*95,220,82,90,i==digit?47:29,i==digit?105:44,i==digit?108:65);
            label(r,72+i*95,245,value,5,237,243,248);
        }
        label(r,48,390,"LEFT RIGHT: DIGIT   UP DOWN: CHANGE",2,196,209,224);
        label(r,48,430,"A PAIR   B CANCEL",2,196,209,224);
        SDL_RenderPresent(r);
        SDL_Event e;
        if(!SDL_WaitEventTimeout(&e,100))continue;
        int move=0,change=0,confirm=0;
        if(e.type==SDL_QUIT){SDL_PushEvent(&e);break;}
        if(e.type==SDL_WINDOWEVENT && e.window.event==SDL_WINDOWEVENT_FOCUS_LOST)break;
        if(e.type==SDL_CONTROLLERDEVICEREMOVED)break;
        if(e.type==SDL_KEYDOWN){
            switch(e.key.keysym.sym){
            case SDLK_LEFT:move=-1;break;case SDLK_RIGHT:move=1;break;
            case SDLK_UP:change=1;break;case SDLK_DOWN:change=-1;break;
            case SDLK_RETURN:confirm=!e.key.repeat;break;
            case SDLK_ESCAPE:done=1;break;default:break;
            }
        }
        if(pad && e.type==SDL_CONTROLLERBUTTONDOWN && e.cbutton.which==SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pad))){
            switch(e.cbutton.button){
            case SDL_CONTROLLER_BUTTON_DPAD_LEFT:move=-1;break;
            case SDL_CONTROLLER_BUTTON_DPAD_RIGHT:move=1;break;
            case SDL_CONTROLLER_BUTTON_DPAD_UP:change=1;break;
            case SDL_CONTROLLER_BUTTON_DPAD_DOWN:change=-1;break;
            case SDL_CONTROLLER_BUTTON_B:confirm=1;break;
            case SDL_CONTROLLER_BUTTON_A:done=1;break;default:break;
            }
        }
        digit=(digit+move+6)%6;code[digit]=(char)('0'+(code[digit]-'0'+change+10)%10);
        if(confirm&&!done){
            rect(r,0,0,960,540,13,22,38);label(r,48,225,"PAIRING...",3,237,243,248);SDL_RenderPresent(r);
            result=pair(code,context);done=1;
        }
    }
    memset(code,0,sizeof code);
    if(result>=0){
        rect(r,0,0,960,540,13,22,38);label(r,48,225,result?"VOICE PAIRED":"PAIRING FAILED OR ALREADY PAIRED",3,237,243,248);
        SDL_RenderPresent(r);SDL_Delay(1800);
    }
}
#endif
