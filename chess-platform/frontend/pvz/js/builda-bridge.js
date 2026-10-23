(function () {
    var GAME_W = 900, GAME_H = 600;
    var SAVE_KEY = "save_main";
    var RANK_ID = "adventure_level";
    var PAY_POINTS = {
        sun_small: { price: 100, sun: 500, name: "500阳光" },
        sun_medium: { price: 300, sun: 2000, name: "2000阳光" },
        sun_large: { price: 1000, sun: 8000, name: "8000阳光" }
    };

    var saveData = { version: 1, progress: 1, bankSun: 0, lastLvl: 0 };
    var saveTimer = null;
    var rankList = [];
    var selfRank = null;
    var mobileActive = false;
    var isDev = false;
    var devInfiniteTimer = null;
    var devNoCdTimer = null;
    var DEV_ROLE_ID = "1080772";
    var SPEED_MAP = { 1: [1, 10], 2: [2, 10], 5: [5, 10], 10: [5, 5] };
    var MAX_ADV_LEVEL = 50;

    function clampProgress(p) {
        p = parseInt(p, 10);
        if (isNaN(p) || p < 1) return 1;
        if (p > MAX_ADV_LEVEL + 1) return MAX_ADV_LEVEL + 1;
        return p;
    }

    function hasBuilda() {
        return !!(window.Builda && Builda.runtime);
    }
    function hasKV() {
        return !!(window.Builda && Builda.privateKV);
    }
    function hasIAP() {
        return !!(window.Builda && Builda.iap);
    }
    function hasRank() {
        return !!(window.Builda && Builda.rank);
    }

    function applyScale() {
        if (!mobileActive) return;
        var sw = window.innerWidth, sh = window.innerHeight;
        var scale = Math.min(sw / GAME_W, sh / GAME_H);
        var offsetX = (sw - GAME_W * scale) / 2;
        var offsetY = (sh - GAME_H * scale) / 2;
        var b = document.body;
        b.style.width = GAME_W + "px";
        b.style.height = GAME_H + "px";
        b.style.overflow = "hidden";
        b.style.margin = "0";
        b.style.padding = "0";
        b.style.position = "fixed";
        b.style.left = offsetX + "px";
        b.style.top = offsetY + "px";
        b.style.transformOrigin = "top left";
        b.style.transform = "scale(" + scale + ")";
        b.style.background = "#000";
        var html = document.documentElement;
        html.style.width = "100%";
        html.style.height = "100%";
        html.style.overflow = "hidden";
        html.style.margin = "0";
        html.style.background = "#000";
    }

    function detectMobile() {
        var isTouch = "ontouchstart" in window || navigator.maxTouchPoints > 0;
        var narrow = window.innerWidth < 920;
        return isTouch && (narrow || /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent));
    }

    function getGameCoords(clientX, clientY) {
        if (!window.EDAll) return { x: clientX, y: clientY };
        var rect = EDAll.getBoundingClientRect();
        if (rect.width === 0) return { x: clientX, y: clientY };
        var sx = GAME_W / rect.width;
        var sy = GAME_H / rect.height;
        return { x: (clientX - rect.left) * sx, y: (clientY - rect.top) * sy };
    }

    function makeMouseEvent(type, x, y) {
        try {
            return new MouseEvent(type, { clientX: x, clientY: y, bubbles: true, cancelable: true, view: window });
        } catch (e) {
            var evt = document.createEvent("MouseEvents");
            evt.initMouseEvent(type, true, true, window, 1, x, y, x, y, false, false, false, false, 0, null);
            return evt;
        }
    }

    function initTouchHandlers() {
        var startTarget = null;
        var startX = 0, startY = 0, moved = false;

        document.addEventListener("touchstart", function (e) {
            if (e.touches.length > 1) { moved = true; return; }
            var t = e.touches[0];
            var c = getGameCoords(t.clientX, t.clientY);
            startX = t.clientX; startY = t.clientY; moved = false;
            startTarget = document.elementFromPoint(t.clientX, t.clientY);
            if (startTarget) {
                var evt = makeMouseEvent("mousedown", c.x, c.y);
                startTarget.dispatchEvent(evt);
            }
            e.preventDefault();
        }, { passive: false });

        document.addEventListener("touchmove", function (e) {
            if (e.touches.length > 1) { moved = true; return; }
            var t = e.touches[0];
            var c = getGameCoords(t.clientX, t.clientY);
            if (Math.abs(t.clientX - startX) > 10 || Math.abs(t.clientY - startY) > 10) moved = true;
            if (window.EDAll) {
                EDAll.dispatchEvent(makeMouseEvent("mousemove", c.x, c.y));
            }
            e.preventDefault();
        }, { passive: false });

        document.addEventListener("touchend", function (e) {
            var t = e.changedTouches[0];
            var c = getGameCoords(t.clientX, t.clientY);
            if (startTarget) {
                startTarget.dispatchEvent(makeMouseEvent("mouseup", c.x, c.y));
                if (!moved) {
                    var clickTarget = document.elementFromPoint(t.clientX, t.clientY);
                    if (clickTarget) {
                        clickTarget.dispatchEvent(makeMouseEvent("click", c.x, c.y));
                    }
                }
            }
            startTarget = null;
            e.preventDefault();
        }, { passive: false });
    }

    function patchNativeCoords() {
        ["mousedown", "mousemove", "click", "mouseover", "mouseout"].forEach(function (type) {
            document.addEventListener(type, function (e) {
                if (!window.EDAll || e._bld_patched) return;
                var rect = EDAll.getBoundingClientRect();
                if (rect.width === 0) return;
                var sx = GAME_W / rect.width, sy = GAME_H / rect.height;
                var gx = (e.clientX - rect.left) * sx;
                var gy = (e.clientY - rect.top) * sy;
                try {
                    Object.defineProperty(e, "clientX", { value: gx, writable: false, configurable: true });
                    Object.defineProperty(e, "clientY", { value: gy, writable: false, configurable: true });
                    e._bld_patched = true;
                } catch (err) {}
            }, true);
        });
    }

    function debounceSave() {
        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = setTimeout(doSave, 1500);
    }

    async function doSave() {
        saveTimer = null;
        if (!hasKV()) return;
        try {
            var prog = clampProgress($User.Visitor && $User.Visitor.Progress);
            saveData.progress = prog;
            saveData.lastLvl = (window.oS && oS.Lvl) || saveData.lastLvl || 0;
            if (typeof saveData.lastLvl === "string") {
                var parsed = parseInt(saveData.lastLvl, 10);
                saveData.lastLvl = (isNaN(parsed) || parsed < 1 || parsed > MAX_ADV_LEVEL) ? 0 : parsed;
            }
            await Builda.privateKV.set(SAVE_KEY, new TextEncoder().encode(JSON.stringify(saveData)));
        } catch (e) {}
    }

    async function loadSave() {
        if (!hasKV()) return;
        try {
            var result = await Builda.privateKV.get(SAVE_KEY);
            if (result.ok && result.data && result.data.length) {
                var text = new TextDecoder().decode(result.data);
                var loaded = JSON.parse(text);
                if (loaded && loaded.version === 1) {
                    saveData = loaded;
                    saveData.progress = clampProgress(saveData.progress);
                    if ($User.Visitor) {
                        $User.Visitor.Progress = clampProgress($User.Visitor.Progress);
                    }
                }
            }
        } catch (e) {}
    }

    function fallbackHash(str) {
        var h = 5381;
        for (var i = 0; i < str.length; i++) {
            h = ((h * 33) ^ str.charCodeAt(i)) >>> 0;
        }
        var hex = h.toString(16);
        while (hex.length < 8) hex = "0" + hex;
        return hex;
    }

    async function makeOrderKey(orderId) {
        try {
            if (window.crypto && crypto.subtle) {
                var enc = new TextEncoder();
                var buf = await crypto.subtle.digest("SHA-256", enc.encode(orderId));
                var hex = Array.from(new Uint8Array(buf)).map(function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
                return "pay_order_" + hex.substring(0, 48);
            }
            return "pay_order_" + fallbackHash(orderId);
        } catch (e) {
            try {
                return "pay_order_" + fallbackHash(orderId);
            } catch (e2) {
                return null;
            }
        }
    }

    async function buySun(payId) {
        if (!hasIAP()) { alert("请在创游世界App中购买"); return; }
        var pp = PAY_POINTS[payId];
        if (!pp) return;
        try {
            var result = await Builda.iap.showPayPanel(payId, { grantBy: "client" });
            if (!result.ok || !(result.data && result.data.success)) return;
            var orderId = result.data.orderId;
            var grantBy = result.data.grantBy || "client";
            if (grantBy !== "client") return;
            var orderKey = await makeOrderKey(orderId);
            if (!orderKey) return;
            var existing = await Builda.privateKV.get(orderKey);
            if (existing.ok && existing.data && existing.data.length) {
                await Builda.iap.claim(orderId);
                return;
            }
            saveData.bankSun = (saveData.bankSun || 0) + pp.sun;
            await Builda.privateKV.set(orderKey, new TextEncoder().encode(JSON.stringify({ payId: payId, granted: 1 })));
            await doSave();
            await Builda.iap.claim(orderId);
            refreshShopBank();
            alert("购买成功！获得" + pp.sun + "阳光，已存入阳光银行");
        } catch (e) {
            alert("购买失败，请重试");
        }
    }

    async function submitLevelScore(lvl) {
        if (!hasRank()) return;
        var score = parseInt(lvl);
        if (isNaN(score) || score <= 0 || score > MAX_ADV_LEVEL) return;
        try {
            await Builda.rank.submitScore(RANK_ID, score);
        } catch (e) {}
    }

    async function loadLeaderboard() {
        if (!hasRank()) { rankList = []; selfRank = null; return; }
        try {
            var result = await Builda.rank.getRankList(RANK_ID, { limit: 20 });
            if (result.ok && result.data) {
                rankList = result.data.list || [];
                selfRank = result.data.self || null;
            }
        } catch (e) {}
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function refreshShopBank() {
        var el = document.getElementById("bld-bank-sun");
        if (el) el.textContent = String(saveData.bankSun || 0);
    }

    function showShop() {
        var panel = document.getElementById("bld-shop");
        if (!panel) return;
        refreshShopBank();
        panel.style.display = "block";
    }
    function hideShop() {
        var panel = document.getElementById("bld-shop");
        if (panel) panel.style.display = "none";
    }

    function showLeaderboard() {
        var panel = document.getElementById("bld-rank");
        if (panel) panel.style.display = "block";
        renderLeaderboard();
        loadLeaderboard().then(renderLeaderboard);
    }
    function hideLeaderboard() {
        var panel = document.getElementById("bld-rank");
        if (panel) panel.style.display = "none";
    }

    function renderLeaderboard() {
        var listEl = document.getElementById("bld-rank-list");
        var selfEl = document.getElementById("bld-rank-self");
        if (!listEl) return;
        if (rankList.length === 0) {
            listEl.innerHTML = '<div style="padding:20px;text-align:center;color:#999">暂无排行数据</div>';
        } else {
            var html = "";
            for (var i = 0; i < rankList.length; i++) {
                var item = rankList[i];
                var player = item.player || {};
                var name = player.name || item.userName || item.name || "玩家";
                var score = item.score || 0;
                html += '<div class="bld-rank-item">' +
                    '<span class="bld-rank-num">' + (i + 1) + "</span>" +
                    '<span class="bld-rank-name">' + escapeHtml(name) + "</span>" +
                    '<span class="bld-rank-score">第' + score + "关</span>" +
                    "</div>";
            }
            listEl.innerHTML = html;
        }
        if (selfEl && selfRank) {
            selfEl.textContent = "我的排名：" + (selfRank.rank || "未上榜") + " | 最高：第" + (selfRank.score || 0) + "关";
        } else if (selfEl) {
            selfEl.textContent = "暂未上榜，通关即可上榜";
        }
    }

    function addBankSun() {
        if (typeof oS === "undefined" || !oS.Lvl) { alert("请在游戏中使用"); return; }
        if ((saveData.bankSun || 0) < 25) { alert("阳光银行余额不足！"); showShop(); return; }
        var add = Math.min(saveData.bankSun, 25);
        saveData.bankSun -= add;
        oS.SunNum += add;
        if (typeof ESSunNum !== "undefined" && ESSunNum) innerText(ESSunNum, oS.SunNum);
        if (typeof MonitorCard === "function") MonitorCard();
        debounceSave();
        refreshShopBank();
    }

    function hookLoadReady() {
        if (typeof oS === "undefined" || !oS.LoadReady) return;
        if (oS.LoadReady.__bldWrapped) return;
        var orig = oS.LoadReady;
        oS.LoadReady = function (f) {
            try {
                if (saveData.bankSun > 0 && f && typeof f.SunNum === "number") {
                    f.SunNum += saveData.bankSun;
                }
            } catch (e) {}
            return orig.call(this, f);
        };
        oS.LoadReady.__bldWrapped = true;
    }

    function toggleAddSun(lvl) {
        var el = document.getElementById("bld-addsun");
        if (el) el.style.display = (lvl && String(lvl) !== "0") ? "block" : "none";
    }

    function resolveDev() {
        var forcedDev = /(?:[?&])blddev=1\b/.test(location.search);
        if (!hasBuilda()) {
            isDev = forcedDev;
            var btn0 = document.getElementById("bld-dev-btn");
            if (btn0) btn0.style.display = isDev ? "block" : "none";
            buildDevLvlOptions();
            return;
        }
        Builda.whoami({ timeoutMs: 5000 }).then(function (result) {
            try {
                if (result.ok && result.data && String(result.data.id) === DEV_ROLE_ID) {
                    isDev = true;
                }
            } catch (e) {}
            isDev = isDev || forcedDev;
            var btn = document.getElementById("bld-dev-btn");
            if (btn) btn.style.display = isDev ? "block" : "none";
            buildDevLvlOptions();
        }).catch(function () {
            isDev = isDev || forcedDev;
            var btn = document.getElementById("bld-dev-btn");
            if (btn) btn.style.display = isDev ? "block" : "none";
            buildDevLvlOptions();
        });
    }

    function setDevSw(id, on) {
        var el = document.getElementById(id);
        if (el) {
            el.classList.toggle("on", !!on);
            el.textContent = el.getAttribute("data-label") || el.textContent;
            el.textContent = el.textContent.replace(/(：|:).*$/, "") + "：" + (on ? "开" : "关");
        }
    }

    function toggleDev() {
        var panel = document.getElementById("bld-dev");
        if (!panel) return;
        panel.style.display = panel.style.display === "none" ? "block" : "none";
    }
    function hideDev() {
        var panel = document.getElementById("bld-dev");
        if (panel) panel.style.display = "none";
    }

    function devAddSun(n) {
        if (typeof oS === "undefined" || !oS.Lvl) { alert("请在游戏中使用"); return; }
        oS.SunNum += n;
        if (typeof ESSunNum !== "undefined" && ESSunNum) innerText(ESSunNum, oS.SunNum);
        if (typeof MonitorCard === "function") MonitorCard();
    }

    function devToggleInfinite() {
        var on = !devInfiniteTimer;
        if (on) {
            devInfiniteTimer = setInterval(function () {
                if (typeof oS === "undefined") return;
                oS.SunNum = 99999;
                if (typeof ESSunNum !== "undefined" && ESSunNum) innerText(ESSunNum, oS.SunNum);
                if (typeof MonitorCard === "function") MonitorCard();
            }, 200);
        } else {
            clearInterval(devInfiniteTimer);
            devInfiniteTimer = null;
        }
        setDevSw("bld-dev-inf", on);
    }

    function devToggleNoCooldown() {
        var on = !devNoCdTimer;
        if (on) {
            devNoCdTimer = setInterval(function () {
                if (typeof ArCard === "undefined" || typeof ImmediatelyCool !== "function") return;
                if (ArCard.length) ImmediatelyCool();
            }, 250);
        } else {
            clearInterval(devNoCdTimer);
            devNoCdTimer = null;
        }
        setDevSw("bld-dev-cd", on);
    }

    function buildDevLvlOptions() {
        var sel = document.getElementById("bld-dev-lvl");
        if (!sel || sel.options.length) return;
        var html = '<optgroup label="冒险模式">';
        for (var i = 1; i <= MAX_ADV_LEVEL; i++) {
            html += '<option value="' + i + '">第' + i + '关</option>';
        }
        html += '</optgroup><optgroup label="中国馆">';
        var china = [
            [100, "初入中国"], [101, "暗杀行动"], [102, "夜幕降临"], [103, "突出重围"],
            [104, "古老水寨"], [105, "水上运动"], [106, "坟墓村庄"], [107, "幽灵喧夜"],
            [108, "火山之脚"], [109, "火上浇油"], [110, "魔王宫殿"], [111, "尸群围剿"],
            [112, "决战秦皇"], ["FB", "副本-关口恶战"], ["WJY", "副本-江轶同学会晤"]
        ];
        for (var j = 0; j < china.length; j++) {
            html += '<option value="' + china[j][0] + '">' + china[j][1] + '</option>';
        }
        html += '</optgroup>';
        sel.innerHTML = html;
    }

    function devJumpLevel() {
        var input = document.getElementById("bld-dev-lvl");
        var v = input && input.value;
        if (!v || typeof SelectModal !== "function") { alert("请选择关卡"); return; }
        hideDev();
        try {
            if (typeof oS !== "undefined" && oS.Lvl && typeof ResetGame === "function") {
                try { ResetGame($("dMenu0")); } catch (e) {}
            }
            SelectModal(v);
        } catch (err) {
            alert("跳关失败：" + (err && err.message ? err.message : err));
        }
    }

    function devSetSpeed(n) {
        if (typeof oSym === "undefined" || typeof $User === "undefined") return;
        var m = SPEED_MAP[n] || [1, 10];
        oSym.NowStep = m[0];
        oSym.TimeStep = m[1];
        if ($User.Visitor) {
            $User.Visitor.NowStep = m[0];
            $User.Visitor.TimeStep = m[1];
        }
        var els = document.querySelectorAll(".bld-dev-mult");
        for (var i = 0; i < els.length; i++) {
            els[i].classList.toggle("on", String(els[i].getAttribute("data-speed")) === String(n));
        }
    }

    window.BuildaBridge = {
        onInit: function () {
            mobileActive = detectMobile();
            if (mobileActive) {
                applyScale();
                initTouchHandlers();
                window.addEventListener("resize", applyScale);
                window.addEventListener("orientationchange", function () { setTimeout(applyScale, 300); });
                try { EDAlloffsetLeft = 0; } catch (e) {}
            } else {
                patchNativeCoords();
            }
            loadSave();
            hookLoadReady();
            if ($User && $User.Visitor) {
                $User.Visitor.Progress = clampProgress($User.Visitor.Progress);
            }
            resolveDev();
        },
        onLevelClear: function (lvl) {
            var n = parseInt(lvl);
            if (isNaN(n) || n <= 0 || n > MAX_ADV_LEVEL) return;
            if (n >= (saveData.progress || 1)) {
                saveData.progress = n + 1;
                if ($User.Visitor) $User.Visitor.Progress = clampProgress(n + 1);
            }
            submitLevelScore(n);
            debounceSave();
        },
        onGameOver: function () { debounceSave(); },
        onSelectModal: function (lvl) {
            toggleAddSun(lvl);
            debounceSave();
        },
        getBankSun: function () { return saveData.bankSun || 0; },
        buySun: buySun,
        showShop: showShop,
        hideShop: hideShop,
        showLeaderboard: showLeaderboard,
        hideLeaderboard: hideLeaderboard,
        addBankSun: addBankSun,
        toggleDev: toggleDev,
        hideDev: hideDev,
        devAddSun: devAddSun,
        devToggleInfinite: devToggleInfinite,
        devToggleNoCooldown: devToggleNoCooldown,
        devJumpLevel: devJumpLevel,
        devSetSpeed: devSetSpeed
    };
})();
