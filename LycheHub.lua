-- LycheHub | AirDrop Arena S5 | Radial Mobile GUI
-- Drawing only. Delta-compatible.

local Players    = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace  = game:GetService("Workspace")
local UIS        = game:GetService("UserInputService")
local Camera     = Workspace.CurrentCamera
local LP         = Players.LocalPlayer

assert(Drawing, "executor tanpa Drawing API")

-- ═══════════════════════════════════════════════════════════
-- CONFIG
-- ═══════════════════════════════════════════════════════════
local CONFIG = {
    Enabled      = true,
    Box          = true,
    Skeleton     = false,
    Snapline     = true,
    HeadDot      = true,
    Name         = true,
    Distance     = true,
    Health       = true,
    WallCheck    = true,
    TeamCheck    = false,
    MaxDistance  = 400,
    UpdateInterval = 0.08,
    JitterMax    = 0.03,
    BoxColor     = Color3.fromRGB(0, 255, 140),
    SkeletonColor= Color3.fromRGB(255, 255, 255),
    SnaplineColor= Color3.fromRGB(0, 255, 140),
    HeadDotColor = Color3.fromRGB(255, 60, 60),
    NameColor    = Color3.fromRGB(255, 255, 255),
    DistColor    = Color3.fromRGB(200, 200, 200),
    HealthFull   = Color3.fromRGB(0, 255, 0),
    HealthLow    = Color3.fromRGB(255, 0, 0),
}

-- ═══════════════════════════════════════════════════════════
-- ESP HELPERS & SKELETON
-- ═══════════════════════════════════════════════════════════
local function mk(c, p)
    local d = Drawing.new(c)
    for k, v in pairs(p) do d[k] = v end
    d.Visible = false
    return d
end

local function w2s(pos)
    local sp, on = Camera:WorldToViewportPoint(pos)
    if not on or sp.Z <= 0 then return nil end
    return Vector2.new(sp.X, sp.Y)
end

local function isVisible(hrp, char)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { LP.Character, char }
    params.IgnoreWater = true
    local origin = Camera.CFrame.Position
    local hit = Workspace:Raycast(origin, hrp.Position - origin, params)
    return hit == nil
end

local SK_R15 = {
    {"Head","UpperTorso"}, {"UpperTorso","LowerTorso"},
    {"UpperTorso","LeftUpperArm"}, {"LeftUpperArm","LeftLowerArm"},
    {"LeftLowerArm","LeftHand"}, {"UpperTorso","RightUpperArm"},
    {"RightUpperArm","RightLowerArm"}, {"RightLowerArm","RightHand"},
    {"LowerTorso","LeftUpperLeg"}, {"LeftUpperLeg","LeftLowerLeg"},
    {"LeftLowerLeg","LeftFoot"}, {"LowerTorso","RightUpperLeg"},
    {"RightUpperLeg","RightLowerLeg"}, {"RightLowerLeg","RightFoot"},
}
local SK_R6 = {
    {"Head","Torso"}, {"Torso","Left Arm"}, {"Torso","Right Arm"},
    {"Torso","Left Leg"}, {"Torso","Right Leg"},
}

local function getBones(char)
    local map = char:FindFirstChild("UpperTorso") and SK_R15 or SK_R6
    local out = {}
    for _, pair in ipairs(map) do
        local a = char:FindFirstChild(pair[1])
        local b = char:FindFirstChild(pair[2])
        if a and b then table.insert(out, {a, b}) end
    end
    return out
end

-- ═══════════════════════════════════════════════════════════
-- RENDER LOOPS
-- ═══════════════════════════════════════════════════════════
local renders = {}

local function buildSet()
    return {
        box  = mk("Square", {Thickness=1, Filled=false, Color=CONFIG.BoxColor}),
        name = mk("Text",   {Size=13, Center=true, Outline=true, Color=CONFIG.NameColor}),
        dist = mk("Text",   {Size=11, Center=true, Outline=true, Color=CONFIG.DistColor}),
        hpBg = mk("Square", {Thickness=1, Filled=true, Color=Color3.new(0,0,0), Transparency=0.4}),
        hpFg = mk("Square", {Thickness=1, Filled=true, Color=CONFIG.HealthFull, Transparency=0.2}),
        line = mk("Line",   {Thickness=1, Color=CONFIG.SnaplineColor, Transparency=0.5}),
        dot  = mk("Circle", {Thickness=1, Filled=true, Radius=3, Color=CONFIG.HeadDotColor}),
        bones= {},
    }
end

local function hideSet(set)
    for k, d in pairs(set) do
        if k == "bones" then for _, l in ipairs(d) do l.Visible = false end
        else d.Visible = false end
    end
end

local function destroySet(set)
    for k, d in pairs(set) do
        if k == "bones" then for _, l in ipairs(d) do l:Remove() end
        else d:Remove() end
    end
