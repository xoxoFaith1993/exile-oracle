-- Headless Path of Building run: loads a build XML, lets PoB calculate, writes the results as JSON.
-- Run by poblua.exe with the working directory = <pob>\src. Env: POB_RUNTIME, POB_IN (xml), POB_OUT (json).
local RUNTIME = os.getenv("POB_RUNTIME")
package.path = RUNTIME .. "/lua/?.lua;" .. RUNTIME .. "/lua/?/init.lua;" .. package.path
package.cpath = RUNTIME .. "/?.dll;" .. package.cpath

arg = arg or {}  -- PoB's Main.lua reads the command-line table
-- PoB prints a lot while loading; results go to POB_OUT, not stdout.
dofile("HeadlessWrapper.lua")
if not loadBuildFromXML then
	error("PoB failed to start: " .. tostring(__mainObject__ and __mainObject__.promptMsg))
end

local f = assert(io.open(os.getenv("POB_IN"), "rb"))
local xml = f:read("*a")
f:close()
loadBuildFromXML(xml, "toolkit")

-- Rate every skill group: make each one the main skill in turn and record its DPS. Then use the group
-- asked for (POB_MAIN_GROUP), else the build's own choice, else the strongest group if the own choice is 0.
local function groupName(g)
	local sk = g.displaySkillList and g.displaySkillList[g.mainActiveSkill or 1]
	local eff = sk and sk.activeEffect and sk.activeEffect.grantedEffect
	return (g.displayLabel or g.label or ""), eff and eff.name
end
local function recalc()
	build.buildFlag = true
	runCallback("OnFrame")
end
local groups = {}
local own = build.mainSocketGroup
local best, bestDps = nil, -1
for i, g in ipairs(build.skillsTab and build.skillsTab.socketGroupList or {}) do
	if g.enabled ~= false and g.displaySkillList and #g.displaySkillList > 0 then
		build.mainSocketGroup = i
		recalc()
		local o = build.calcsTab.mainOutput or {}
		local label, skill = groupName(g)
		local dps = o.CombinedDPS or o.TotalDPS or 0
		if dps ~= dps or dps == math.huge then dps = -1 end
		table.insert(groups, { index = i, label = label, skill = skill, dps = dps, total_dps = o.TotalDPS,
			full_dps = o.FullDPS, include_in_full = g.includeInFullDPS and true or false })
		if dps > bestDps then best, bestDps = i, dps end
	end
end
local want = tonumber(os.getenv("POB_MAIN_GROUP") or "")
local chosen = want or own
local ownDps = 0
for _, gr in ipairs(groups) do if gr.index == own then ownDps = gr.dps end end
local reason = want and "asked" or "build's own main skill"
if not want and (ownDps or 0) <= 0 and best then chosen, reason = best, "strongest skill (build's own main skill showed 0 DPS)" end
build.mainSocketGroup = chosen or own
recalc()

local out = {}
local main = build.calcsTab and build.calcsTab.mainOutput or {}
for k, v in pairs(main) do
	if type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then
		out[k] = v
	elseif type(v) == "boolean" then
		out[k] = v
	end
end

local skill = nil
local env = build.calcsTab and build.calcsTab.mainEnv
if env and env.player and env.player.mainSkill and env.player.mainSkill.activeEffect then
	local g = env.player.mainSkill.activeEffect.grantedEffect
	skill = g and g.name
end

local result = {
	ok = true,
	main_skill = skill,
	class = build.spec and build.spec.curClassName,
	ascendancy = build.spec and build.spec.curAscendClassName,
	level = build.characterLevel,
	main_group = build.mainSocketGroup,
	main_group_reason = reason,
	skill_groups = groups,
	output = out,
}
local dkjson = require("dkjson")
local o = assert(io.open(os.getenv("POB_OUT"), "wb"))
o:write(dkjson.encode(result))
o:close()
