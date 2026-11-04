#include <dlfcn.h>
#include <stdio.h>
#include "../include/tailscale_ohos.h"

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: smoke /absolute/path/libtailscale_go.so\n"); return 2; }
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "library load failed\n"); return 3; }
    char *(*hello)(void) = (char *(*)(void))dlsym(library, "TSHello");
    char *(*version)(void) = (char *(*)(void))dlsym(library, "TSTailscaleVersion");
    void (*release)(char *) = (void (*)(char *))dlsym(library, "TSFreeString");
    if (!hello || !version || !release) return 4;
    char *a = hello(), *b = version();
    int ok = a != NULL && b != NULL;
    if (a) { puts(a); release(a); }
    if (b) { puts(b); release(b); }
    /* No login, account-state access or dlclose of a live Go runtime. */
    return ok ? 0 : 5;
}
