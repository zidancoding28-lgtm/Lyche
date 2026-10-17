-- LycheHub | AirDrop Arena S5 | Dark Checkbox Menu
-- Drawing only. Delta-compatible. Smooth Mobile Drag.

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
    Skeleton     = true,
    Snapline     = true,
    HeadDot      = true,
    Name         = true,
    Distance     = true,
    Health       = true,
    WallCheck    = false,
    TeamCheck    = false,
    MaxDistance  = 1000,
    UpdateInterval = 0.05,
    JitterMax    = 0.02,
    BoxColor     = Color3.fromRGB(0, 255, 140),
    SkeletonColor= Color3.fromRGB(255, 255, 255),
    SnaplineColor= Color3.fromRGB(0, 255, 140),
    HeadDotColor = Color3.fromRGB(255, 60, 60),
}

-- ═══════════════════════════════════════════════════════════
-- ESP HELPERS (Sama seperti versi fix streaming)
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

local function getESPBase(char)
    if not char then return nil end
    local hrp = char:FindFirstChild("HumanoidRootPart")
    if hrp then return hrp, char:FindFirstChild("Head") end
    local torso = char:FindFirstChild("UpperTorso") or char:FindFirstChild("Torso")
    if torso then return torso, char:FindFirstChild("Head") end
    local fallback
    for _, v in ipairs(char:GetDescendants()) do
        if v:IsA("BasePart") then return v, v end
    end
    return nil, nil
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

