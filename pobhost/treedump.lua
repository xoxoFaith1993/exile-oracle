-- Dump PoB's passive tree data (TreeData/<version>/tree.lua) to JSON for the dashboard's tree view.
-- Run by poblua.exe with the working directory = <pob>\src. Env: POB_RUNTIME, TREE_VERSION, POB_OUT.
local RUNTIME = os.getenv("POB_RUNTIME")
package.path = RUNTIME .. "/lua/?.lua;" .. RUNTIME .. "/lua/?/init.lua;" .. package.path
local dkjson = require("dkjson")
local ver = os.getenv("TREE_VERSION")
local tree = dofile("TreeData/" .. ver .. "/tree.lua")

local out = { version = ver, constants = { orbitRadii = tree.constants.orbitRadii,
	orbitAnglesByOrbit = tree.constants.orbitAnglesByOrbit }, groups = {}, nodes = {}, classes = {} }
for id, g in pairs(tree.groups) do
	out.groups[tostring(id)] = { x = g.x, y = g.y }
end
for id, n in pairs(tree.nodes) do
	local conns = {}
	for _, c in ipairs(n.connections or {}) do table.insert(conns, { c.id, c.orbit or 0 }) end
	out.nodes[tostring(id)] = {
		g = n.group, o = n.orbit, oi = n.orbitIndex, name = n.name, icon = n.icon, stats = n.stats,
		ks = n.isKeystone or nil, nt = n.isNotable or nil, js = n.isJewelSocket or nil, ms = n.isMastery or nil,
		asc = n.ascendancyName, ascStart = n.isAscendancyStart or nil, cls = n.classStartIndex,
		attr = n.isAttribute or nil, c = conns,
	}
end
for i, c in ipairs(tree.classes or {}) do
	local ascs = {}
	for _, a in ipairs(c.ascendancies or {}) do table.insert(ascs, { id = a.id, name = a.name }) end
	out.classes[i] = { name = c.name, ascendancies = ascs }
end
local o = assert(io.open(os.getenv("POB_OUT"), "wb"))
o:write(dkjson.encode(out))
o:close()
