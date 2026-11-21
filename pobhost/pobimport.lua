-- Headless character import: runs Path of Building's OWN import code (ImportTab + PoEAPI) without its window,
-- using the GGG login the author already gave PoB. Only runs when asked (never on a timer).
-- Env: POB_RUNTIME, POB_USERPATH (PoB's Documents folder, ends with /), POB_OUT (json),
--      POB_MODE = "list" | "import", POB_CHAR (character name for import), POB_ALLOW_REFRESH = "1"/"0".
local RUNTIME = os.getenv("POB_RUNTIME")
package.path = RUNTIME .. "/lua/?.lua;" .. RUNTIME .. "/lua/?/init.lua;" .. package.path
package.cpath = (os.getenv("POB_CPATH") or (RUNTIME .. "/?.dll")) .. ";" .. package.cpath  -- Linux: .so add-ons
arg = arg or {}
dofile("HeadlessWrapper.lua")
if not newBuild then error("PoB failed to start") end
local dkjson = require("dkjson")
local out = { ok = false }
local function finish()
	local o = assert(io.open(os.getenv("POB_OUT"), "wb"))
	o:write(dkjson.encode(out))
	o:close()
end

-- PoB's downloads normally run on a background thread of its window; headless has none, so run PoB's own
-- download code inline (same lcurl calls, same "Path of Building/<version>" user agent).
function launch:DownloadPage(url, callback, params)
	params = params or {}
	-- HeadlessWrapper blocks require("lcurl.safe"), so load PoB's own lcurl.dll directly
	CURL = CURL or assert(package.loadlib(os.getenv("POB_LCURL") or (RUNTIME .. "/lcurl.dll"), "luaopen_lcurl_safe"))()
	local curl = CURL
	local easy = curl.easy()
	local responseHeader, responseBody = "", ""
	if params.header then
		local header = {}
		for s in params.header:gmatch("[^\r\n]+") do table.insert(header, s) end
		easy:setopt(curl.OPT_HTTPHEADER, header)
	end
	easy:setopt_url(url)
	easy:setopt(curl.OPT_USERAGENT, "Path of Building/" .. tostring(self.versionNumber))
	easy:setopt(curl.OPT_ACCEPT_ENCODING, "")
	easy:setopt(curl.OPT_FOLLOWLOCATION, 1)
	if params.body then
		easy:setopt(curl.OPT_POST, true)
		easy:setopt(curl.OPT_POSTFIELDS, params.body)
	end
	easy:setopt_headerfunction(function(d) responseHeader = responseHeader .. d return true end)
	easy:setopt_writefunction(function(d) responseBody = responseBody .. d return true end)
	local _, err = easy:perform()
	local code = easy:getinfo(curl.INFO_RESPONSE_CODE)
	easy:close()
	local errMsg
	if err then errMsg = err:msg() elseif code ~= 200 then errMsg = "Response code: " .. code
	elseif #responseBody == 0 then errMsg = "No data returned" end
	callback({ header = responseHeader, body = responseBody }, errMsg)
end

-- Load PoB's real settings (where its GGG login lives) instead of the headless default path.
main.userPath = os.getenv("POB_USERPATH")
main:LoadSettings(true)
if not main.lastToken then
	out.error = "Path of Building is not signed in with GGG. Sign in once in PoB (Import/Export → Authorize)."
	finish() return
end
if os.getenv("POB_ALLOW_REFRESH") ~= "1" and (main.tokenExpiry or 0) < os.time() + 60 then
	out.error = "PoB's GGG login has expired and PoB's window is open. Press Import once in PoB to renew it, or close PoB and ask again."
	finish() return
end
local savedSave = main.SaveSettings
local refreshed = false
main.SaveSettings = function(self) refreshed = true return savedSave(self) end  -- only happens on a token refresh

newBuild()
local tab = build.importTab
main.api = new("PoEAPI"):PoEAPI(main.lastToken, main.lastRefreshToken, main.tokenExpiry)
tab.controls.accountRealm:SelByValue("PoE2", "id")
tab:DownloadCharacterList()
if not tab.lastCharList then
	out.error = "Could not get the character list: " .. tostring(tab.charImportStatus)
	out.refreshed_login = refreshed
	finish() return
end
out.characters = {}
for _, c in ipairs(tab.lastCharList) do
	table.insert(out.characters, { name = c.name, class = c.class, level = c.level, league = c.league })
end

if os.getenv("POB_MODE") == "import" then
	local want = os.getenv("POB_CHAR")
	tab:BuildCharacterList(nil)  -- all leagues
	local idx
	for i, e in ipairs(tab.controls.charSelect.list) do
		if e.char.name == want then idx = i break end
	end
	if not idx then
		out.error = "No character called " .. tostring(want)
		finish() return
	end
	tab.controls.charSelect.selIndex = idx
	local got
	tab:DownloadCharacter(function(charData)
		tab:ImportPassiveTreeAndJewels(charData)
		tab:ImportItemsAndSkills(charData)
		got = charData
	end)
	runCallback("OnFrame")
	if not got then
		out.error = "Import failed: " .. tostring(tab.charImportStatus)
		finish() return
	end
	out.character = { name = got.name, class = got.class, level = got.level, league = got.league }
	out.xml = build:SaveDB("import")
end
out.ok = true
out.refreshed_login = refreshed
finish()