local renders = {}
local function buildSet()
    return {
        box  = mk("Square", {Thickness=1, Filled=false, Color=CONFIG.BoxColor}),
        name = mk("Text",   {Size=13, Center=true, Outline=true, Color=Color3.new(1,1,1)}),
        dist = mk("Text",   {Size=11, Center=true, Outline=true, Color=Color3.fromRGB(200,200,200)}),
        hpBg = mk("Square", {Thickness=1, Filled=true, Color=Color3.new(0,0,0), Transparency=0.4}),
        hpFg = mk("Square", {Thickness=1, Filled=true, Color=Color3.fromRGB(0,255,0), Transparency=0.2}),
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
    local hum = char:FindFirstChildOfClass("Humanoid")
    if not hum or hum.Health <= 0 then if renders[player] then hideSet(renders[player]) end; return end
    local basePart, headPart = getESPBase(char)
    if not basePart or not headPart then if renders[player] then hideSet(renders[player]) end; return end

    local set = renders[player] or buildSet()
    renders[player] = set
    local myHrp = LP.Character and LP.Character:FindFirstChild("HumanoidRootPart")
    if not myHrp then hideSet(set); return end
    
    local dist = (basePart.Position - myHrp.Position).Magnitude
    if dist > CONFIG.MaxDistance then hideSet(set); return end

    local headS = w2s(headPart.Position)
    local rootS = w2s(basePart.Position)
    if not headS or not rootS then hideSet(set); return end

    local h = math.abs(rootS.Y - headS.Y) * 2.5
    if h < 10 then h = 40 end
    local w = h * 0.5
    local bx = headS.X - w / 2
    local by = headS.Y - (h * 0.15)

    set.box.Visible = CONFIG.Box
    if CONFIG.Box then set.box.Size = Vector2.new(w, h); set.box.Position = Vector2.new(bx, by) end

    set.name.Visible = CONFIG.Name
    if CONFIG.Name then set.name.Text = player.Name; set.name.Position = Vector2.new(headS.X, by - 16) end

    set.dist.Visible = CONFIG.Distance
    if CONFIG.Distance then set.dist.Text = string.format("[%dm]", math.floor(dist / 3)); set.dist.Position = Vector2.new(headS.X, by + h + 2) end

    set.hpBg.Visible = CONFIG.Health; set.hpFg.Visible = CONFIG.Health
    if CONFIG.Health then
        local pct = math.clamp(hum.Health / hum.MaxHealth, 0, 1)
        set.hpBg.Size = Vector2.new(3, h); set.hpBg.Position = Vector2.new(bx - 6, by)
        set.hpFg.Size = Vector2.new(3, h * pct); set.hpFg.Position = Vector2.new(bx - 6, by + h * (1 - pct))
        set.hpFg.Color = Color3.fromRGB(255,0,0):Lerp(Color3.fromRGB(0,255,0), pct)
    end

    set.line.Visible = CONFIG.Snapline
    if CONFIG.Snapline then set.line.From = Vector2.new(Camera.ViewportSize.X / 2, Camera.ViewportSize.Y); set.line.To = Vector2.new(headS.X, by + h) end

    set.dot.Visible = CONFIG.HeadDot
    if CONFIG.HeadDot then set.dot.Position = headS end

    if CONFIG.Skeleton then
        local bones = getBones(char); ensureBones(set, #bones)
        for i, pair in ipairs(bones) do
            local sa = w2s(pair[1].Position); local sb = w2s(pair[2].Position)
            local l = set.bones[i]
            if sa and sb then l.Visible = true; l.From = sa; l.To = sb else l.Visible = false end
        end
    end
end

local accum = 0
RunService.Heartbeat:Connect(function(dt)
    if not CONFIG.Enabled then for _, s in pairs(renders) do hideSet(s) end; return end
    accum = accum + dt
    if accum < CONFIG.UpdateInterval + math.random() * CONFIG.JitterMax then return end
    accum = 0
    for _, p in ipairs(Players:GetPlayers()) do pcall(render, p) end
end)

Players.PlayerRemoving:Connect(function(p)
    local s = renders[p]; if s then destroySet(s); renders[p] = nil end
end)

-- ═══════════════════════════════════════════════════════════
-- DARK THEME GUI (CHECKBOX & DRAG HEADER)
-- ═══════════════════════════════════════════════════════════
local C = {
    Bg = Color3.fromRGB(15, 15, 18),         -- Hitam pekat
    Header = Color3.fromRGB(25, 25, 30),     -- Hitam agak terang buat header
    Border = Color3.fromRGB(60, 60, 70),     -- Garis tepi abu-abu
    Text = Color3.fromRGB(240, 240, 240),    -- Putih
    TextDim = Color3.fromRGB(150, 150, 160), -- Abu-abu text
    CheckOn = Color3.fromRGB(0, 220, 120),   -- Hijau centang
    CheckOff = Color3.fromRGB(40, 40, 45),   -- Kotak kosong
}

local PANEL_W, HEADER_H, ROW_H, PAD = 220, 40, 36, 8
local FEATURES = {
    {label="ESP Master", key="Enabled"}, {label="Box", key="Box"},
    {label="Skeleton", key="Skeleton"},  {label="Snapline", key="Snapline"},
    {label="Head Dot", key="HeadDot"},   {label="Name", key="Name"},
    {label="Distance", key="Distance"},  {label="Health Bar", key="Health"},
    {label="Wall Check", key="WallCheck"}
}

local gs = {visible=true, x=30, y=100, dragging=false, dragOff=Vector2.new(), rows={}}

local function gmk(c, p)
    local d = Drawing.new(c)
    for k, v in pairs(p) do d[k] = v end
    d.Visible = false
    return d
end

local G = {
    bg = gmk("Square",{Filled=true,Thickness=0,Color=C.Bg,Transparency=0.1}),
    hd = gmk("Square",{Filled=true,Thickness=0,Color=C.Header}),
    bd = gmk("Square",{Filled=false,Thickness=1,Color=C.Border}),
    title = gmk("Text",{Size=14,Center=false,Color=C.Text,Text="LYCHE HUB"}),
    close = gmk("Text",{Size=16,Center=true,Color=C.TextDim,Text="X"}),
}

for i=1, #FEATURES do
    gs.rows[i] = {
        bg = gmk("Square",{Filled=true,Thickness=0,Color=C.Bg,Transparency=0.5}),
        lb = gmk("Text",{Size=13,Center=false,Color=C.Text}),
        box = gmk("Square",{Filled=true,Thickness=1,Color=C.CheckOff}),
        tick = gmk("Text",{Size=14,Center=true,Color=Color3.new(1,1,1),Text="✓"}),
    }
end

local function updateUI()
    if not gs.visible then
        for _, v in pairs(G) do v.Visible = false end
        for _, r in pairs(gs.rows) do r.bg.Visible=false; r.lb.Visible=false; r.box.Visible=false; r.tick.Visible=false end
        return
    end

    local totalH = HEADER_H + PAD + (#FEATURES * ROW_H) + PAD
    G.bg.Position = Vector2.new(gs.x, gs.y); G.bg.Size = Vector2.new(PANEL_W, totalH)
    G.hd.Position = Vector2.new(gs.x, gs.y); G.hd.Size = Vector2.new(PANEL_W, HEADER_H)
    G.bd.Position = Vector2.new(gs.x, gs.y); G.bd.Size = Vector2.new(PANEL_W, totalH)
    
    G.title.Position = Vector2.new(gs.x + PAD + 4, gs.y + 12)
    G.close.Position = Vector2.new(gs.x + PANEL_W - 20, gs.y + 12)

    for i, f in ipairs(FEATURES) do
        local r = gs.rows[i]
        local y = gs.y + HEADER_H + PAD + (i-1)*ROW_H
        r.bg.Position = Vector2.new(gs.x, y); r.bg.Size = Vector2.new(PANEL_W, ROW_H)
        r.lb.Position = Vector2.new(gs.x + PAD + 4, y + 9); r.lb.Text = f.label
        
        local val = CONFIG[f.key]
        local bx = gs.x + PANEL_W - 30
        local by = y + (ROW_H - 16)/2
        
        r.box.Position = Vector2.new(bx, by); r.box.Size = Vector2.new(16, 16)
        r.box.Color = val and C.CheckOn or C.CheckOff
        r.box.Transparency = 0
        
        r.tick.Position = Vector2.new(bx + 8, by - 1)
        r.tick.Visible = val
        
        r.bg.Visible = true; r.lb.Visible = true; r.box.Visible = true
    end
    G.bg.Visible = true; G.hd.Visible = true; G.bd.Visible = true; G.title.Visible = true; G.close.Visible = true
end

local function inRect(mx,my,x,y,w,h) return mx>=x and mx<=x+w and my>=y and my<=y+h end

UIS.InputBegan:Connect(function(input)
    if input.UserInputType ~= Enum.UserInputType.Touch and input.UserInputType ~= Enum.UserInputType.MouseButton1 then return end
    local mx, my = input.Position.X, input.Position.Y

    -- Tombol Close
    if gs.visible and inRect(mx,my, gs.x + PANEL_W - 30, gs.y, 30, HEADER_H) then
        gs.visible = false
        updateUI()
        return
    end

    if not gs.visible then return end

    -- Area Drag (Header)
    if inRect(mx,my, gs.x, gs.y, PANEL_W, HEADER_H) then
        gs.dragging = true
        gs.dragOff = Vector2.new(mx - gs.x, my - gs.y)
        return
    end

    -- Area Klik Fitur (Seluruh baris)
    for i, f in ipairs(FEATURES) do
        local y = gs.y + HEADER_H + PAD + (i-1)*ROW_H
        if inRect(mx,my, gs.x, y, PANEL_W, ROW_H) then
            CONFIG[f.key] = not CONFIG[f.key]
            updateUI()
            return
        end
    end
end)

UIS.InputChanged:Connect(function(input)
    if not gs.dragging then return end
    if input.UserInputType == Enum.UserInputType.Touch or input.UserInputType == Enum.UserInputType.MouseMovement then
        gs.x = input.Position.X - gs.dragOff.X
        gs.y = input.Position.Y - gs.dragOff.Y
        updateUI()
    end
end)

UIS.InputEnded:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.Touch or input.UserInputType == Enum.UserInputType.MouseButton1 then
        gs.dragging = false
    end
end)

updateUI()
RunService.RenderStepped:Connect(updateUI)
