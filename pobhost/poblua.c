/* poblua: run a Lua script with Path of Building's OWN LuaJIT (runtime\lua51.dll), so PoB's native
   modules (lua-utf8.dll, lzip.dll, ...) match exactly. Usage: poblua.exe <pob runtime dir> <script.lua>
   Functions are looked up at run time, so no LuaJIT headers or import libs are needed. */
#include <windows.h>
#include <stdio.h>

typedef void *(*newstate_t)(void);
typedef void (*openlibs_t)(void *);
typedef int (*loadfile_t)(void *, const char *);
typedef int (*pcall_t)(void *, int, int, int);
typedef const char *(*tolstring_t)(void *, int, size_t *);

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: poblua <pob runtime dir> <script.lua>\n");
        return 2;
    }
    char dll[MAX_PATH];
    SetDllDirectoryA(argv[1]);
    snprintf(dll, sizeof dll, "%s\\lua51.dll", argv[1]);
    HMODULE h = LoadLibraryA(dll);
    if (!h) {
        fprintf(stderr, "poblua: cannot load %s (error %lu)\n", dll, GetLastError());
        return 3;
    }
    newstate_t newstate = (newstate_t)GetProcAddress(h, "luaL_newstate");
    openlibs_t openlibs = (openlibs_t)GetProcAddress(h, "luaL_openlibs");
    loadfile_t loadfile = (loadfile_t)GetProcAddress(h, "luaL_loadfile");
    pcall_t pcall = (pcall_t)GetProcAddress(h, "lua_pcall");
    tolstring_t tolstring = (tolstring_t)GetProcAddress(h, "lua_tolstring");
    if (!newstate || !openlibs || !loadfile || !pcall || !tolstring) {
        fprintf(stderr, "poblua: lua51.dll is missing expected functions\n");
        return 4;
    }
    void *L = newstate();
    openlibs(L);
    if (loadfile(L, argv[2]) != 0 || pcall(L, 0, 0, 0) != 0) {
        const char *msg = tolstring(L, -1, NULL);
        fprintf(stderr, "poblua: %s\n", msg ? msg : "(unknown error)");
        return 1;
    }
    return 0;
}
