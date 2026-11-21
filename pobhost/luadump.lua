-- Dump any PoB data table (a Lua file that returns a table) to JSON. Env: POB_RUNTIME, LUA_FILE, POB_OUT.
local RUNTIME = os.getenv("POB_RUNTIME")
package.path = RUNTIME .. "/lua/?.lua;" .. RUNTIME .. "/lua/?/init.lua;" .. package.path
local dkjson = require("dkjson")
local t = dofile(os.getenv("LUA_FILE"))
local o = assert(io.open(os.getenv("POB_OUT"), "wb"))
o:write(dkjson.encode(t))
o:close()
