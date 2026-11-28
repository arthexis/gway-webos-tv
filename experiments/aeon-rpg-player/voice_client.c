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
#include <sys/stat.h>

#define RELEASE "9e09b80699cd5d293d7d3c37d718fe09f463fa2fdd3e714fab2cad96d056c4cd"
struct client {
    struct mg_connection *conn;
    struct mg_str ca;
    const char *name;
    char auth[44], launch[33], nonce[33];
    unsigned seq;
    int fd, ready, pending, listening, desired, done, pairing;
    const char *credential_path;
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
static int store_credential(const char *path, const char *value) {
    if(!token(value,43,0))return 0;
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if(fd<0)return 0;
    ssize_t n=write(fd,value,43);
    int ok=n==43 && fsync(fd)==0;
    if(close(fd)<0)ok=0;
    if(!ok)unlink(path);
    return ok;
}
static int verify_release(const char *path) {
    int fd=open(path,O_RDONLY|O_NOFOLLOW);
    if(fd<0)return 0;
    struct stat st;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size>64*1024*1024){close(fd);return 0;}
    unsigned char buf[8192],hash[32];char hex[65];
    mg_sha256_ctx ctx;mg_sha256_init(&ctx);
    ssize_t n;
    while((n=read(fd,buf,sizeof buf))>0)mg_sha256_update(&ctx,buf,(size_t)n);
    close(fd);if(n<0)return 0;
    mg_sha256_final(hash,&ctx);
    for(unsigned i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",hash[i]);
    return !strcmp(hex,RELEASE);
}
static void event(struct mg_connection *c,int ev,void *data) {
    struct client *s=c->fn_data;
    if(ev==MG_EV_CONNECT){
        struct mg_tls_opts opts={.ca=s->ca,.name=mg_str(s->name)};
        mg_tls_init(c,&opts);
    }else if(ev==MG_EV_WS_OPEN){
        if(s->pairing)
            mg_ws_printf(c,WEBSOCKET_OP_TEXT,"{\"type\":\"pair\",\"app\":\"aeon-player\",\"secret\":\"%s\"}",s->auth);
        else
            mg_ws_printf(c,WEBSOCKET_OP_TEXT,"{\"type\":\"auth\",\"credential\":\"%s\"}",s->auth);
        memset(s->auth,0,sizeof s->auth);
    }else if(ev==MG_EV_WS_MSG){
        struct mg_ws_message *m=data;
        if(m->data.len>2048 || (m->flags&15)!=WEBSOCKET_OP_TEXT){fail(s);return;}
        char *type=mg_json_get_str(m->data,"$.type");
        if(!type){fail(s);return;}
        if(s->pairing){
            char *credential=mg_json_get_str(m->data,"$.credential");
            if(!strcmp(type,"paired") && store_credential(s->credential_path,credential)){
                status(s,'S');s->done=1;
            }else fail(s);
            if(credential){memset(credential,0,strlen(credential));free(credential);}
        }else if(!s->ready && !strcmp(type,"aeon.voice.ready")){
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
    if((argc!=6 && argc!=7 && argc!=8) || strncmp(argv[1],"wss://",6) || !argv[2][0] ||
       strlen(argv[2])>253 || strchr(argv[2],'\n') ||
       (strcmp(mg_url_uri(argv[1]),"/aeon/voice") && strcmp(mg_url_uri(argv[1]),"/aeon/pair")))return 2;
    struct client s={0};
    s.pairing=argc==8 && !strcmp(argv[6],"--pair") && !strcmp(mg_url_uri(argv[1]),"/aeon/pair");
    if(s.pairing)s.credential_path=argv[7];
    else if(argc==8 || strcmp(mg_url_uri(argv[1]),"/aeon/voice") || (argc==7 && !verify_release(argv[6])))return 2;
    char *end=NULL;
    long fd=strtol(argv[4],&end,10);
    if(*end || fd<3 || fd>65535)return 2;
    s.fd=(int)fd;
    long secret=strtol(argv[5],&end,10);
    if(*end || secret<3 || secret>65535 || secret==fd)return 2;
    if(s.pairing){
        if(!read_secret((int)secret,s.auth,6))return 2;
        for(int i=0;i<6;i++)if(s.auth[i]<'0'||s.auth[i]>'9')return 2;
    }else if(!read_secret((int)secret,s.auth,43) || !token(s.auth,43,0))return 2;
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
            if(!s.pairing && (b=='M'||b=='C'))s.desired=!s.desired;
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
