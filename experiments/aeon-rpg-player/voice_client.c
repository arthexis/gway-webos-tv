/* SPDX-License-Identifier: GPL-2.0-only
 * Private standalone transport helper; uses Mongoose, not linked into core.
 */
#define _POSIX_C_SOURCE 200809L
#include "mongoose.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>

#define RELEASE "9e09b80699cd5d293d7d3c37d718fe09f463fa2fdd3e714fab2cad96d056c4cd"
struct client {
    struct mg_connection *conn;
    struct mg_str ca;
    const char *name;
    char auth[44], launch[33], nonce[33];
    unsigned seq;
    int fd, ready, pending, listening, desired, done;
    uint64_t deadline, heartbeat;
};

static int token(const char *s, size_t length, int hex) {
    if(!s || strlen(s)!=length)return 0;
    for(size_t i=0;i<length;i++){
        char c=s[i];
        if(hex ? !((c>='0'&&c<='9')||(c>='a'&&c<='f')) :
           !((c>='0'&&c<='9')||(c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='-'||c=='_'))return 0;
    }
    return 1;
}
static void status(struct client *s,char value) {
    if(send(s->fd,&value,1,MSG_DONTWAIT|MSG_NOSIGNAL)!=1)s->done=1;
}
static void fail(struct client *s) {
    status(s,'U');s->done=1;
}
static void send_set(struct client *s) {
    if(s->seq>=2147483647u){fail(s);return;}
    mg_ws_printf(s->conn,WEBSOCKET_OP_TEXT,
        "{\"type\":\"aeon.voice.set\",\"game\":\"lantern-gate\","
        "\"release\":\"%s\",\"launch\":\"%s\",\"connection\":\"%s\","
        "\"sequence\":%u,\"enabled\":%s}",RELEASE,s->launch,s->nonce,
        ++s->seq,s->desired?"true":"false");
    s->pending=1;s->deadline=mg_millis()+55000;
    status(s,'P');
}
static void event(struct mg_connection *c,int ev,void *data) {
    struct client *s=c->fn_data;
    if(ev==MG_EV_CONNECT){
        struct mg_tls_opts opts={.ca=s->ca,.name=mg_str(s->name)};
        mg_tls_init(c,&opts);
    }else if(ev==MG_EV_WS_OPEN){
        mg_ws_printf(c,WEBSOCKET_OP_TEXT,"{\"type\":\"auth\",\"credential\":\"%s\"}",s->auth);
        memset(s->auth,0,sizeof s->auth);
    }else if(ev==MG_EV_WS_MSG){
        struct mg_ws_message *m=data;
        if(m->data.len>2048 || (m->flags&15)!=WEBSOCKET_OP_TEXT){fail(s);return;}
        char *type=mg_json_get_str(m->data,"$.type");
        if(!type){fail(s);return;}
        if(!s->ready && !strcmp(type,"aeon.voice.ready")){
            char *n=mg_json_get_str(m->data,"$.connection");
            if(!token(n,32,1))fail(s);
            else {memcpy(s->nonce,n,33);s->ready=1;s->pending=0;status(s,'S');}
            free(n);
        }else if(s->ready && s->pending && !strcmp(type,"aeon.voice.status")){
            char *state=mg_json_get_str(m->data,"$.state");
            if(!state || (strcmp(state,"listening") && strcmp(state,"stopped")))fail(s);
            else{
                s->listening=!strcmp(state,"listening");
                s->pending=0;s->heartbeat=mg_millis()+5000;
                status(s,s->listening?'L':'S');
            }
            free(state);
        }else fail(s);
        free(type);
    }else if(ev==MG_EV_ERROR || ev==MG_EV_CLOSE){
        if(!s->done)fail(s);
    }
}

static int read_secret(int fd,char *out,size_t len) {
    size_t n=0;
    while(n<len){
        ssize_t r=read(fd,out+n,len-n);
        if(r<0 && errno==EINTR)continue;
        if(r<=0)return 0;
        n+=(size_t)r;
    }
    out[n]=0;
    char extra;
    return read(fd,&extra,1)==0;
}
int main(int argc,char **argv) {
    if(argc!=6 || strncmp(argv[1],"wss://",6) || !argv[2][0] ||
       strlen(argv[2])>253 || strchr(argv[2],'\n') ||
       strcmp(mg_url_uri(argv[1]),"/aeon/voice"))return 2;
    struct client s={0};
    char *end=NULL;
    long fd=strtol(argv[4],&end,10);
    if(*end || fd<3 || fd>65535)return 2;
    s.fd=(int)fd;
    long secret=strtol(argv[5],&end,10);
    if(*end || secret<3 || secret>65535 || secret==fd)return 2;
    if(!read_secret((int)secret,s.auth,43) || !token(s.auth,43,0))return 2;
    close((int)secret);
    if(fcntl(s.fd,F_SETFL,O_NONBLOCK)<0)return 2;
    s.name=argv[2];
    s.ca=mg_file_read(&mg_fs_posix,argv[3]);
    if(!s.ca.buf || !s.ca.len || s.ca.len>65536)return 2;
    unsigned char random[16];
    if(!mg_random(random,sizeof random))return 2;
    for(unsigned i=0;i<sizeof random;i++)snprintf(s.launch+2*i,3,"%02x",random[i]);
    struct mg_mgr mgr;
    mg_log_set(MG_LL_NONE);
    mg_mgr_init(&mgr);
    s.deadline=mg_millis()+10000;
    s.conn=mg_ws_connect(&mgr,argv[1],event,&s,NULL);
    if(!s.conn)fail(&s);
    while(!s.done){
        char b;
        ssize_t n=recv(s.fd,&b,1,MSG_DONTWAIT);
        if(n==0 || (n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR)){
            s.done=1;break;
        }
        if(n==1){
            if(b=='Q'){s.done=1;break;}
            if((b=='M'||b=='C') && s.ready)s.desired=!s.desired;
            else if(b!='M' && b!='C'){fail(&s);break;}
        }
        uint64_t now=mg_millis();
        if((!s.ready || s.pending) && now>=s.deadline){fail(&s);break;}
        if(s.ready && !s.pending){
            if(s.desired!=s.listening)send_set(&s);
            else if(s.listening && now>=s.heartbeat){
                mg_ws_printf(s.conn,WEBSOCKET_OP_TEXT,"{\"type\":\"aeon.voice.heartbeat\"}");
                s.pending=1;s.deadline=now+10000;
            }
        }
        mg_mgr_poll(&mgr,25);
    }
    mg_mgr_free(&mgr);
    memset(s.auth,0,sizeof s.auth);
    free((void *)s.ca.buf);
    close(s.fd);
    return 0;
}