end

local function ensureBones(set, n)
    while #set.bones < n do
        table.insert(set.bones, mk("Line", {Thickness=1.5, Color=CONFIG.SkeletonColor, Transparency=0.2}))
    end
    for i = n + 1, #set.bones do set.bones[i].Visible = false end
end

local function render(player)
    if player == LP then return end
    local char = player.Character
    if not char then if renders[player] then hideSet(renders[player]) end; return end
    local hrp  = char:FindFirstChild("HumanoidRootPart")
    local hum  = char:FindFirstChildOfClass("Humanoid")
    local head = char:FindFirstChild("Head")
    if not hrp or not hum or hum.Health <= 0 or not head then
        if renders[player] then hideSet(renders[player]) end; return
    end

    local set = renders[player] or buildSet()
    renders[player] = set

    if CONFIG.TeamCheck and player.Team and LP.Team and player.Team == LP.Team then hideSet(set); return end

    local myChar = LP.Character
    local myHrp  = myChar and myChar:FindFirstChild("HumanoidRootPart")
    if not myHrp then hideSet(set); return end
    local dist = (hrp.Position - myHrp.Position).Magnitude
    if dist > CONFIG.MaxDistance then hideSet(set); return end
    if CONFIG.WallCheck and not isVisible(hrp, char) then hideSet(set); return end

    local headS = w2s(head.Position)
    local rootS = w2s(hrp.Position)
    if not headS or not rootS then hideSet(set); return end

    local h = (rootS.Y - headS.Y) * 2.2
    if h < 8 then hideSet(set); return end
    local w = h * 0.5
    local bx = headS.X - w / 2
    local by = headS.Y - h * 0.1

    set.box.Visible = CONFIG.Box
    if CONFIG.Box then
        set.box.Size = Vector2.new(w, h)
        set.box.Position = Vector2.new(bx, by)
    end

    set.name.Visible = CONFIG.Name
    if CONFIG.Name then
        set.name.Text = player.Name
        set.name.Position = Vector2.new(headS.X, by - 16)
    end

    set.dist.Visible = CONFIG.Distance
    if CONFIG.Distance then
        set.dist.Text = string.format("[%dm]", math.floor(dist / 3))
        set.dist.Position = Vector2.new(headS.X, by + h + 2)
    end

    set.hpBg.Visible = CONFIG.Health
    set.hpFg.Visible = CONFIG.Health
    if CONFIG.Health then
        local pct = math.clamp(hum.Health / hum.MaxHealth, 0, 1)
        set.hpBg.Size = Vector2.new(3, h)
        set.hpBg.Position = Vector2.new(bx - 6, by)
        set.hpFg.Size = Vector2.new(3, h * pct)
        set.hpFg.Position = Vector2.new(bx - 6, by + h * (1 - pct))
        set.hpFg.Color = CONFIG.HealthLow:Lerp(CONFIG.HealthFull, pct)
    end

    set.line.Visible = CONFIG.Snapline
    if CONFIG.Snapline then
        local vp = Camera.ViewportSize
        set.line.From = Vector2.new(vp.X / 2, vp.Y)
        set.line.To = Vector2.new(headS.X, by + h)
    end

    set.dot.Visible = CONFIG.HeadDot
    if CONFIG.HeadDot then set.dot.Position = headS end

    if CONFIG.Skeleton then
        local bones = getBones(char)
        ensureBones(set, #bones)
        for i, pair in ipairs(bones) do
            local sa = w2s(pair[1].Position)
            local sb = w2s(pair[2].Position)
            local l  = set.bones[i]
            if sa and sb then
                l.Visible = true; l.From = sa; l.To = sb
            else l.Visible = false end
        end
    else
        for _, l in ipairs(set.bones) do l.Visible = false end
    end
end

local accum = 0
RunService.Heartbeat:Connect(function(dt)
    if not CONFIG.Enabled then
        for _, s in pairs(renders) do hideSet(s) end
        return
    end
    accum = accum + dt
    if accum < CONFIG.UpdateInterval + math.random() * CONFIG.JitterMax then return end
    accum = 0
    for _, p in ipairs(Players:GetPlayers()) do pcall(render, p) end
end)

Players.PlayerRemoving:Connect(function(p)
    local s = renders[p]
    if s then destroySet(s); renders[p] = nil end
end)

-- ═══════════════════════════════════════════════════════════
-- RADIAL MOBILE GUI (NO DRAG, TOUCH FRIENDLY)
-- ═══════════════════════════════════════════════════════════
local C = {
    Bg=Color3.fromRGB(18,20,26), Border=Color3.fromRGB(0,220,180),
    Text=Color3.fromRGB(230,235,245), Dim=Color3.fromRGB(150,158,175),
    On=Color3.fromRGB(0,220,180), Off=Color3.fromRGB(70,76,92)
}

local FEATURES = {
    {label="ESP",        key="Enabled"},
    {label="Box",        key="Box"},
    {label="Line",       key="Snapline"},
    {label="Head",       key="HeadDot"},
    {label="Name",       key="Name"},
    {label="Dist",       key="Distance"},
    {label="HP",         key="Health"},
    {label="Wall",       key="WallCheck"},
}

-- State
local menuOpen = false
local animProg = 0 -- 0 to 1 untuk animasi melengkung
local cx, cy     = 0, 0
local mainBtnR   = 30
local itemBtnR   = 24

local function gmk(c, p)
    local d = Drawing.new(c)
    for k, v in pairs(p) do d[k] = v end
    d.Visible = false
    return d
end

local gui = {
    mainCircle = gmk("Circle",{Filled=true,Thickness=0,Color=C.Bg,Transparency=0.1}),
    mainBorder = gmk("Circle",{Filled=false,Thickness=2,Color=C.Border,Transparency=0.2}),
    mainText   = gmk("Text",{Size=14,Center=true,Outline=true,Color=C.Text,Text="ESP"}),
    items = {}
}

for i, f in ipairs(FEATURES) do
    gui.items[i] = {
        bg  = gmk("Circle",{Filled=true,Thickness=0,Color=C.Off,Transparency=0.2}),
        txt = gmk("Text",{Size=12,Center=true,Outline=true,Color=C.Text,Text=f.label}),
        f   = f
    }
end

local function updateGuiPositions()
    local v = Camera.ViewportSize
    cx = v.X - 50
    cy = v.Y - 100

    gui.mainCircle.Position = Vector2.new(cx, cy)
    gui.mainCircle.Radius = mainBtnR
    gui.mainBorder.Position = Vector2.new(cx, cy)
    gui.mainBorder.Radius = mainBtnR
    gui.mainText.Position = Vector2.new(cx, cy - 6)

    local n = #FEATURES
    local startAngle = math.rad(180) -- mulai dari kiri
    local endAngle   = math.rad(270) -- sampai atas
    local radiusDist = 80

    for i, item in ipairs(gui.items) do
        local angle = startAngle + (endAngle - startAngle) * ((i - 1) / math.max(1, n - 1))
        local dist  = radiusDist * animProg
        local ix = cx + math.cos(angle) * dist
        local iy = cy + math.sin(angle) * dist

        item.bg.Position = Vector2.new(ix, iy)
        item.bg.Radius = itemBtnR
        item.txt.Position = Vector2.new(ix, iy - 6)
        
        local val = CONFIG[item.f.key]
        item.bg.Color = val and C.On or C.Off
        item.bg.Transparency = animProg > 0.5 and 0.3 or 0 -- fade out pas nutup
    end
end

local function applyGuiVisibility()
    gui.mainCircle.Visible = true
    gui.mainBorder.Visible = true
    gui.mainText.Visible = true
    gui.mainText.Text = menuOpen and "X" or "ESP"

    for _, item in ipairs(gui.items) do
        item.bg.Visible = animProg > 0.1
        item.txt.Visible = animProg > 0.5
    end
end

-- Render loop buat animasi buka-tutup
RunService.RenderStepped:Connect(function(dt)
    if menuOpen and animProg < 1 then
        animProg = math.min(1, animProg + dt * 8) -- animasi cepat 0.12 detik
    elseif not menuOpen and animProg > 0 then
        animProg = math.max(0, animProg - dt * 8)
    end
    updateGuiPositions()
    applyGuiVisibility()
end)

-- Hit Detection
local function distSq(x1,y1,x2,y2)
    local dx, dy = x1-x2, y1-y2
    return dx*dx + dy*dy
end

-- Input Tangkap Klik
UIS.InputBegan:Connect(function(input)
    if input.UserInputType ~= Enum.UserInputType.Touch
       and input.UserInputType ~= Enum.UserInputType.MouseButton1 then return end
    local mx, my = input.Position.X, input.Position.Y

    -- 1. Cek Klik Tombol Utama
    if distSq(mx, my, cx, cy) <= mainBtnR^2 then
        menuOpen = not menuOpen
        return
    end

    -- 2. Cek Klik Tombol Melengkung (hanya jika menu terbuka penuh)
    if menuOpen and animProg > 0.8 then
        for i, item in ipairs(gui.items) do
            if distSq(mx, my, item.bg.Position.X, item.bg.Position.Y) <= itemBtnR^2 then
                local k = item.f.key
                CONFIG[k] = not CONFIG[k]
                break
            end
        end
    end
end)

-- Handle Resize (Misal HP diputar)
Camera:GetPropertyChangedSignal("ViewportSize"):Connect(updateGuiPositions)
