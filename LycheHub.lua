-- LycheHub | AirDrop Arena S5 | combined ESP + GUI + anti-detect
-- Drawing only. Delta-compatible. One loadstring.
-- Replace isi LycheHub.lua di repo dengan file ini.

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
-- HELPERS
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

-- ═══════════════════════════════════════════════════════════
-- SKELETON MAP
-- ═══════════════════════════════════════════════════════════
local SK_R15 = {
    {"Head","UpperTorso"}, {"UpperTorso","LowerTorso"},
    {"UpperTorso","LeftUpperArm"}, {"LeftUpperArm","LeftLowerArm"},
    {"LeftLowerArm","LeftHand"},
    {"UpperTorso","RightUpperArm"}, {"RightUpperArm","RightLowerArm"},
    {"RightLowerArm","RightHand"},
    {"LowerTorso","LeftUpperLeg"}, {"LeftUpperLeg","LeftLowerLeg"},
    {"LeftLowerLeg","LeftFoot"},
    {"LowerTorso","RightUpperLeg"}, {"RightUpperLeg","RightLowerLeg"},
    {"RightLowerLeg","RightFoot"},
}
local SK_R6 = {
    {"Head","Torso"},
    {"Torso","Left Arm"}, {"Torso","Right Arm"},
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
-- RENDER SETS
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
        if k == "bones" then
            for _, l in ipairs(d) do l.Visible = false end
        else
            d.Visible = false
        end
    end
end

local function destroySet(set)
    for k, d in pairs(set) do
        if k == "bones" then
            for _, l in ipairs(d) do l:Remove() end
        else
            d:Remove()
        end
    end
end

local function ensureBones(set, n)
    while #set.bones < n do
        table.insert(set.bones, mk("Line", {
            Thickness=1.5, Color=CONFIG.SkeletonColor, Transparency=0.2,
        }))
    end
    for i = n + 1, #set.bones do set.bones[i].Visible = false end
end

-- ═══════════════════════════════════════════════════════════
-- PER-PLAYER RENDER
-- ═══════════════════════════════════════════════════════════
local function render(player)
    if player == LP then return end
    local char = player.Character
    if not char then
        if renders[player] then hideSet(renders[player]) end
        return
    end
    local hrp  = char:FindFirstChild("HumanoidRootPart")
    local hum  = char:FindFirstChildOfClass("Humanoid")
    local head = char:FindFirstChild("Head")
    if not hrp or not hum or hum.Health <= 0 or not head then
        if renders[player] then hideSet(renders[player]) end
        return
    end

    local set = renders[player] or buildSet()
    renders[player] = set

    if CONFIG.TeamCheck and player.Team and LP.Team and player.Team == LP.Team then
        hideSet(set); return
    end

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

    if CONFIG.Box then
        set.box.Visible  = true
        set.box.Size     = Vector2.new(w, h)
        set.box.Position = Vector2.new(bx, by)
        set.box.Color    = CONFIG.BoxColor
    else set.box.Visible = false end

    if CONFIG.Name then
        set.name.Visible  = true
        set.name.Text     = player.Name
        set.name.Position = Vector2.new(headS.X, by - 16)
    else set.name.Visible = false end

    if CONFIG.Distance then
        set.dist.Visible  = true
        set.dist.Text     = string.format("[%dm]", math.floor(dist / 3))
        set.dist.Position = Vector2.new(headS.X, by + h + 2)
    else set.dist.Visible = false end

    if CONFIG.Health then
        local pct = math.clamp(hum.Health / hum.MaxHealth, 0, 1)
        set.hpBg.Visible  = true
        set.hpBg.Size     = Vector2.new(3, h)
        set.hpBg.Position = Vector2.new(bx - 6, by)
        set.hpFg.Visible  = true
        set.hpFg.Size     = Vector2.new(3, h * pct)
        set.hpFg.Position = Vector2.new(bx - 6, by + h * (1 - pct))
        set.hpFg.Color    = CONFIG.HealthLow:Lerp(CONFIG.HealthFull, pct)
    else
        set.hpBg.Visible = false; set.hpFg.Visible = false
    end

    if CONFIG.Snapline then
        local vp = Camera.ViewportSize
        set.line.Visible = true
        set.line.From    = Vector2.new(vp.X / 2, vp.Y)
        set.line.To      = Vector2.new(headS.X, by + h)
        set.line.Color   = CONFIG.SnaplineColor
    else set.line.Visible = false end

    if CONFIG.HeadDot then
        set.dot.Visible  = true
        set.dot.Position = headS
        set.dot.Color    = CONFIG.HeadDotColor
    else set.dot.Visible = false end

    if CONFIG.Skeleton then
        local bones = getBones(char)
        ensureBones(set, #bones)
        for i, pair in ipairs(bones) do
            local sa = w2s(pair[1].Position)
            local sb = w2s(pair[2].Position)
            local l  = set.bones[i]
            if sa and sb then
                l.Visible = true
                l.From    = sa
                l.To      = sb
                l.Color   = CONFIG.SkeletonColor
            else l.Visible = false end
        end
    else
        for _, l in ipairs(set.bones) do l.Visible = false end
    end
end

-- ═══════════════════════════════════════════════════════════
-- MAIN LOOP (anti-detect throttle + jitter)
-- ═══════════════════════════════════════════════════════════
local accum = 0
RunService.Heartbeat:Connect(function(dt)
    if not CONFIG.Enabled then
        for _, s in pairs(renders) do hideSet(s) end
        return
    end
    accum = accum + dt
    if accum < CONFIG.UpdateInterval + math.random() * CONFIG.JitterMax then return end
    accum = 0
    for _, p in ipairs(Players:GetPlayers()) do
        pcall(render, p)
    end
end)

Players.PlayerRemoving:Connect(function(p)
    local s = renders[p]
    if s then destroySet(s); renders[p] = nil end
end)

-- ═══════════════════════════════════════════════════════════
-- GUI MOBILE
-- ═══════════════════════════════════════════════════════════
local C = {
    Bg=Color3.fromRGB(18,20,26), Header=Color3.fromRGB(28,32,42),
    Border=Color3.fromRGB(0,220,180), Text=Color3.fromRGB(230,235,245),
    Dim=Color3.fromRGB(150,158,175), On=Color3.fromRGB(0,220,180),
    Off=Color3.fromRGB(70,76,92), Hover=Color3.fromRGB(38,44,58),
}
local PANEL_W, HEADER_H, ROW_H, PAD = 250, 40, 40, 10

local FEATURES = {
    {label="ESP",        key="Enabled"},
    {label="Box",        key="Box"},
    {label="Snapline",   key="Snapline"},
    {label="Head Dot",   key="HeadDot"},
    {label="Name",       key="Name"},
    {label="Distance",   key="Distance"},
    {label="Health Bar", key="Health"},
    {label="Skeleton",   key="Skeleton"},
    {label="Wall Check", key="WallCheck"},
}

local gs = {visible=true, collapsed=false, x=20, y=70,
            dragging=false, dragOff=Vector2.new(), rows={}, hoverKey=nil}

local function gmk(c, p)
    local d = Drawing.new(c)
    for k, v in pairs(p) do d[k] = v end
    d.Visible = false
    return d
end

local G = {
    bg = gmk("Square",{Filled=true,Thickness=0,Color=C.Bg,Transparency=0.1}),
    hd = gmk("Square",{Filled=true,Thickness=0,Color=C.Header}),
    bd = gmk("Square",{Filled=false,Thickness=1,Color=C.Border,Transparency=0.2}),
    tt = gmk("Text",{Size=15,Center=false,Color=C.Text}),
    cl = gmk("Text",{Size=15,Center=true,Color=C.Dim}),
}

local function grow(i)
    if gs.rows[i] then return gs.rows[i] end
    local r = {
        bg = gmk("Square",{Filled=true,Thickness=0,Color=C.Hover,Transparency=1}),
        lb = gmk("Text",{Size=14,Center=false,Color=C.Text}),
        kn = gmk("Square",{Filled=true,Thickness=0,Color=C.Off}),
        kb = gmk("Square",{Filled=true,Thickness=0,Color=C.Header}),
    }
    gs.rows[i] = r
    return r
end

local function pHeight()
    if gs.collapsed then return HEADER_H end
    return HEADER_H + PAD + #FEATURES * ROW_H + PAD
end

local function refresh()
    local h = pHeight()
    G.bg.Position = Vector2.new(gs.x, gs.y)
    G.bg.Size     = Vector2.new(PANEL_W, h)
    G.hd.Position = Vector2.new(gs.x, gs.y)
    G.hd.Size     = Vector2.new(PANEL_W, HEADER_H)
    G.bd.Position = Vector2.new(gs.x, gs.y)
    G.bd.Size     = Vector2.new(PANEL_W, h)
    G.tt.Position = Vector2.new(gs.x + PAD + 2, gs.y + 11)
    G.tt.Text     = "LYCHE ESP"
    G.cl.Position = Vector2.new(gs.x + PANEL_W - 28, gs.y + 11)
    G.cl.Text     = gs.collapsed and "v" or "^"

    for i, f in ipairs(FEATURES) do
        local r = grow(i)
        local y = gs.y + HEADER_H + PAD + (i - 1) * ROW_H
        r.bg.Position     = Vector2.new(gs.x + 6, y)
        r.bg.Size         = Vector2.new(PANEL_W - 12, ROW_H - 6)
        r.bg.Transparency = (gs.hoverKey == f.key) and 0.5 or 1
        r.lb.Position     = Vector2.new(gs.x + PAD + 4, y + 9)
        r.lb.Text         = f.label

        local val = CONFIG[f.key]
        local kw, kh = 40, 20
        local kx = gs.x + PANEL_W - PAD - kw - 6
        local ky = y + (ROW_H - 6 - kh) / 2
        r.kb.Position = Vector2.new(kx, ky)
        r.kb.Size     = Vector2.new(kw, kh)
        r.kb.Color    = val and C.On or C.Off
        local kk = kh - 6
        r.kn.Position = Vector2.new(kx + (val and (kw - kk - 3) or 3), ky + 3)
        r.kn.Size     = Vector2.new(kk, kk)
        r.kn.Color    = val and Color3.new(1,1,1) or C.Dim
    end
end

local function setVisible(v)
    gs.visible = v
    G.bg.Visible = v; G.hd.Visible = v; G.bd.Visible = v
    G.tt.Visible = v; G.cl.Visible = v
    for i = 1, #FEATURES do
        local r = gs.rows[i]
        if r then
            local show = v and not gs.collapsed
            r.bg.Visible = show; r.lb.Visible = show
            r.kn.Visible = show; r.kb.Visible = show
        end
    end
end

local function pointIn(mx,my,x,y,w,h)
    return mx>=x and mx<=x+w and my>=y and my<=y+h
end

local function hitTest(mx,my)
    if pointIn(mx,my,gs.x,gs.y,PANEL_W,HEADER_H) then
        if pointIn(mx,my,gs.x+PANEL_W-36,gs.y,36,HEADER_H) then return "collapse" end
        return "header"
    end
    if gs.collapsed then return nil end
    for i, f in ipairs(FEATURES) do
        local y = gs.y + HEADER_H + PAD + (i - 1) * ROW_H
        if pointIn(mx,my,gs.x+6,y,PANEL_W-12,ROW_H-6) then return "row", i end
    end
    return nil
end

-- FAB
local FAB = {
    size = 48, x = 0, y = 0, visible = true,
    bg = gmk("Circle",{Filled=true,Thickness=0,Color=C.Border,Transparency=0.2}),
    tx = gmk("Text",{Size=15,Center=true,Outline=true,Color=C.Text}),
}

local function posFab()
    local v = Camera.ViewportSize
    FAB.x = v.X - FAB.size - 14
    FAB.y = v.Y - FAB.size - 80
    FAB.bg.Position = Vector2.new(FAB.x, FAB.y)
    FAB.bg.Size     = Vector2.new(FAB.size, FAB.size)
    FAB.tx.Position = Vector2.new(FAB.x + FAB.size/2, FAB.y + FAB.size/2 - 8)
    FAB.tx.Text     = "ESP"
end

local function fabHit(mx,my)
    local dx = mx - (FAB.x + FAB.size/2)
    local dy = my - (FAB.y + FAB.size/2)
    return dx*dx + dy*dy <= (FAB.size/2)^2
end

-- INPUT
local function onBegan(input)
    if input.UserInputType ~= Enum.UserInputType.Touch
       and input.UserInputType ~= Enum.UserInputType.MouseButton1 then return end
    local mx, my = input.Position.X, input.Position.Y

    if FAB.visible and fabHit(mx,my) then
        setVisible(not gs.visible)
        return
    end
    if not gs.visible then return end

    local hit, idx = hitTest(mx,my)
    if hit == "collapse" then
        gs.collapsed = not gs.collapsed
        refresh(); setVisible(gs.visible)
    elseif hit == "header" then
        gs.dragging = true
        gs.dragOff = Vector2.new(mx - gs.x, my - gs.y)
    elseif hit == "row" then
        local f = FEATURES[idx]
        CONFIG[f.key] = not CONFIG[f.key]
        refresh()
    end
end

local function onChanged(input)
    if not gs.dragging then return end
    if input.UserInputType ~= Enum.UserInputType.Touch
       and input.UserInputType ~= Enum.UserInputType.MouseMovement then return end
    local mx, my = input.Position.X, input.Position.Y
    gs.x = mx - gs.dragOff.X
    gs.y = my - gs.dragOff.Y
    refresh()
end

local function onEnded(input)
    if input.UserInputType == Enum.UserInputType.Touch
       or input.UserInputType == Enum.UserInputType.MouseButton1 then
        gs.dragging = false
    end
end

posFab()
refresh()
setVisible(true)
FAB.bg.Visible = true
FAB.tx.Visible = true

UIS.InputBegan:Connect(onBegan)
UIS.InputChanged:Connect(onChanged)
UIS.InputEnded:Connect(onEnded)

Camera:GetPropertyChangedSignal("ViewportSize"):Connect(function()
    posFab(); refresh()
end)

RunService.RenderStepped:Connect(function()
    refresh()
    FAB.bg.Visible = FAB.visible
    FAB.tx.Visible = FAB.visible
end)
