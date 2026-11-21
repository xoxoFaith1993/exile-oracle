-- Batch "try this unique in that slot" runner: loads one build, then uses PoB's own compare calculator
-- (the one behind its item tooltips) to test many items without rebuilding the build each time.
-- Env: POB_RUNTIME, POB_IN (build xml), POB_JOBS (json: {main_group=?, slots={...}, names={...}}), POB_OUT.
local RUNTIME = os.getenv("POB_RUNTIME")
package.path = RUNTIME .. "/lua/?.lua;" .. RUNTIME .. "/lua/?/init.lua;" .. package.path
package.cpath = (os.getenv("POB_CPATH") or (RUNTIME .. "/?.dll")) .. ";" .. package.cpath  -- Linux: .so add-ons
arg = arg or {}
dofile("HeadlessWrapper.lua")
if not loadBuildFromXML then
	error("PoB failed to start: " .. tostring(__mainObject__ and __mainObject__.promptMsg))
end
local dkjson = require("dkjson")

local function readAll(p)
	local f = assert(io.open(p, "rb")); local s = f:read("*a"); f:close(); return s
end
loadBuildFromXML(readAll(os.getenv("POB_IN")), "toolkit")
local jobs = dkjson.decode(readAll(os.getenv("POB_JOBS")))

local function recalc() build.buildFlag = true; runCallback("OnFrame") end
if jobs.main_group then
	build.mainSocketGroup = jobs.main_group
	recalc()
end

local KEYS = { "CombinedDPS", "TotalDPS", "FullDPS", "Speed", "Life", "EnergyShield", "Mana", "Spirit", "TotalEHP",
	"PhysicalMaximumHitTaken", "FireMaximumHitTaken", "ColdMaximumHitTaken", "LightningMaximumHitTaken",
	"ChaosMaximumHitTaken", "FireResist", "ColdResist", "LightningResist", "ChaosResist", "Armour", "Evasion",
	"EffectiveMovementSpeedMod", "Str", "Dex", "Int", "ReqStr", "ReqDex", "ReqInt", "SpiritUnreserved", "SpiritReserved" }
local function pick(o)
	local r = {}
	for _, k in ipairs(KEYS) do
		local v = o[k]
		if type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then r[k] = v end
	end
	return r
end

local calcFunc, baseOut = build.calcsTab:GetMiscCalculator()
-- PoB keys uniques as "Name, Base"; index by title so "Alpha's Howl" finds every base version.
local byTitle = {}
for _, u in pairs(main.uniqueDB.list) do
	local t = (u.title or u.name or ""):lower()
	byTitle[t] = byTitle[t] or {}
	table.insert(byTitle[t], u)
end
local result = { base = pick(baseOut), main_group = build.mainSocketGroup, slots = {}, unique_db_size = 0 }
for _ in pairs(main.uniqueDB.list) do result.unique_db_size = result.unique_db_size + 1 end

for _, slotName in ipairs(jobs.slots) do
	local slot = build.itemsTab.slots[slotName]
	local cur = slot and build.itemsTab.items[slot.selItemId]
	local entry = { slot = slotName, current = cur and cur.name or nil, current_type = cur and cur.type or nil, tried = {} }
	if cur then
		for _, name in ipairs(jobs.names) do
		  for _, u in ipairs(byTitle[name:lower()] or {}) do
			if u.type == cur.type then
				-- Weapons: keep the same handedness / weapon class as what's equipped now.
				local ok = true
				if cur.base and u.base and cur.base.weapon then
					ok = (u.base.type == cur.base.type) and (u.base.subType == cur.base.subType)
				end
				if ok then
					local testItem = new("Item"):Item(u:BuildRaw())
					local ok2, out = pcall(calcFunc, { repSlotName = slotName, repItem = testItem })
					if ok2 and out then
						table.insert(entry.tried, { name = u.name, base = u.baseName, req_level = testItem.requirements and testItem.requirements.level or nil, out = pick(out) })
					else
						table.insert(entry.tried, { name = u.name, base = u.baseName, error = tostring(out) })
					end
				end
			end
		  end
		end
	end
	table.insert(result.slots, entry)
end

local o = assert(io.open(os.getenv("POB_OUT"), "wb"))
o:write(dkjson.encode(result))
o:close()
