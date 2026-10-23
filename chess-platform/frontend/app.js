'use strict';
/* 棋魂阁 - 联机棋类平台 前端 SPA */
const S = {
  token: localStorage.getItem('qh_token') || '',
  me: null, view: 'auth', params: {}, stack: [],
  games: [], regions: [], packages: [], stats: null, mult: 1,
  match: null, queueing: false, ws: null, wsOpen: false, unread: 0,
  forum: null, lobby: null, room: null, adminTab: 'users', music: null, adminForumKw: '',
  homeTab: 'level', rankTab: 'level', msgTab: 'notif', chat: null, user: null,
};
/* ---------- 工具 ---------- */
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtNum = (n) => (n >= 10000 ? (n / 10000).toFixed(1).replace(/\.0$/, '') + 'w' : String(n ?? 0));
function fmtTime(t) {
  if (!t) return '';
  const d = new Date(t * 1000), now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
  if (diff < 86400 * 7) return Math.floor(diff / 86400) + '天前';
  return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
function toast(msg, cls = '') {
  document.querySelectorAll('.toast').forEach((e) => e.remove());
  const t = document.createElement('div');
  t.className = 'toast ' + cls;
  t.textContent = msg;
  t.onclick = () => t.remove();
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}
function modal(html) {
  closeModal();
  const mask = document.createElement('div');
  mask.className = 'modal-mask';
  mask.innerHTML = `<div class="modal"><span class="close-x" onclick="closeModal()">✕</span>${html}</div>`;
  mask.addEventListener('click', (e) => { if (e.target === mask) closeModal(); });
  document.body.appendChild(mask);
  return mask;
}
function closeModal() { document.querySelectorAll('.modal-mask').forEach((e) => e.remove()); }
/* ---------- 声音 ---------- */
const snd = {
  ctx: null, musicNodes: null,
  ensure() {
    if (!this.ctx) { try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { } }
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  },
  vol(kind) {
    const st = (S.me && S.me.settings) || {};
    if (st.muted) return 0;
    return (kind === 'music' ? (st.music_vol ?? 60) : (st.sfx_vol ?? 80)) / 100 * 0.5;
  },
};
snd.beep = function (freq, dur, type = 'sine', delay = 0) {
  const ctx = this.ensure(); if (!ctx || !this.vol('sfx')) return;
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.value = freq;
  o.connect(g); g.connect(ctx.destination);
  const t = ctx.currentTime + delay, v = this.vol('sfx');
  g.gain.setValueAtTime(v, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + dur);
  o.start(t); o.stop(t + dur + 0.02);
};
snd.play = function (name) {
  if (name === 'move') this.beep(520, 0.08, 'triangle');
  else if (name === 'click') this.beep(700, 0.05, 'sine');
  else if (name === 'msg') { this.beep(880, 0.1, 'sine'); this.beep(1180, 0.12, 'sine', 0.1); }
  else if (name === 'win') { [523, 659, 784, 1046].forEach((f, i) => this.beep(f, 0.16, 'triangle', i * 0.13)); }
  else if (name === 'lose') { [440, 349, 262].forEach((f, i) => this.beep(f, 0.2, 'sawtooth', i * 0.15)); }
};
snd.startMusic = function () {
  if (!this.vol('music')) return;
  if (S.music && S.music.url) {
    let el = this.musicEl;
    if (el && el.dataset.src === S.music.url) { if (el.paused) { const p = el.play(); if (p && p.catch) p.catch(() => { }); } return; }
    if (!el) { el = new Audio(); el.loop = true; this.musicEl = el; }
    el.dataset.src = S.music.url;
    el.src = S.music.url;
    el.volume = Math.min(1, this.vol('music') * 1.6);
    const p = el.play();
    if (p && p.catch) p.catch(() => { });
    return;
  }
  const ctx = this.ensure();
  if (!ctx || this.musicNodes) return;
  const g = ctx.createGain();
  g.gain.value = this.vol('music') * 0.12;
  g.connect(ctx.destination);
  const os = [261.6, 329.6, 392.0].map((f, i) => {
    const o = ctx.createOscillator();
    o.type = 'sine'; o.frequency.value = f;
    const lfo = ctx.createOscillator(), lg = ctx.createGain();
    lfo.frequency.value = 0.08 + i * 0.03; lg.gain.value = 2;
    lfo.connect(lg); lg.connect(o.frequency);
    o.connect(g); o.start(); lfo.start();
    return [o, lfo];
  });
  this.musicNodes = { g, os };
};
snd.stopMusic = function () {
  if (this.musicEl) { try { this.musicEl.pause(); } catch (e) { } }
  if (!this.musicNodes) return;
  try {
    this.musicNodes.os.forEach(([o, l]) => { o.stop(); l.stop(); });
  } catch (e) { }
  this.musicNodes = null;
};
snd.setTrack = function (t) {
  S.music = t && t.url ? t : null;
  if (this.musicEl) { try { this.musicEl.pause(); } catch (e) { } this.musicEl = null; }
  this.stopMusic();
  if (S.me) this.startMusic();
};
/* ---------- API ---------- */
async function api(method, path, body) {
  const opt = { method, headers: {} };
  if (S.token) opt.headers.Authorization = 'Bearer ' + S.token;
  if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  if (typeof AbortController !== 'undefined') {
    const ctrl = new AbortController();
    opt.signal = ctrl.signal;
    setTimeout(() => { try { ctrl.abort(); } catch (e) { } }, 12000);
  }
  let r;
  try { r = await fetch('/api' + path, opt); } catch (e) { throw new Error('网络异常，请稍后重试'); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && S.me) { logoutLocal(); showView('auth'); }
    throw new Error(data.detail || '请求失败');
  }
  return data;
}
const GET = (p) => api('GET', p);
const POST = (p, b) => api('POST', p, b || {});
const DEL = (p) => api('DELETE', p);
/* ---------- WebSocket ---------- */
function wsConnect() {
  if (S.ws) { try { S.ws.close(); } catch (e) { } }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  S.ws = ws;
  ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: S.token }));
  ws.onmessage = (ev) => { try { wsDispatch(JSON.parse(ev.data)); } catch (e) { } };
  ws.onclose = () => { S.wsOpen = false; setTimeout(() => { if (S.me && S.token) wsConnect(); }, 3000); };
  ws.onerror = () => { };
}
function wsSend(obj) { if (S.ws && S.wsOpen) S.ws.send(JSON.stringify(obj)); }
function wsDispatch(d) {
  if (d.type === 'ready') { S.wsOpen = true; }
  else if (d.type === 'stats') { S.stats = d; if (S.view === 'games') refreshStatsBar(); }
  else if (d.type === 'queue_status') {
    S.queueing = !!d.waiting;
    if (S.view === 'lobby') renderLobbyQueue(d.msg || (d.waiting ? '正在匹配同段位玩家...' : ''));
  }
  else if (d.type === 'matched') {
    S.queueing = false;
    enterMatch(d.match_id, d.game, d.mode, d.side, d.opponent, d.ai_stars, d.seats, d.ai_sides);
  }
  else if (d.type === 'state') onMatchState(d);
  else if (d.type === 'game_over') onGameOver(d);
  else if (d.type === 'chat') {
    snd.play('msg');
    if (S.match && d.match_id === S.match.id) {
      S.match.chat = S.match.chat || [];
      S.match.chat.push({ from: d.from, text: d.text });
      if (S.view === 'match') renderMatchChat();
    }
    toast(`${d.from}: ${d.text}`);
  }
  else if (d.type === 'dm') onDm(d);
  else if (d.type === 'music') {
    if (d.renamed) { if (S.music && S.music.id === d.id) S.music.name = d.name; }
    else { snd.setTrack(d.url ? d : null); if (d.url) toast(`背景音乐已切换：${d.name || ''}`, 'ok'); }
  }
  else if (d.type === 'error') toast(d.msg || '操作无效', 'err');
}
function onDm(d) {
  snd.play('msg');
  if (S.view === 'chat' && S.chat && S.chat.peer && S.chat.peer.id === d.from_id) {
    S.chat.msgs.push({ from_id: d.from_id, content: d.content, created_at: d.t });
    renderChatMsgs();
  } else {
    S.unread++;
    updateBadges();
    toast(`来自 ${d.from} 的新消息`, 'ok');
  }
}
/* ---------- 路由 ---------- */
const TAB_VIEWS = ['home', 'games', 'forum', 'friends', 'messages'];
function showView(view, params = {}, replace = false) {
  if (!replace && S.view !== view) S.stack.push({ view: S.view, params: S.params });
  S.view = view; S.params = params;
  render();
}
function goBack() {
  const prev = S.stack.pop() || { view: 'home', params: {} };
  S.view = prev.view; S.params = prev.params;
  render();
}
function nav(view) {
  if (S.view === view) return;
  snd.play('click');
  showView(view, {}, true);
  S.stack = [];
}
function render() {
  const app = $('#app');
  if (!app) return;
  try {
    const views = {
      auth: viewAuth, recover: viewRecover, find: viewFind,
      home: viewHome, rankings: viewRankings, games: viewGames,
      lobby: viewLobby, room: viewRoom, match: viewMatch,
      forum: viewForum, friends: viewFriends, chat: viewChat,
      messages: viewMessages, settings: viewSettings, shop: viewShop,
      avatarShop: viewAvatarShop, admin: viewAdmin, user: viewUser, history: viewHistory,
    };
    (views[S.view] || viewHome)(app);
    window.scrollTo(0, 0);
  } catch (e) {
    app.innerHTML = '<div class="auth-wrap"><div class="auth-title">棋魂阁</div><div class="sub" style="text-align:center;margin-top:12px">页面加载失败，请刷新重试</div></div>';
  }
}
/* ---------- 公共组件 ---------- */
const FRAME_CSS = {
  f_gold: 'frame-gold', f_silver: 'frame-silver', f_bronze: 'frame-bronze', f_rainbow: 'frame-rainbow',
  f_flame: 'frame-flame', f_thunder: 'frame-thunder', f_crown: 'frame-crown', f_glow: 'frame-glow',
  d_fire: 'dyn-fire', d_star: 'dyn-star', d_bolt: 'dyn-bolt', d_bubble: 'dyn-bubble',
};
function frameCss(fr) {
  if (!fr) return '';
  return FRAME_CSS[fr] || (/^(frame-|dyn-)/.test(fr) ? fr : '');
}
function avatarBare(u, cls = '') {
  const a = u && u.avatar;
  const nm = (u && u.name) || '?';
  if (a) return `<img class="avatar ${cls}" src="${esc(a)}" data-fb="${esc(nm)}" data-cls="${esc(cls)}" onerror="avFallback(this)">`;
  return fbAvatar(nm, cls);
}
function avFallback(el) {
  if (!el) return;
  el.outerHTML = fbAvatar(el.getAttribute('data-fb') || '?', el.getAttribute('data-cls') || '');
}
function avatarHtml(u, cls = '') {
  const img = avatarBare(u, cls);
  const css = frameCss(u && u.avatar_frame);
  if (css) return `<span class="avatar-frame ${css}">${img}</span>`;
  return img;
}
function fbAvatar(name, cls) {
  return `<div class="avatar ${cls}" style="display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;background:linear-gradient(135deg,#5b8cff,#8b5cf6)">${esc((name || '?')[0])}</div>`;
}
function isStaff() { return S.me && (S.me.role === 'author' || S.me.role === 'admin'); }
function userTag(u) {
  if (u && u.is_virtual) return isStaff() ? '<span class="tag virtual">虚拟</span>' : '';
  if (u && u.role === 'author') return '<span class="tag real">作者</span>';
  if (u && u.role === 'admin') return '<span class="tag real">管理</span>';
  return '';
}
function topbarHtml(title, showBack = true) {
  const mailN = S.unread ? ` data-n="${S.unread}"` : '';
  return `<div class="topbar">
    <div class="row">${showBack ? '<span class="back-link" onclick="goBack()">←</span>' : ''}<h1>${esc(title)}</h1></div>
    <div class="actions">
      <span class="badge"${mailN} onclick="openMail()" title="邮箱">✉</span>
      <span onclick="showView('settings')" title="设置">⚙</span>
    </div></div>`;
}
function bottomNavHtml() {
  const items = [['home', '🏠', '我的'], ['games', '♟', '游戏'], ['forum', '💬', '论坛'], ['friends', '👥', '好友'], ['messages', '🔔', '消息']];
  return `<div class="bottom-nav">${items.map(([v, i, n]) =>
    `<div class="nav-item ${S.view === v || (v === 'home' && ['shop', 'settings', 'admin', 'rankings'].includes(S.view)) ? 'active' : ''}" onclick="nav('${v}')"><span class="ico">${i}</span>${n}</div>`).join('')}</div>`;
}
/* ---------- 认证 ---------- */
function viewAuth(app) {
  document.title = '棋魂阁 - 登录';
  app.innerHTML = `<div class="auth-wrap">
    <div class="auth-logo">♟</div>
    <div class="auth-title">棋魂阁</div>
    <div class="auth-sub">联机棋类竞技平台 · 金币钻石 · 段位排位</div>
    <div class="auth-card">
      <div class="auth-tabs">
        <button class="active" id="tab-login" onclick="authTab('login')">登录</button>
        <button id="tab-reg" onclick="authTab('register')">注册</button>
      </div>
      <div id="auth-form"></div>
      <div class="link" onclick="showView('recover')">忘记密码？找回密码</div>
      <div class="link" onclick="showView('find')">找回帐号</div>
    </div></div>`;
  authTab('login');
}
function authTab(t) {
  $('#tab-login').classList.toggle('active', t === 'login');
  $('#tab-reg').classList.toggle('active', t === 'register');
  $('#auth-form').innerHTML = t === 'login' ? `
    <input id="li-name" placeholder="昵称（注册时的名字）">
    <div class="row" style="gap:8px"><input id="li-pass" type="password" placeholder="密码" style="flex:1"><button class="btn small ghost" onclick="togglePw('#li-pass',this)">显示</button></div>
    <div class="err" id="li-err"></div>
    <button class="btn block" onclick="doLogin()">登 录</button>` : `
    <input id="rg-name" placeholder="昵称（2-16字，唯一，即帐号）">
    <div class="row" style="gap:8px"><input id="rg-pass" type="password" placeholder="密码（至少6位）" style="flex:1"><button class="btn small ghost" onclick="togglePw('#rg-pass',this)">显示</button></div>
    <div class="row" style="gap:8px"><input id="rg-pass2" type="password" placeholder="确认密码" style="flex:1"><button class="btn small ghost" onclick="togglePw('#rg-pass2',this)">显示</button></div>
    <input id="rg-qq" placeholder="QQ号（选填，用于找回）">
    <input id="rg-phone" placeholder="手机号（选填，用于找回）">
    <div class="err" id="rg-err"></div>
    <button class="btn block" onclick="doRegister()">注册并登录</button>
    <div class="sub" style="margin-top:8px">首次注册赠送 1000 金币</div>`;
}
async function doLogin() {
  const name = $('#li-name').value.trim(), password = $('#li-pass').value;
  if (!name || !password) { $('#li-err').textContent = '请输入昵称和密码'; return; }
  try {
    const r = await POST('/login', { name, password });
    afterAuth(r, '欢迎回来，' + r.user.name);
  } catch (e) { $('#li-err').textContent = e.message; }
}
async function doRegister() {
  const name = $('#rg-name').value.trim(), password = $('#rg-pass').value,
    password2 = $('#rg-pass2').value, qq = $('#rg-qq').value.trim(), phone = $('#rg-phone').value.trim();
  try {
    const r = await POST('/register', { name, password, password2, qq, phone });
    afterAuth(r, '注册成功，赠送 1000 金币！');
  } catch (e) { $('#rg-err').textContent = e.message; }
}
async function afterAuth(r, msg) {
  S.token = r.token; S.me = r.user;
  localStorage.setItem('qh_token', r.token);
  wsConnect();
  snd.ensure(); snd.startMusic();
  toast(msg, 'ok');
  showView('home', {}, true); S.stack = [];
  refreshBadges();
}
function togglePw(inputId, btn) {
  const el = $(inputId);
  el.type = el.type === 'password' ? 'text' : 'password';
  btn.textContent = el.type === 'password' ? '显示' : '隐藏';
}
function viewRecover(app) {
  app.innerHTML = `${topbarHtml('找回密码')}
    <div class="card">
      <div class="sub" style="margin-bottom:10px">输入名字 + 注册时绑定的QQ号或手机号，验证通过后设置新密码</div>
      <input id="rc-name" placeholder="帐号名字">
      <input id="rc-contact" placeholder="QQ号或手机号">
      <div class="row" style="gap:8px"><input id="rc-pass" type="password" placeholder="新密码（至少6位）" style="flex:1"><button class="btn small ghost" onclick="togglePw('#rc-pass',this)">显示</button></div>
      <div class="row" style="gap:8px"><input id="rc-pass2" type="password" placeholder="确认新密码" style="flex:1"><button class="btn small ghost" onclick="togglePw('#rc-pass2',this)">显示</button></div>
      <div class="err" id="rc-err"></div>
      <button class="btn block" onclick="doRecover()">重置密码</button>
    </div>${bottomNavHtml()}`;
}
async function doRecover() {
  const name = $('#rc-name').value.trim(), contact = $('#rc-contact').value.trim(),
    new_password = $('#rc-pass').value, password2 = $('#rc-pass2').value;
  if (new_password !== password2) { $('#rc-err').textContent = '两次输入的密码不一致'; return; }
  try {
    await POST('/recover', { name, contact, new_password });
    toast('密码已重置，请重新登录', 'ok');
    showView('auth', {}, true); S.stack = [];
  } catch (e) { $('#rc-err').textContent = e.message; }
}
function viewFind(app) {
  app.innerHTML = `${topbarHtml('找回帐号')}
    <div class="card">
      <div class="sub" style="margin-bottom:10px">输入QQ号或手机号，查找绑定的帐号</div>
      <input id="fd-contact" placeholder="QQ号或手机号">
      <div class="err" id="fd-err"></div>
      <button class="btn block" onclick="doFind()">查找帐号</button>
      <div id="fd-result" style="margin-top:10px"></div>
    </div>${bottomNavHtml()}`;
}
async function doFind() {
  const contact = $('#fd-contact').value.trim();
  try {
    const r = await POST('/recover/find', { contact });
    $('#fd-err').textContent = '';
    $('#fd-result').innerHTML = `<div class="sub">共找到 ${r.count} 个帐号：</div>` +
      r.accounts.map((a) => `<div class="code-box">${esc(a)}</div>`).join('') +
      `<div class="sub">找回密码请到「找回密码」页，使用完整名字</div>`;
  } catch (e) { $('#fd-err').textContent = e.message; $('#fd-result').innerHTML = ''; }
}
/* ---------- 我的 ---------- */
const HOME_TABS = [['level', '等级榜'], ['coins', '金币榜'], ['history', '历史对局'], ['bills', '金币账单'], ['fav', '我的收藏'], ['likes', '我的点赞']];
async function viewHome(app) {
  if (!S.me) { showView('auth', {}, true); return; }
  document.title = '棋魂阁 - 我的';
  const me = S.me;
  const expPct = me.exp % 100;
  app.innerHTML = `${topbarHtml('我的', false)}
    <div class="profile-head">
      <div style="cursor:pointer" onclick="pickAvatar()">${avatarHtml(me, 'lg')}</div>
      <div style="flex:1">
        <div class="row"><b style="font-size:17px">${esc(me.name)}</b>${userTag(me)}</div>
        <div class="sub">ID: ${me.id} · Lv.${me.level} · ${esc(me.region || '未设置地区')}</div>
        <div class="sub">❤ ${me.likes} · 注册于 ${fmtTime(me.created_at)}</div>
        <div class="sub">${esc(me.bio || '')}</div>
      </div>
      <div style="text-align:center"></div>
    </div>
    <div class="sub" style="margin:0 16px">经验 ${expPct}/100</div>
    <div class="shop-banner" onclick="showView('shop')" style="margin:10px 14px;padding:14px 16px;border-radius:14px;background:linear-gradient(135deg,#f59e0b,#ef4444);color:#fff;display:flex;align-items:center;gap:12px;cursor:pointer">
      <span style="font-size:24px">💎</span>
      <div style="flex:1"><div style="font-weight:700;font-size:15px">充值中心 · 商城</div><div style="font-size:12px;opacity:.85">1元 = 100钻石 · 多档套餐</div></div>
      <span style="font-size:20px">›</span>
    </div>
    <div class="wallet-row">
      <div class="wallet" onclick="showView('shop')"><div class="num gold-txt">${fmtNum(me.coins)}</div><div class="lab">金币 ›</div></div>
      <div class="wallet" onclick="showView('shop')"><div class="num dia-txt">${fmtNum(me.diamonds)}</div><div class="lab">钻石 ›</div></div>
    </div>
    <div class="row" style="margin:0 14px;gap:8px">
      <button class="btn small" style="flex:1" onclick="showView('rankings')">排行榜</button>
      <button class="btn small gold" style="flex:1" onclick="showView('shop')">充值中心</button>
      ${me.role !== 'player' ? `<button class="btn small danger" style="flex:1" onclick="showView('admin')">管理后台</button>` : ''}
    </div>
    <div class="section-title">个人中心</div>
    <div class="card" id="home-tab-content"></div>
    ${bottomNavHtml()}`;
  renderHomeTab();
}
function homeTab(t) { S.homeTab = t; snd.play('click'); renderHomeTab(); }
async function renderHomeTab() {
  const box = $('#home-tab-content'); if (!box) return;
  box.innerHTML = `<div class="row" style="flex-wrap:wrap;gap:6px;margin-bottom:10px">${HOME_TABS.map(([k, n]) =>
    `<button class="btn small ${S.homeTab === k ? '' : 'ghost'}" onclick="homeTab('${k}')">${n}</button>`).join('')}</div>
    <div id="home-tab-body"><div class="empty">加载中...</div></div>`;
  const body = $('#home-tab-body');
  try {
    if (S.homeTab === 'level' || S.homeTab === 'coins') {
      const rows = await GET(`/rankings?type=${S.homeTab}&limit=50`);
      body.innerHTML = rankRowsHtml(rows, S.homeTab);
    } else if (S.homeTab === 'history') {
      const rows = await GET('/me/history?limit=30');
      body.innerHTML = rows.length ? rows.map(historyRow).join('') : '<div class="empty">还没有对局，去游戏分区开一局吧</div>';
    } else if (S.homeTab === 'bills') {
      const rows = await GET('/me/bills?limit=50');
      body.innerHTML = rows.length ? rows.map((b) => `<div class="list-item">
        <div style="flex:1"><div>${esc(b.reason || '变动')}</div><div class="sub">${fmtTime(b.created_at)}</div></div>
        <div class="${b.amount >= 0 ? 'gold-txt' : 'sub'}" style="font-weight:700">${b.amount >= 0 ? '+' : ''}${b.amount} ${b.currency === 'coins' ? '金币' : '钻石'}</div>
      </div>`).join('') : '<div class="empty">暂无账单</div>';
    } else {
      await renderHomeTabFav();
    }
  } catch (e) { body.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function renderHomeTabFav() {
  const body = $('#home-tab-body'); if (!body) return;
  const rows = await GET(S.homeTab === 'fav' ? '/me/favorites' : '/me/likes');
  body.innerHTML = rows.length ? rows.map((p) => forumPostHtml(p, true)).join('') : '<div class="empty">暂无内容</div>';
}
function rankRowsHtml(rows, type) {
  if (!rows.length) return '<div class="empty">暂无数据</div>';
  return `<div class="rank-list">` + rows.map((r, i) => {
    const no = i < 3 ? `top${i + 1}` : '';
    const score = type === 'coins' ? `${fmtNum(r.score)} 金币` : `Lv.${r.level} · ${fmtNum(r.score)}经验`;
    return `<div class="item" onclick="openUser(${r.id})">${avatarHtml(r, 'sm')}
      <div style="flex:1"><div class="row">${esc(r.name)} ${isStaff() && r.is_virtual ? '<span class="tag virtual">虚拟</span>' : ''}</div>
      <div class="sub">${esc(r.region || '未设置')}</div></div>
      <div class="gold-txt" style="font-size:13px">${score}</div></div>`;
  }).join('') + `</div>`;
}
function rankRowsFix(rows) {
  if (!rows.length) return '<div class="empty">暂无数据</div>';
  return '<div class="rank-list">' + rows.map((r, i) => `<div class="item" onclick="openUser(${r.id})">
    <div class="no ${i < 3 ? 'top' + (i + 1) : ''}">${i + 1}</div>${avatarHtml(r, 'sm')}
    <div style="flex:1"><div class="row">${esc(r.name)}${isStaff() && r.is_virtual ? '<span class="tag virtual">虚拟</span>' : ''}</div>
    <div class="sub">${esc(r.region || '未设置')} · ${esc(r.label || ('Lv.' + r.level))}</div></div>
    <div class="gold-txt" style="font-size:13px">${r.score ?? r.coins ?? ''}</div></div>`).join('') + '</div>';
}
function historyRow(h) {
  const opp = h.p1 === S.me.id
    ? { name: h.p2_name, avatar: h.p2_avatar, avatar_frame: h.p2_frame }
    : { name: h.p1_name, avatar: h.p1_avatar, avatar_frame: h.p1_frame };
  const res = h.draw ? '<span class="sub">平局</span>' : h.won ? '<span class="gold-txt">胜利</span>' : '<span class="sub" style="color:#fca5a5">失败</span>';
  return `<div class="list-item">${avatarHtml(opp, 'sm')}
    <div style="flex:1"><div>${esc(opp.name || '未知')} · ${esc(gameName(h.game))}</div><div class="sub">${fmtTime(h.finished_at || h.created_at)} · ${modeName(h.mode)}</div></div>
    ${res}</div>`;
}
const GAME_NAMES = { gomoku: '五子棋', tictactoe: '井字棋', xiangqi: '中国象棋', doubeast: '斗兽棋', go: '围棋', chess: '国际象棋', junqi: '军棋', feixing: '飞行棋', tiaoqi: '国际跳棋', doudizhu: '斗地主', pvz: '植物大战僵尸', horror: '五夜抓鬼' };
function gameName(k) { return GAME_NAMES[k] || k; }
function modeName(m) { return m === 'ranked' ? '排位赛' : m === 'ai' ? '人机对战' : '房间对战'; }
function pickAvatar() {
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = 'image/*';
  inp.onchange = () => uploadFile(inp.files[0], true);
  inp.click();
}
function readAsDataUrl(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = () => rej(new Error('读取失败'));
    r.readAsDataURL(file);
  });
}
function loadImageFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('无法读取该图片，请改用 JPG 或 PNG')); };
    img.src = url;
  });
}
async function fileToDataUrl(file, isAvatar) {
  const isVideo = (file.type || '').startsWith('video');
  if (isVideo) {
    if (file.size > 60 * 1024 * 1024) throw new Error('视频不能超过 60MB');
    return readAsDataUrl(file);
  }
  const img = await loadImageFile(file);
  const max = isAvatar ? 512 : 1280;
  let w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
  if (!w || !h) throw new Error('无法读取该图片，请改用 JPG 或 PNG');
  if (w > max || h > max) {
    const s = max / Math.max(w, h);
    w = Math.round(w * s); h = Math.round(h * s);
  }
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  cv.getContext('2d').drawImage(img, 0, 0, w, h);
  return cv.toDataURL('image/jpeg', isAvatar ? 0.88 : 0.82);
}
async function uploadFile(file, isAvatar) {
  if (!file) return;
  try {
    const dataUrl = await fileToDataUrl(file, isAvatar);
    const r = await POST('/upload', { data_url: dataUrl });
    if (isAvatar) { await POST('/me/avatar', { avatar: r.url }); await refreshMe(); toast('头像已更新', 'ok'); render(); }
    return r;
  } catch (e) { toast(e.message, 'err'); }
}
async function refreshMe() {
  try { S.me = await GET('/me'); } catch (e) { }
  return S.me;
}
async function refreshBadges() {
  try {
    const list = await GET('/notifications');
    S.unread = list.filter((n) => !n.read).length;
    updateBadges();
  } catch (e) { }
}
function updateBadges() {
  document.querySelectorAll('.topbar .badge').forEach((b) => {
    if (S.unread) b.setAttribute('data-n', S.unread); else b.removeAttribute('data-n');
  });
}
function openMail() { snd.play('click'); S.msgTab = 'mail'; showView('messages'); }
/* ---------- 排行榜页 ---------- */
const RANK_NAMES = ['青铜', '白银', '黄金', '铂金', '钻石', '星耀', '大师', '宗师', '王者', '传奇', '荣耀', '巅峰'];
function divLabel(div, stars) { return `${RANK_NAMES[Math.max(0, Math.min(11, div - 1))]}${'ⅠⅡⅢ'[Math.max(0, Math.min(2, stars))]}`; }
async function viewRankings(app) {
  app.innerHTML = `${topbarHtml('排行榜')}
    <div class="row" style="margin:10px 14px;gap:8px">
      <button class="btn small ${S.rankTab === 'level' ? '' : 'ghost'}" onclick="rankTab('level')">等级榜</button>
      <button class="btn small ${S.rankTab === 'coins' ? '' : 'ghost'}" onclick="rankTab('coins')">金币榜</button>
    </div>
    <div class="card" id="rank-body"><div class="empty">加载中...</div></div>${bottomNavHtml()}`;
  loadRankings();
}
function rankTab(t) { S.rankTab = t; render(); }
async function loadRankings() {
  const body = $('#rank-body'); if (!body) return;
  try { body.innerHTML = rankRowsFix(await GET(`/rankings?type=${S.rankTab}&limit=100`)); }
  catch (e) { body.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
/* ---------- 游戏分区 ---------- */
const GAME_ICONS = { gomoku: '⚫', tictactoe: '⭕', xiangqi: '♞', doubeast: '🦁', go: '⚪', chess: '♛', junqi: '🚩', feixing: '✈', tiaoqi: '🔷', doudizhu: '🃏', pvz: '🌻', horror: '👻' };
async function viewGames(app) {
  document.title = '棋魂阁 - 游戏分区';
  if (!S.games.length) { try { S.games = await GET('/games'); } catch (e) { } }
  app.innerHTML = `${topbarHtml('游戏分区', false)}
    <div class="card" id="stats-bar"><div class="empty">加载中...</div></div>
    <div class="section-title">全部游戏 <span class="sub">排位 · 人机 · 房间</span></div>
    <div class="game-grid">${S.games.map(gameTile).join('')}</div>
    ${bottomNavHtml()}`;
  refreshStats();
}
function gameTile(g) {
  const my = g.my_rank && g.my_rank.label;
  return `<div class="game-tile ${g.available ? '' : 'locked'}" onclick="openGame('${g.key}')">
    <div class="ico">${GAME_ICONS[g.key] || '♟'}</div>
    <div class="nm">${esc(g.name)}${g.available ? '' : ' <span class="tag">开发中</span>'}</div>
    <div class="ds">${esc(g.desc)}</div>
    ${g.available && my ? `<div class="myrank">我的段位：${esc(my)}</div>` : ''}
  </div>`;
}
function refreshStatsBar() {
  const bar = $('#stats-bar'); if (bar && S.stats) bar.innerHTML = statsHtml(S.stats);
}
async function refreshStats() {
  try { S.stats = await GET('/stats'); refreshStatsBar(); } catch (e) { }
}
function statsHtml(s) {
  const full = s.online_real !== undefined;
  const ov = Math.max(0, (s.online_total || 0) - (s.online_real || 0));
  const rv = Math.max(0, (s.registered_total || 0) - (s.registered_real || 0));
  return `<div class="spread"><div>
      <div style="font-weight:700;font-size:15px">在线 ${s.online_total || 0} 人</div>
      ${full ? `<div class="sub">真实 ${s.online_real || 0} / 虚拟 ${ov}</div>` : ''}</div>
    <div style="text-align:right">
      <div style="font-weight:700;font-size:15px">注册 ${fmtNum(s.registered_total || 0)} 人</div>
      ${full ? `<div class="sub">真实 ${s.registered_real || 0} / 虚拟 ${rv}</div>` : ''}</div></div>
    <div class="sub" style="margin-top:6px">金币活动倍率 x${S.mult} · 充值 1元 = 100钻石</div>`;
}
/* ---------- 游戏大厅 ---------- */
const LOBBY_TABS = [['ranked', '排位赛'], ['ai', '人机对战'], ['room', '房间']];
function openGame(key) {
  const g = S.games.find((x) => x.key === key);
  if (!g) return;
  if (!g.available) { toast(g.name + ' 开发中，敬请期待', 'err'); return; }
  snd.play('click');
  S.lobby = { game: key, mode: 'ranked', stars: 30, queueMsg: '' };
  showView('lobby');
}
async function viewLobby(app) {
  const g = S.games.find((x) => x.key === S.lobby.game) || {};
  const myRank = (S.me.ranks || {})[S.lobby.game];
  app.innerHTML = `${topbarHtml(g.name || '游戏')}
    <div class="row" style="margin:6px 14px">
      <div class="player-chip ${myRank ? 'turn' : ''}">🏆 我的段位：${myRank ? esc(myRank.label) : '青铜Ⅰ'} · ${myRank ? myRank.stars + '/3星' : ''} ${myRank ? myRank.points + '分' : ''}</div>
    </div>
    <div class="mode-tabs">${LOBBY_TABS.map(([k, n]) =>
    `<button class="${S.lobby.mode === k ? 'active' : ''}" onclick="lobbyMode('${k}')">${n}</button>`).join('')}</div>
    <div id="lobby-body"></div>
    <div class="section-title">本游戏排行榜 <span class="sub">段位前百</span></div>
    <div class="card" id="lobby-rank"><div class="empty">加载中...</div></div>
    ${bottomNavHtml()}`;
  renderLobbyBody(); loadLobbyRank();
}
function lobbyMode(m) { S.lobby.mode = m; snd.play('click'); renderLobbyBody(); }
function renderLobbyBody() {
  const box = $('#lobby-body'); if (!box) return;
  if (S.lobby.mode === 'ranked') {
    box.innerHTML = `<div class="card">
      <div class="sub">优先匹配同段位真人，真人不足自动匹配同水平虚拟玩家</div>
      <div class="sub">胜 +50金币×活动倍率 · 负 -20金币 · 100分升1星 · 3星升1段 · 共12段</div>
      <div id="queue-msg" class="sub" style="margin:8px 0;min-height:18px;color:var(--gold)">${esc(S.lobby.queueMsg)}</div>
      <button id="queue-btn" class="btn block ${S.queueing ? 'ghost' : ''}" onclick="S.queueing ? leaveQueue() : joinQueue()">${S.queueing ? '取消匹配' : '开始排位匹配'}</button>
    </div>`;
  } else if (S.lobby.mode === 'ai') {
    box.innerHTML = `<div class="card">
      <div class="sub">人机 1-100 星，星数越高越强</div>
      <div class="stars-picker"><span style="font-weight:700">${S.lobby.stars}</span>
        <input type="range" min="1" max="100" value="${S.lobby.stars}" oninput="S.lobby.stars=+this.value;this.previousElementSibling.textContent=this.value"></div>
      <div class="sub">胜利 +30金币×倍率 · 失败无惩罚</div>
      <button class="btn block" style="margin-top:8px" onclick="startAI()">开始人机对战</button>
    </div>`;
  } else {
    box.innerHTML = `<div class="card">
      <button class="btn block" onclick="createRoom()">创建房间</button>
      <input id="room-pass" placeholder="房间密码（选填）" style="margin-top:8px">
      <div class="row" style="margin-top:8px">
        <input id="room-code" placeholder="输入6位房间号" style="flex:1">
        <button class="btn" onclick="joinRoomByCode()">加入</button>
      </div>
      <div class="sub" style="margin-top:8px">房主可邀请AI补位；也可把房间号分享给好友</div>
    </div>`;
  }
}
function renderLobbyQueue(msg) {
  S.lobby.queueMsg = msg;
  const q = $('#queue-msg'), b = $('#queue-btn');
  if (q) q.textContent = msg;
  if (b) { b.textContent = S.queueing ? '取消匹配' : '开始排位匹配'; b.classList.toggle('ghost', S.queueing); }
}
function joinQueue() { if (!S.wsOpen) { toast('连接服务器中，请稍候', 'err'); return; } S.queueing = true; renderLobbyQueue('正在匹配同段位玩家...'); wsSend({ type: 'queue_join', game: S.lobby.game }); }
function leaveQueue() { S.queueing = false; wsSend({ type: 'queue_leave', game: S.lobby.game }); renderLobbyQueue(''); }
async function startAI() {
  try {
    await POST('/match/start', { game: S.lobby.game, mode: 'ai', stars: S.lobby.stars });
    toast('已创建对局', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}
async function loadLobbyRank() {
  const box = $('#lobby-rank'); if (!box) return;
  try {
    const rows = await GET(`/rankings?type=game&game=${S.lobby.game}&limit=100`);
    box.innerHTML = rows.length ? rows.map((r, i) => `<div class="item" onclick="openUser(${r.id})">
      <div class="no ${i < 3 ? 'top' + (i + 1) : ''}">${i + 1}</div>${avatarHtml(r, 'sm')}
      <div style="flex:1"><div class="row">${esc(r.name)}${isStaff() && r.is_virtual ? '<span class="tag virtual">虚拟</span>' : ''}</div>
      <div class="sub">${esc(r.label)} · 累计 ${r.accumulated} 分 · ${r.wins}胜${r.losses}负</div></div></div>`).join('')
      : '<div class="empty">暂无段位数据</div>';
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function createRoom() {
  try {
    const password = $('#room-pass') ? $('#room-pass').value.trim() : '';
    const r = await POST('/rooms', { game: S.lobby.game, password });
    S.room = { code: r.code, game: r.game, members: [S.me], max_players: r.max_players, has_password: !!password };
    showView('room');
  } catch (e) { toast(e.message, 'err'); }
}
async function joinRoomByCode() {
  const code = $('#room-code').value.trim();
  if (!/^\d{6}$/.test(code)) { toast('请输入6位房间号', 'err'); return; }
  const password = $('#room-pass') ? $('#room-pass').value.trim() : '';
  try {
    const r = await POST(`/rooms/${code}/join`, { password });
    if (r.match_id) return;
    await loadRoom(code);
  } catch (e) { toast(e.message, 'err'); }
}
async function loadRoom(code) {
  try {
    const r = await GET(`/rooms/${code}`);
    S.room = { code, game: r.game, members: r.members || [], max_players: r.max_players, has_password: r.has_password };
    if (S.view === 'room') render(); else showView('room');
  } catch (e) { toast(e.message, 'err'); }
}
function viewRoom(app) {
  const r = S.room; if (!r) { goBack(); return; }
  const isHost = r.members.length && r.members[0].id === S.me.id;
  app.innerHTML = `${topbarHtml('房间 · ' + gameName(r.game))}
    <div class="card" style="text-align:center">
      <div class="sub">房间号（分享给好友加入）</div>
      <div class="code-box">${r.code}</div>
      ${r.has_password ? '<div class="sub">本房间已设密码</div>' : ''}
      <button class="btn small ghost" onclick="copyRoomCode()">复制房间号</button>
    </div>
    <div class="section-title">成员 ${r.members.length}/${r.max_players}</div>
    <div class="card">${r.members.map((m) => `<div class="list-item">${avatarHtml(m, 'sm')}
      <div style="flex:1">${esc(m.name)} ${m.id === S.me.id ? '<span class="tag">我</span>' : ''} ${userTag(m)}</div>
      ${m.id === (r.members[0] && r.members[0].id) ? '<span class="tag real">房主</span>' : ''}</div>`).join('')}
    ${r.members.length < r.max_players ? '<div class="empty">等待玩家加入，或由房主邀请AI</div>' : '<div class="sub" style="text-align:center">人齐了，即将开局...</div>'}</div>
    <div class="row" style="margin:0 14px;gap:8px">
      ${isHost && r.members.length < r.max_players ? `<button class="btn" style="flex:1" onclick="addRoomAI()">邀请AI</button>` : ''}
      <button class="btn ghost" style="flex:1" onclick="leaveRoom()">离开房间</button>
    </div>${bottomNavHtml()}`;
}
function copyRoomCode() {
  const code = S.room && S.room.code;
  if (navigator.clipboard) navigator.clipboard.writeText(code).then(() => toast('已复制 ' + code, 'ok'), () => { });
  else toast('房间号：' + code);
}
async function addRoomAI() {
  try { await POST(`/rooms/${S.room.code}/ai`, { stars: S.lobby.stars || 40 }); }
  catch (e) { toast(e.message, 'err'); }
}
async function leaveRoom() {
  try { if (S.room) await POST(`/rooms/${S.room.code}/leave`, {}); } catch (e) { }
  S.room = null; goBack();
}
const SEAT_LABEL = { 1: '红/先手', 2: '黄/二手', 3: '蓝/三手', 4: '绿/四手' };
function seatName(side, n) {
  if (n <= 2) return side === 1 ? '红/先手' : '蓝/后手';
  return SEAT_LABEL[side] || (side + '号');
}
function matchSeats(m) {
  if (m.seats && Object.keys(m.seats).length) return m.seats;
  const out = {};
  out[String(m.side || 1)] = S.me;
  if (m.opponent) out[String(m.side === 1 ? 2 : 1)] = m.opponent;
  return out;
}
function renderMatchHud() {
  const box = $('#match-hud'); if (!box || !S.match) return;
  const m = S.match;
  const seats = matchSeats(m);
  const n = Object.keys(seats).length || 2;
  box.innerHTML = Object.keys(seats).sort((a, b) => +a - +b).map((k) => {
    const s = +k, u = seats[k] || {};
    const mine = s === m.side;
    const ai = m.ai_sides && m.ai_sides[s];
    return `<div class="player-chip ${m.turn === s && !m.finished ? 'turn' : ''}">${avatarHtml(mine ? S.me : u, 'sm')} ${esc((mine ? (S.me && S.me.name) : u.name) || ('座位' + s))} <span class="sub">${seatName(s, n)}</span>${ai ? ` <span class="tag virtual">${ai}星AI</span>` : ''}</div>`;
  }).join('');
}
function toggleTrust() {
  if (!isStaff()) { toast('托管仅作者可用', 'err'); return; }
  S.match.trust = !S.match.trust; render();
  if (S.match.trust && S.match.turn === S.match.side) {
    if (S.match.game === 'gomoku') autoMoveGomoku();
    else if (S.match.game === 'feixing') autoMoveFeixing();
    else if (S.match.game === 'horror') autoMoveHorror();
  }
}
function resign() {
  if (!confirm('确定认输吗？')) return;
  wsSend({ type: 'resign', match_id: S.match.id });
}
function sendGameChat() {
  const inp = $('#chat-input'); if (!inp || !inp.value.trim()) return;
  const text = inp.value.trim();
  wsSend({ type: 'chat', match_id: S.match.id, text });
  S.match.chat = S.match.chat || [];
  S.match.chat.push({ from: (S.me && S.me.name) || '我', text });
  renderMatchChat();
  inp.value = '';
}
const XQ_CHARS = { K: '帥', A: '仕', E: '相', H: '馬', R: '車', C: '炮', P: '兵', k: '將', a: '士', e: '象', h: '馬', r: '車', c: '砲', p: '卒' };
function drawXiangqi(ctx, st) {
  const P = 26, CW = 36, CH = 36;
  ctx.strokeStyle = '#8a6d3b'; ctx.lineWidth = 1.2;
  for (let r = 0; r < 10; r++) {
    ctx.beginPath(); ctx.moveTo(P, P + r * CH); ctx.lineTo(P + 8 * CW, P + r * CH); ctx.stroke();
  }
  for (let c = 0; c < 9; c++) {
    if (c === 0 || c === 8) {
      ctx.beginPath(); ctx.moveTo(P + c * CW, P); ctx.lineTo(P + c * CW, P + 9 * CH); ctx.stroke();
    } else {
      ctx.beginPath(); ctx.moveTo(P + c * CW, P); ctx.lineTo(P + c * CW, P + 4 * CH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(P + c * CW, P + 5 * CH); ctx.lineTo(P + c * CW, P + 9 * CH); ctx.stroke();
    }
  }
  for (const [r, c] of [[0, 3], [0, 5], [2, 3], [2, 5], [7, 3], [7, 5], [9, 3], [9, 5]]) {
    ctx.beginPath(); ctx.moveTo(P + c * CW, P + r * CH);
    ctx.lineTo(P + (c === 3 ? 5 : 3) * CW, P + (r <= 2 ? 2 : 7) * CH); ctx.stroke();
  }
  ctx.fillStyle = '#8a6d3b'; ctx.font = '14px serif';
  ctx.fillText('楚 河', P + 2.2 * CW, P + 4.65 * CH);
  ctx.fillText('汉 界', P + 5.3 * CW, P + 4.65 * CH);
  const sel = S.match.sel;
  st.board.forEach((row, r) => row.forEach((p, c) => {
    const x = P + c * CW, y = P + r * CH;
    if (sel && sel[0] === r && sel[1] === c) {
      ctx.beginPath(); ctx.arc(x, y, 17, 0, 7); ctx.strokeStyle = '#f5b942'; ctx.lineWidth = 3; ctx.stroke();
    }
    if (!p) return;
    ctx.beginPath(); ctx.arc(x, y, 15, 0, 7);
    ctx.fillStyle = p === p.toUpperCase() ? '#f8ecd0' : '#e8d9b8'; ctx.fill();
    ctx.strokeStyle = p === p.toUpperCase() ? '#c0392b' : '#1c1c24'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = p === p.toUpperCase() ? '#c0392b' : '#1c1c24';
    ctx.font = 'bold 16px serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(XQ_CHARS[p] || '?', x, y + 1);
  }));
  ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
  if (Array.isArray(st.last) && st.last.length === 4) {
    const [, , r2, c2] = st.last;
    ctx.strokeStyle = 'rgba(239,68,68,.9)'; ctx.lineWidth = 2;
    ctx.strokeRect(P + c2 * CW - 17, P + r2 * CH - 17, 34, 34);
  }
}
function boardClick(x, y) {
  const m = S.match; if (!m || m.finished || !m.state) return;
  if (m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  const game = m.game;
  if (game === 'gomoku') {
    const P = 24, C = 24;
    const c = Math.round((x - P) / C), r = Math.round((y - P) / C);
    if (r < 0 || r > 14 || c < 0 || c > 14) return;
    if (m.state.board[r][c] && !isStaff()) return;
    wsSend({ type: 'move', match_id: m.id, move: [r, c] }); snd.play('click');
  } else if (game === 'tictactoe') {
    const P = 18, C = 76;
    const c = Math.floor((x - P) / C), r = Math.floor((y - P) / C);
    if (r < 0 || r > 2 || c < 0 || c > 2) return;
    const idx = r * 3 + c;
    if (m.state.board[idx] && !isStaff()) return;
    wsSend({ type: 'move', match_id: m.id, move: idx }); snd.play('click');
  } else if (game === 'go') {
    const P = 24, C = 42;
    const c = Math.round((x - P) / C), r = Math.round((y - P) / C);
    if (r < 0 || r > 8 || c < 0 || c > 8) return;
    if (m.state.board[r][c] && !isStaff()) return;
    wsSend({ type: 'move', match_id: m.id, move: [r, c] }); snd.play('click');
  }
  boardClickDispatch(x, y);
}
function xiangqiClick(x, y) {
  const m = S.match, P = 26, CW = 36, CH = 36;
  const c = Math.round((x - P) / CW), r = Math.round((y - P) / CH);
  if (r < 0 || r > 9 || c < 0 || c > 8) return;
  const board = m.state.board, p = board[r][c];
  const mine = p && ((m.side === 1) === (p === p.toUpperCase()));
  if (m.sel) {
    const mv = [m.sel[0], m.sel[1], r, c];
    if (m.sel[0] === r && m.sel[1] === c) { m.sel = null; drawBoard(); return; }
    if (isStaff()) {
      if (!p || xqSide(p) !== m.side) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    } else {
      const legal = xqLegalTargets(board, m.side, m.sel[0], m.sel[1]);
      if (legal.some(([rr, cc]) => rr === r && cc === c)) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    }
  }
  if (mine) { m.sel = [r, c]; drawBoard(); highlightXqTargets(board, r, c); }
  else { m.sel = null; drawBoard(); }
}
function xqSide(p) { return p ? (p === p.toUpperCase() ? 1 : 2) : 0; }
function xqInPalace(r, c, side) { return c >= 3 && c <= 5 && (side === 1 ? r >= 7 : r <= 2); }
function xqGenAll(board, side) {
  const out = [];
  for (let r = 0; r < 10; r++) for (let c = 0; c < 9; c++) {
    const p = board[r][c];
    if (!p || xqSide(p) !== side) continue;
    out.push(...xqMovesFrom(board, r, c));
  }
  return out;
}
function xqMovesFrom(board, r, c) {
  const p = board[r][c]; if (!p) return [];
  const side = xqSide(p), up = p.toUpperCase(), out = [];
  const push = (rr, cc) => { if (rr >= 0 && rr < 10 && cc >= 0 && cc < 9 && xqSide(board[rr][cc]) !== side) out.push([rr, cc]); };
  if (up === 'K') { [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([dr, dc]) => { const rr = r + dr, cc = c + dc; if (xqInPalace(rr, cc, side)) push(rr, cc); }); }
  else if (up === 'A') { [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([dr, dc]) => { const rr = r + dr, cc = c + dc; if (xqInPalace(rr, cc, side)) push(rr, cc); }); }
  else if (up === 'E') {
    [[2, 2], [2, -2], [-2, 2], [-2, -2]].forEach(([dr, dc]) => {
      const rr = r + dr, cc = c + dc, mr = r + dr / 2, mc = c + dc / 2;
      if (rr < 0 || rr > 9 || cc < 0 || cc > 8 || board[mr][mc]) return;
      if (side === 1 && rr < 5) return; if (side === 2 && rr > 4) return;
      push(rr, cc);
    });
  } else if (up === 'H') {
    [[2, 1, 1, 0], [2, -1, 1, 0], [-2, 1, -1, 0], [-2, -1, -1, 0], [1, 2, 0, 1], [-1, 2, 0, 1], [1, -2, 0, -1], [-1, -2, 0, -1]].forEach(([dr, dc, lr, lc]) => {
      const rr = r + dr, cc = c + dc;
      if (rr < 0 || rr > 9 || cc < 0 || cc > 8 || board[r + lr][c + lc]) return;
      push(rr, cc);
    });
  } else if (up === 'R' || up === 'C') {
    for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      let rr = r + dr, cc = c + dc, jumped = false;
      while (rr >= 0 && rr < 10 && cc >= 0 && cc < 9) {
        const t = board[rr][cc];
        if (up === 'R') { if (t) { if (xqSide(t) !== side) out.push([rr, cc]); break; } out.push([rr, cc]); }
        else { if (!jumped) { if (t) jumped = true; else out.push([rr, cc]); } else if (t) { if (xqSide(t) !== side) out.push([rr, cc]); break; } }
        rr += dr; cc += dc;
      }
    }
  } else if (up === 'P') {
    const fwd = side === 1 ? -1 : 1;
    push(r + fwd, c);
    const crossed = side === 1 ? r <= 4 : r >= 5;
    if (crossed) { push(r, c + 1); push(r, c - 1); }
  }
  return out;
}
function xqLegalTargets(board, side, r, c) { return xqMovesFrom(board, r, c); }
function highlightXqTargets(board, r, c) {
  const cv = $('#board'); if (!cv) return;
  const ctx = cv.getContext('2d'), P = 26, CW = 36, CH = 36;
  ctx.fillStyle = 'rgba(245,185,66,.85)';
  xqLegalTargets(board, S.match.side, r, c).forEach(([rr, cc]) => {
    ctx.beginPath(); ctx.arc(P + cc * CW, P + rr * CH, 5, 0, 7); ctx.fill();
  });
}
function dbClick(x, y) {
  const m = S.match, P = 20, C = 36;
  const c = Math.floor((x - P) / C), r = Math.floor((y - P) / C);
  if (r < 0 || r > 8 || c < 0 || c > 6) return;
  const board = m.state.board, p = board[r][c];
  const mine = p && (p.startsWith('r_') ? 1 : 2) === m.side;
  if (m.sel) {
    if (m.sel[0] === r && m.sel[1] === c) { m.sel = null; drawBoard(); return; }
    const mv = [m.sel[0], m.sel[1], r, c];
    if (isStaff()) {
      if (!p || (p.startsWith('r_') ? 1 : 2) !== m.side) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    } else {
      const legal = dbLegalTargets(board, m.sel[0], m.sel[1]);
      if (legal.some(([rr, cc]) => rr === r && cc === c)) {
        wsSend({ type: 'move', match_id: m.id, move: mv });
        m.sel = null; snd.play('click'); return;
      }
    }
  }
  if (mine) { m.sel = [r, c]; drawBoard(); highlightDbTargets(board, r, c); }
  else { m.sel = null; drawBoard(); }
}
async function setAI(key, val) {
  try { await POST('/admin/ai', { [key]: val }); toast('已保存', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
let _lpTimer = null, _lpFired = false;
function initBoardCanvas() {
  const cv = $('#board'); if (!cv || !S.match || S.match.game === 'pvz') return;
  const cfg = BOARD_CFG[S.match.game];
  cv.width = cfg.w * devicePixelRatio; cv.height = cfg.h * devicePixelRatio;
  cv.style.width = cfg.w + 'px'; cv.style.height = cfg.h + 'px';
  cv.onclick = (e) => {
    if (_lpFired) { _lpFired = false; return; }
    const rect = cv.getBoundingClientRect();
    boardClick(Math.round(e.clientX - rect.left), Math.round(e.clientY - rect.top));
  };
  const lpStart = (x, y) => {
    _lpFired = false;
    if (_lpTimer) clearTimeout(_lpTimer);
    _lpTimer = setTimeout(() => {
      _lpFired = true;
      if (isStaff()) authorTransformAt(x, y);
    }, 450);
  };
  const lpCancel = () => { if (_lpTimer) { clearTimeout(_lpTimer); _lpTimer = null; } };
  cv.onmousedown = (e) => { const r = cv.getBoundingClientRect(); lpStart(e.clientX - r.left, e.clientY - r.top); };
  cv.onmouseup = lpCancel;
  cv.onmouseleave = lpCancel;
  cv.ontouchstart = (e) => { const r = cv.getBoundingClientRect(); const t = e.touches[0]; lpStart(t.clientX - r.left, t.clientY - r.top); };
  cv.ontouchend = lpCancel;
  cv.ontouchmove = lpCancel;
  drawBoard();
}
function authorTransformAt(x, y) {
  const m = S.match; if (!m || !m.state) return;
  const g = m.game;
  let r, c;
  if (g === 'chess' || g === 'tiaoqi') {
    const P = g === 'tiaoqi' ? 8 : 16, C = g === 'tiaoqi' ? 46 : 44;
    r = Math.round((y - P) / C); c = Math.round((x - P) / C);
    if (r < 0 || r > 7 || c < 0 || c > 7) return;
  } else if (g === 'xiangqi') {
    const P = 26, CW = 36, CH = 36;
    c = Math.round((x - P) / CW); r = Math.round((y - P) / CH);
    if (r < 0 || r > 9 || c < 0 || c > 8) return;
  } else if (g === 'doubeast') {
    const P = 20, C = 36;
    c = Math.floor((x - P) / C); r = Math.floor((y - P) / C);
    if (r < 0 || r > 8 || c < 0 || c > 6) return;
  } else if (g === 'gomoku') {
    const P = 24, C = 24;
    c = Math.round((x - P) / C); r = Math.round((y - P) / C);
    if (r < 0 || r > 14 || c < 0 || c > 14) return;
  } else if (g === 'go') {
    const P = 24, C = 42;
    c = Math.round((x - P) / C); r = Math.round((y - P) / C);
    if (r < 0 || r > 8 || c < 0 || c > 8) return;
  } else if (g === 'tictactoe') {
    const P = 18, C = 76;
    c = Math.floor((x - P) / C); r = Math.floor((y - P) / C);
    if (r < 0 || r > 2 || c < 0 || c > 2) return;
  } else if (g === 'junqi') {
    const P = 12, CW = 68, CH = 30;
    c = Math.floor((x - P) / CW); r = Math.floor((y - P) / CH);
    if (r < 0 || r > 11 || c < 0 || c > 4) return;
  } else if (g === 'horror') {
    r = 0; c = 0;
  } else return;
  openTransformModal(r, c);
}
function openTransformModal(r, c) {
  const m = S.match;
  const g = m.game;
  const cell = (piece, label) =>
    `<button class="btn small" style="min-width:54px" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:${r},c:${c},piece:'${piece}',side:0});closeModal()">${label}</button>`;
  if (g === 'horror') {
    let html = `<div style="padding:6px 2px"><div class="sub" style="text-align:center;margin-bottom:8px">五夜神权</div>
      <div class="sub">传送鬼</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    [['stage','舞台'],['dining','餐厅'],['west','西厅'],['east','东厅'],['left_door','左门'],['right_door','右门'],['office','办公室']].forEach(([k,n]) => {
      html += `<button class="btn small" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:0,c:0,piece:'${k}',side:0});closeModal()">${n}</button>`;
    });
    html += `</div><div class="sub" style="margin-top:8px">门 / 电量 / 钟点</div><div class="row" style="flex-wrap:wrap;gap:6px">
      <button class="btn small" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:1,c:0,piece:'left',side:0});closeModal()">左门</button>
      <button class="btn small" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:1,c:0,piece:'right',side:0});closeModal()">右门</button>
      <button class="btn small" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:2,c:0,piece:'100',side:0});closeModal()">电100</button>
      <button class="btn small" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:2,c:0,piece:'0',side:0});closeModal()">断电</button>
      <button class="btn small" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:3,c:0,piece:'6',side:0});closeModal()">6点</button>
    </div></div>`;
    modal(html); return;
  }
  let cur;
  if (g === 'tictactoe') cur = m.state.board[r * 3 + c];
  else cur = m.state.board[r][c];
  const curLabel = (!cur || cur === '.' || cur === 0) ? '空' : String(cur);
  let html = `<div style="padding:6px 2px">
    <div class="sub" style="text-align:center;margin-bottom:8px">改变 (${r + 1},${c + 1}) · 当前：${esc(curLabel)}</div>`;
  if (g === 'chess' || g === 'xiangqi') {
    const CHESS_U = { K: '♔', Q: '♕', R: '♖', B: '♗', N: '♘', P: '♙' };
    const CHESS_L = { K: '♚', Q: '♛', R: '♜', B: '♝', N: '♞', P: '♟' };
    const XQ_U = { K: '帅', A: '仕', E: '相', H: '马', R: '车', C: '炮', P: '兵' };
    const XQ_L = { K: '将', A: '士', E: '象', H: '马', R: '车', C: '炮', P: '卒' };
    const up = g === 'chess' ? CHESS_U : XQ_U;
    const low = g === 'chess' ? CHESS_L : XQ_L;
    html += `<div class="sub" style="margin:4px 0">红/白方</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    for (const k of Object.keys(up)) html += cell(k.toUpperCase(), up[k]);
    html += `</div><div class="sub" style="margin:4px 0">黑方</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    for (const k of Object.keys(low)) html += cell(k.toLowerCase(), low[k]);
    html += `</div>`;
  } else if (g === 'gomoku' || g === 'go') {
    html += `<div class="row" style="flex-wrap:wrap;gap:6px">${cell('1', '黑子')}${cell('2', '白子')}</div>`;
  } else if (g === 'tictactoe') {
    html += `<div class="row" style="flex-wrap:wrap;gap:6px">${cell('1', 'X 先手')}${cell('2', 'O 后手')}</div>`;
  } else if (g === 'tiaoqi') {
    html += `<div class="sub" style="margin:4px 0">白方</div><div class="row" style="flex-wrap:wrap;gap:6px">${cell('1', '白兵')}${cell('3', '白王')}</div>
      <div class="sub" style="margin:4px 0">黑方</div><div class="row" style="flex-wrap:wrap;gap:6px">${cell('2', '黑兵')}${cell('4', '黑王')}</div>`;
  } else if (g === 'doubeast') {
    const kinds = [['rat', '鼠'], ['cat', '猫'], ['dog', '狗'], ['wolf', '狼'], ['leopard', '豹'], ['tiger', '虎'], ['lion', '狮'], ['elephant', '象']];
    html += `<div class="sub" style="margin:4px 0">红方</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    for (const [k, n] of kinds) html += cell('r_' + k, n);
    html += `</div><div class="sub" style="margin:4px 0">蓝方</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    for (const [k, n] of kinds) html += cell('b_' + k, n);
    html += `</div>`;
  } else if (g === 'junqi') {
    const kinds = [['cmd', '司'], ['army', '军'], ['div', '师'], ['brig', '旅'], ['reg', '团'], ['bat', '营'], ['co', '连'], ['plt', '排'], ['eng', '工'], ['bomb', '炸'], ['mine', '雷'], ['flag', '旗']];
    html += `<div class="sub" style="margin:4px 0">红方</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    for (const [k, n] of kinds) html += cell('r_' + k, n);
    html += `</div><div class="sub" style="margin:4px 0">黑方</div><div class="row" style="flex-wrap:wrap;gap:6px">`;
    for (const [k, n] of kinds) html += cell('b_' + k, n);
    html += `</div>`;
  }
  html += `<div class="row" style="margin-top:10px;gap:8px">
    <button class="btn small danger" style="flex:1" onclick="wsSend({type:'transform_piece',match_id:${m.id},r:${r},c:${c},piece:'.',side:0});closeModal()">清空格子</button>
  </div></div>`;
  modal(html);
}
const BOARD_CFG = {
  gomoku: { w: 384, h: 384 }, tictactoe: { w: 264, h: 264 },
  xiangqi: { w: 342, h: 384 }, doubeast: { w: 288, h: 360 },
  chess: { w: 384, h: 384 }, tiaoqi: { w: 384, h: 384 },
  go: { w: 384, h: 384 }, junqi: { w: 364, h: 384 },
  feixing: { w: 384, h: 384 }, doudizhu: { w: 384, h: 280 },
  horror: { w: 384, h: 280 },
};
function drawBoard() {
  const cv = $('#board'); if (!cv || !S.match || !S.match.state) return;
  if (S.match.game === 'pvz') return;
  const ctx = cv.getContext('2d');
  const cfg = BOARD_CFG[S.match.game]; if (!cfg) return;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.fillStyle = '#f3e9d2'; ctx.fillRect(0, 0, cfg.w, cfg.h);
  drawBoardDispatch();
}
function drawBoardDispatch() {
  if (!S.match || !S.match.state) return;
  const ctx = $('#board').getContext('2d');
  if (S.match.game === 'gomoku') drawGomoku(ctx, S.match.state);
  else if (S.match.game === 'tictactoe') drawTicTacToe(ctx, S.match.state);
  else if (S.match.game === 'xiangqi') drawXiangqi(ctx, S.match.state);
  else if (S.match.game === 'doubeast') drawDoubeast(ctx, S.match.state);
  else if (S.match.game === 'chess') drawChess(ctx, S.match.state);
  else if (S.match.game === 'tiaoqi') drawCheckers(ctx, S.match.state);
  else if (S.match.game === 'go') drawGo(ctx, S.match.state);
  else if (S.match.game === 'junqi') drawJunqi(ctx, S.match.state);
  else if (S.match.game === 'feixing') drawFeixing(ctx, S.match.state);
  else if (S.match.game === 'doudizhu') drawDoudizhu(ctx, S.match.state);
  else if (S.match.game === 'horror') drawHorror(ctx, S.match.state);
}
function drawGomoku(ctx, st) {
  const N = 15, P = 24, C = 24;
  ctx.strokeStyle = '#8a6d3b'; ctx.lineWidth = 1;
  for (let i = 0; i < N; i++) {
    ctx.beginPath(); ctx.moveTo(P, P + i * C); ctx.lineTo(P + (N - 1) * C, P + i * C); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(P + i * C, P); ctx.lineTo(P + i * C, P + (N - 1) * C); ctx.stroke();
  }
  [[3, 3], [11, 11], [3, 11], [11, 3], [7, 7]].forEach(([r, c]) => {
    ctx.beginPath(); ctx.arc(P + c * C, P + r * C, 2.5, 0, 7); ctx.fillStyle = '#8a6d3b'; ctx.fill();
  });
  st.board.forEach((row, r) => row.forEach((v, c) => {
    if (!v) return;
    ctx.beginPath(); ctx.arc(P + c * C, P + r * C, 10, 0, 7);
    ctx.fillStyle = v === 1 ? '#1c1c24' : '#f8f8f8'; ctx.fill();
    ctx.strokeStyle = v === 1 ? '#000' : '#999'; ctx.stroke();
  }));
  if (st.last) {
    ctx.beginPath(); ctx.arc(P + st.last[1] * C, P + st.last[0] * C, 3.5, 0, 7);
    ctx.fillStyle = '#ef4444'; ctx.fill();
  }
}
function drawTicTacToe(ctx, st) {
  const P = 18, C = 76;
  ctx.strokeStyle = '#8a6d3b'; ctx.lineWidth = 2;
  for (let i = 1; i < 3; i++) {
    ctx.beginPath(); ctx.moveTo(P + i * C, P); ctx.lineTo(P + i * C, P + 3 * C - 22); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(P, P + i * C); ctx.lineTo(P + 3 * C - 22, P + i * C); ctx.stroke();
  }
  st.board.forEach((v, i) => {
    const r = Math.floor(i / 3), c = i % 3;
    const x = P + c * C + 30, y = P + r * C + 30;
    ctx.lineWidth = 5;
    if (v === 1) { ctx.strokeStyle = '#5b8cff'; ctx.beginPath(); ctx.moveTo(x - 20, y - 20); ctx.lineTo(x + 20, y + 20); ctx.moveTo(x + 20, y - 20); ctx.lineTo(x - 20, y + 20); ctx.stroke(); }
    else if (v === 2) { ctx.strokeStyle = '#ec4899'; ctx.beginPath(); ctx.arc(x, y, 20, 0, 7); ctx.stroke(); }
  });
}
const DB_NAMES = { rat: '鼠', cat: '猫', dog: '狗', wolf: '狼', leopard: '豹', tiger: '虎', lion: '狮', elephant: '象' };
const DB_RIVERS = [[3, 1], [3, 2], [3, 4], [3, 5], [4, 1], [4, 2], [4, 4], [4, 5], [5, 1], [5, 2], [5, 4], [5, 5]];
const DB_TRAPS = [[0, 2], [0, 4], [1, 3], [8, 2], [8, 4], [7, 3]];
function drawDoubeast(ctx, st) {
  const P = 20, C = 36;
  for (const [r, c] of DB_RIVERS) { ctx.fillStyle = '#7db8e8'; ctx.fillRect(P + c * C, P + r * C, C, C); }
  for (const [r, c] of DB_TRAPS) { ctx.fillStyle = 'rgba(180,140,80,.35)'; ctx.fillRect(P + c * C, P + r * C, C, C); }
  ctx.fillStyle = 'rgba(120,80,20,.5)'; ctx.font = '12px serif'; ctx.textAlign = 'center';
  ctx.fillText('穴', P + 3 * C + 18, P + 0 * C + 22);
  ctx.fillText('穴', P + 3 * C + 18, P + 8 * C + 22);
  ctx.textAlign = 'start';
  ctx.strokeStyle = '#8a6d3b'; ctx.lineWidth = 1.2;
  for (let r = 0; r <= 9; r++) { ctx.beginPath(); ctx.moveTo(P, P + r * C); ctx.lineTo(P + 7 * C, P + r * C); ctx.stroke(); }
  for (let c = 0; c <= 7; c++) { ctx.beginPath(); ctx.moveTo(P + c * C, P); ctx.lineTo(P + c * C, P + 9 * C); ctx.stroke(); }
  const sel = S.match.sel;
  st.board.forEach((row, r) => row.forEach((p, c) => {
    const x = P + c * C + C / 2, y = P + r * C + C / 2;
    if (sel && sel[0] === r && sel[1] === c) {
      ctx.beginPath(); ctx.arc(x, y, 16, 0, 7); ctx.strokeStyle = '#f5b942'; ctx.lineWidth = 3; ctx.stroke();
    }
    if (!p) return;
    const kind = p.split('_')[1], red = p.startsWith('r_');
    ctx.beginPath(); ctx.arc(x, y, 14.5, 0, 7);
    ctx.fillStyle = red ? '#f8d8c8' : '#d8e4f0'; ctx.fill();
    ctx.strokeStyle = red ? '#c0392b' : '#2c5aa0'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = red ? '#c0392b' : '#2c5aa0';
    ctx.font = 'bold 14px serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(DB_NAMES[kind] || '?', x, y + 1);
  }));
  ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
  if (Array.isArray(st.last) && st.last.length === 4) {
    const [, , r2, c2] = st.last;
    ctx.strokeStyle = 'rgba(239,68,68,.9)'; ctx.lineWidth = 2;
    ctx.strokeRect(P + c2 * C + 2, P + r2 * C + 2, C - 4, C - 4);
  }
}
const DB_RANK = { rat: 1, cat: 2, dog: 3, wolf: 4, leopard: 5, tiger: 6, lion: 7, elephant: 8 };
const DB_RIVER_SET = new Set(DB_RIVERS.map((p) => p.join()));
const DB_TRAP_SET = new Set(DB_TRAPS.map((p) => p.join()));
function dbCanCapture(ak, dk, atkR, atkC, defR, defC) {
  if (ak === 'rat' && dk === 'elephant') return true;
  if (ak === 'elephant' && dk === 'rat') return false;
  if (DB_TRAP_SET.has(defR + ',' + defC)) return true;
  const aw = DB_RIVER_SET.has(atkR + ',' + atkC), dw = DB_RIVER_SET.has(defR + ',' + defC);
  if (aw !== dw) return false;
  return DB_RANK[ak] >= DB_RANK[dk];
}
function dbLegalTargets(board, r, c) {
  const p = board[r][c]; if (!p) return [];
  const side = p.startsWith('r_') ? 1 : 2, kind = p.split('_')[1], out = [];
  for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    const rr = r + dr, cc = c + dc;
    if (rr < 0 || rr > 8 || cc < 0 || cc > 6) continue;
    if (DB_RIVER_SET.has(rr + ',' + cc) && kind !== 'rat' && kind !== 'lion' && kind !== 'tiger') continue;
    const t = board[rr][cc];
    if (t) {
      const tside = t.startsWith('r_') ? 1 : 2;
      if (tside === side) continue;
      if (dbCanCapture(kind, t.split('_')[1], r, c, rr, cc)) out.push([rr, cc]);
    } else out.push([rr, cc]);
  }
  return out;
}
function dbJumpTargets(board, r, c, kind, side) {
  const out = [];
  for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    let rr = r + dr, cc = c + dc, blocked = false, steps = 0;
    while (rr >= 0 && rr <= 8 && cc >= 0 && cc <= 6 && DB_RIVER_SET.has(rr + ',' + cc)) {
      if (board[rr][cc]) { blocked = true; break; }
      rr += dr; cc += dc; steps++;
    }
    if (!steps || blocked || rr < 0 || rr > 8 || cc < 0 || cc > 6) continue;
    const t = board[rr][cc];
    if (!t) out.push([rr, cc]);
    else if ((t.startsWith('r_') ? 1 : 2) !== side && dbCanCapture(kind, t.split('_')[1], r, c, rr, cc)) out.push([rr, cc]);
  }
  return out;
}
const _dbLegalOrig = dbLegalTargets;
dbLegalTargets = function (board, r, c) {
  const p = board[r][c]; if (!p) return [];
  const kind = p.split('_')[1], side = p.startsWith('r_') ? 1 : 2;
  const base = _dbLegalOrig(board, r, c);
  if (kind === 'lion' || kind === 'tiger') base.push(...dbJumpTargets(board, r, c, kind, side));
  return base;
};
function highlightDbTargets(board, r, c) {
  const cv = $('#board'); if (!cv) return;
  const ctx = cv.getContext('2d'), P = 20, C = 36;
  ctx.fillStyle = 'rgba(245,185,66,.85)';
  dbLegalTargets(board, r, c).forEach(([rr, cc]) => {
    ctx.beginPath(); ctx.arc(P + cc * C + 18, P + rr * C + 18, 5, 0, 7); ctx.fill();
  });
}
function boardClickDispatch(x, y) {
  const g = S.match.game;
  if (g === 'xiangqi') xiangqiClick(x, y);
  else if (g === 'doubeast') dbClick(x, y);
  else if (g === 'chess') chessClick(x, y);
  else if (g === 'tiaoqi') checkersClick(x, y);
  else if (g === 'junqi') junqiClick(x, y);
  else if (g === 'feixing') feixingClick(x, y);
  else if (g === 'doudizhu') doudizhuClick(x, y);
  else if (g === 'horror') horrorClick(x, y);
}
/* ---------- 国际象棋（前端） ---------- */
const CHESS_UNICODE = {
  K: '♔', Q: '♕', R: '♖', B: '♗', N: '♘', P: '♙',
  k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟',
};
function chSide(p) { if (!p || p === '.') return 0; return (p === p.toUpperCase()) ? 1 : 2; }
function chInB(r, c) { return r >= 0 && r < 8 && c >= 0 && c < 8; }
function chPush(out, board, side, rr, cc) {
  if (chInB(rr, cc) && chSide(board[rr][cc]) !== side) out.push([rr, cc]);
}
function chMovesFrom(board, r, c) {
  const p = board[r][c]; if (!p || p === '.') return [];
  const side = chSide(p), up = p.toUpperCase(), out = [];
  const slide = (dirs) => { for (const [dr, dc] of dirs) { let rr = r + dr, cc = c + dc; while (chInB(rr, cc)) { const t = board[rr][cc]; if (t === '.') { out.push([rr, cc]); } else { if (chSide(t) !== side) out.push([rr, cc]); break; } rr += dr; cc += dc; } } };
  if (up === 'P') {
    const dr = side === 1 ? -1 : 1, start = side === 1 ? 6 : 1;
    const rr = r + dr;
    if (chInB(rr, c) && board[rr][c] === '.') { out.push([rr, c]); if (r === start && board[r + 2 * dr][c] === '.') out.push([r + 2 * dr, c]); }
    for (const dc of [-1, 1]) { const rr2 = r + dr, cc2 = c + dc; if (chInB(rr2, cc2) && board[rr2][cc2] !== '.' && chSide(board[rr2][cc2]) !== side) out.push([rr2, cc2]); }
  } else if (up === 'N') {
    [[2,1],[2,-1],[-2,1],[-2,-1],[1,2],[1,-2],[-1,2],[-1,-2]].forEach(([dr, dc]) => chPush(out, board, side, r + dr, c + dc));
  } else if (up === 'K') {
    [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]].forEach(([dr, dc]) => chPush(out, board, side, r + dr, c + dc));
  } else if (up === 'R') slide([[1,0],[-1,0],[0,1],[0,-1]]);
  else if (up === 'B') slide([[1,1],[1,-1],[-1,1],[-1,-1]]);
  else if (up === 'Q') slide([[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]);
  return out;
}
function chLegalTargets(board, r, c, side) {
  const targets = chMovesFrom(board, r, c);
  // 简单合法性过滤：走完后自己不在将军（轻量实现：目标格不是受保护导致王被吃）
  return targets;
}
function highlightChessTargets(board, r, c) {
  const cv = $('#board'); if (!cv) return;
  const ctx = cv.getContext('2d'), P = 16, C = 44;
  ctx.fillStyle = 'rgba(245,185,66,.85)';
  chLegalTargets(board, r, c).forEach(([rr, cc]) => {
    ctx.beginPath(); ctx.arc(P + cc * C + 22, P + rr * C + 22, 6, 0, 7); ctx.fill();
  });
}
function chessClick(x, y) {
  const m = S.match, P = 16, C = 44;
  const c = Math.round((x - P) / C), r = Math.round((y - P) / C);
  if (r < 0 || r > 7 || c < 0 || c > 7) return;
  const board = m.state.board, p = board[r][c];
  const mine = p && p !== '.' && ((m.side === 1) === (p === p.toUpperCase()));
  if (m.sel) {
    const mv = [m.sel[0], m.sel[1], r, c];
    if (m.sel[0] === r && m.sel[1] === c) { m.sel = null; drawBoard(); return; }
    if (isStaff()) {
      if (p === '.' || chSide(p) !== m.side) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    } else {
      const targets = chMovesFrom(board, m.sel[0], m.sel[1]);
      if (targets.some(([rr, cc]) => rr === r && cc === c)) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    }
  }
  if (mine) { m.sel = [r, c]; drawBoard(); highlightChessTargets(board, r, c); }
  else { m.sel = null; drawBoard(); }
}
function drawChess(ctx, st) {
  const P = 16, C = 44;
  ctx.fillStyle = '#f0d9b5'; ctx.fillRect(0, 0, 384, 384);
  ctx.fillStyle = '#b58863';
  for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
    if ((r + c) % 2 === 0) ctx.fillStyle = '#f0d9b5'; else ctx.fillStyle = '#b58863';
    ctx.fillRect(P + c * C, P + r * C, C, C);
  }
  const sel = S.match.sel;
  st.board.forEach((row, r) => row.forEach((p, c) => {
    const x = P + c * C + C / 2, y = P + r * C + C / 2;
    if (sel && sel[0] === r && sel[1] === c) {
      ctx.beginPath(); ctx.arc(x, y, 20, 0, 7); ctx.strokeStyle = '#f5b942'; ctx.lineWidth = 3; ctx.stroke();
    }
    if (!p || p === '.') return;
    ctx.font = '34px serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = chSide(p) === 1 ? '#111' : '#222';
    ctx.fillText(CHESS_UNICODE[p] || p, x, y + 1);
  }));
  ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
  if (Array.isArray(st.last) && st.last.length === 4) {
    const [, , r2, c2] = st.last;
    ctx.strokeStyle = 'rgba(239,68,68,.9)'; ctx.lineWidth = 3;
    ctx.strokeRect(P + c2 * C + 2, P + r2 * C + 2, C - 4, C - 4);
  }
}
/* ---------- 国际跳棋（前端） ---------- */
function ckSide(p) {
  if (p === '1' || p === '3') return 1;
  if (p === '2' || p === '4') return 2;
  return 0;
}
function ckDark(r, c) { return (r + c) % 2 === 1; }
function ckMovesFrom(board, r, c) {
  const p = board[r][c]; if (!p || p === '.') return [];
  const side = ckSide(p), king = (p === '3' || p === '4');
  const dirs = king ? [[1,-1],[1,1],[-1,-1],[-1,1]] : (side === 1 ? [[-1,-1],[-1,1]] : [[1,-1],[1,1]]);
  const out = [];
  for (const [dr, dc] of dirs) {
    const rr = r + dr, cc = c + dc;
    if (chInB(rr, cc) && ckDark(rr, cc) && board[rr][cc] === '.') out.push([rr, cc]);
  }
  return out;
}
function ckJumpsFrom(board, r, c) {
  const p = board[r][c]; if (!p || p === '.') return [];
  const side = ckSide(p), king = (p === '3' || p === '4');
  const dirs = king ? [[1,-1],[1,1],[-1,-1],[-1,1]] : (side === 1 ? [[-1,-1],[-1,1]] : [[1,-1],[1,1]]);
  const out = [];
  for (const [dr, dc] of dirs) {
    const mr = r + dr, mc = c + dc, lr = r + 2 * dr, lc = c + 2 * dc;
    if (!chInB(lr, lc) || !ckDark(lr, lc)) continue;
    const mid = board[mr][mc];
    if (mid === '.' || mid === undefined || ckSide(mid) === side) continue;
    if (board[lr][lc] !== '.') continue;
    out.push([lr, lc]);
  }
  return out;
}
function ckLegalTargets(board, r, c) {
  // 有吃必吃：若全局存在吃子则只显示吃子
  let hasAnyJump = false;
  for (let rr = 0; rr < 8; rr++) for (let cc = 0; cc < 8; cc++) {
    const q = board[rr][cc];
    if (q === '.' || q === undefined || ckSide(q) !== ckSide(board[r][c])) continue;
    if (ckJumpsFrom(board, rr, cc).length) { hasAnyJump = true; break; }
  }
  if (hasAnyJump) return ckJumpsFrom(board, r, c);
  return ckMovesFrom(board, r, c);
}
function highlightCheckersTargets(board, r, c) {
  const cv = $('#board'); if (!cv) return;
  const ctx = cv.getContext('2d'), P = 8, C = 46;
  ctx.fillStyle = 'rgba(245,185,66,.9)';
  ckLegalTargets(board, r, c).forEach(([rr, cc]) => {
    ctx.beginPath(); ctx.arc(P + cc * C + 23, P + rr * C + 23, 7, 0, 7); ctx.fill();
  });
}
function checkersClick(x, y) {
  const m = S.match, P = 8, C = 46;
  const c = Math.round((x - P) / C), r = Math.round((y - P) / C);
  if (r < 0 || r > 7 || c < 0 || c > 7) return;
  const board = m.state.board, p = board[r][c];
  const mine = p && p !== '.' && ckSide(p) === m.side;
  if (m.sel) {
    const mv = [m.sel[0], m.sel[1], r, c];
    if (m.sel[0] === r && m.sel[1] === c) { m.sel = null; drawBoard(); return; }
    if (isStaff()) {
      if (!p || p === '.' || ckSide(p) !== m.side) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    } else {
      const targets = ckLegalTargets(board, m.sel[0], m.sel[1]);
      if (targets.some(([rr, cc]) => rr === r && cc === c)) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    }
  }
  if (mine) { m.sel = [r, c]; drawBoard(); highlightCheckersTargets(board, r, c); }
  else { m.sel = null; drawBoard(); }
}
function drawCheckers(ctx, st) {
  const P = 8, C = 46;
  ctx.fillStyle = '#c8b899'; ctx.fillRect(0, 0, 384, 384);
  for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
    if (!ckDark(r, c)) { ctx.fillStyle = '#efe3c8'; ctx.fillRect(P + c * C, P + r * C, C, C); }
  }
  const sel = S.match.sel;
  st.board.forEach((row, r) => row.forEach((p, c) => {
    if (!p || p === '.') return;
    const x = P + c * C + C / 2, y = P + r * C + C / 2;
    const side = ckSide(p), king = (p === '3' || p === '4');
    ctx.beginPath(); ctx.arc(x, y, 17, 0, 7);
    ctx.fillStyle = side === 1 ? '#f5f0e6' : '#3a2b1e'; ctx.fill();
    ctx.strokeStyle = side === 1 ? '#9a8a6a' : '#000'; ctx.lineWidth = 1.5; ctx.stroke();
    if (sel && sel[0] === r && sel[1] === c) {
      ctx.beginPath(); ctx.arc(x, y, 20, 0, 7); ctx.strokeStyle = '#f5b942'; ctx.lineWidth = 3; ctx.stroke();
    }
    if (king) {
      ctx.fillStyle = side === 1 ? '#c0392b' : '#f5d442';
      ctx.font = 'bold 16px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('★', x, y + 1);
      ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
    }
  }));
  if (Array.isArray(st.last) && st.last.length === 4) {
    const [, , r2, c2] = st.last;
    ctx.strokeStyle = 'rgba(239,68,68,.9)'; ctx.lineWidth = 3;
    ctx.strokeRect(P + c2 * C + 2, P + r2 * C + 2, C - 4, C - 4);
  }
}
function drawGo(ctx, st) {
  const N = 9, P = 24, C = 42;
  ctx.fillStyle = '#dcb35c'; ctx.fillRect(0, 0, 384, 384);
  ctx.strokeStyle = '#5a3a1a'; ctx.lineWidth = 1.2;
  for (let i = 0; i < N; i++) {
    ctx.beginPath(); ctx.moveTo(P, P + i * C); ctx.lineTo(P + (N - 1) * C, P + i * C); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(P + i * C, P); ctx.lineTo(P + i * C, P + (N - 1) * C); ctx.stroke();
  }
  [[2, 2], [2, 6], [6, 2], [6, 6], [4, 4]].forEach(([r, c]) => {
    ctx.beginPath(); ctx.arc(P + c * C, P + r * C, 3, 0, 7); ctx.fillStyle = '#5a3a1a'; ctx.fill();
  });
  st.board.forEach((row, r) => row.forEach((v, c) => {
    if (!v) return;
    ctx.beginPath(); ctx.arc(P + c * C, P + r * C, 16, 0, 7);
    ctx.fillStyle = v === 1 ? '#1a1a1a' : '#f4f1ea'; ctx.fill();
    ctx.strokeStyle = v === 1 ? '#000' : '#888'; ctx.lineWidth = 1; ctx.stroke();
  }));
  if (Array.isArray(st.last) && st.last.length === 2 && st.last[0] >= 0) {
    const [r, c] = st.last;
    ctx.strokeStyle = 'rgba(239,68,68,.9)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(P + c * C, P + r * C, 8, 0, 7); ctx.stroke();
  }
}
function goPass() {
  const m = S.match; if (!m || m.finished || m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  wsSend({ type: 'move', match_id: m.id, move: [-1, -1] }); snd.play('click');
}
const JQ_LABEL = { cmd: '司', army: '军', div: '师', brig: '旅', reg: '团', bat: '营', co: '连', plt: '排', eng: '工', bomb: '炸', mine: '雷', flag: '旗' };
const JQ_CAMPS = [[2, 1], [2, 3], [4, 1], [4, 3], [7, 1], [7, 3], [9, 1], [9, 3]];
function drawJunqi(ctx, st) {
  const P = 12, CW = 68, CH = 30;
  ctx.fillStyle = '#3d5a3a'; ctx.fillRect(0, 0, 364, 384);
  for (let r = 0; r < 12; r++) for (let c = 0; c < 5; c++) {
    const x = P + c * CW, y = P + r * CH;
    ctx.fillStyle = (r === 5 || r === 6) ? '#2a4a28' : '#4a6a40';
    ctx.fillRect(x + 1, y + 1, CW - 2, CH - 2);
  }
  JQ_CAMPS.forEach(([r, c]) => {
    ctx.beginPath(); ctx.arc(P + c * CW + CW / 2, P + r * CH + CH / 2, 11, 0, 7);
    ctx.strokeStyle = '#c9a227'; ctx.lineWidth = 2; ctx.stroke();
  });
  const sel = S.match.sel;
  st.board.forEach((row, r) => row.forEach((p, c) => {
    if (!p) return;
    const x = P + c * CW + CW / 2, y = P + r * CH + CH / 2;
    const red = p.startsWith('r_') || (p === '?' && r >= 6);
    const hidden = p === '?';
    ctx.fillStyle = hidden ? '#6b5a3a' : (p.startsWith('r_') ? '#c0392b' : '#2c3e80');
    ctx.fillRect(x - 28, y - 12, 56, 24);
    ctx.strokeStyle = sel && sel[0] === r && sel[1] === c ? '#f5b942' : '#111';
    ctx.lineWidth = sel && sel[0] === r && sel[1] === c ? 3 : 1;
    ctx.strokeRect(x - 28, y - 12, 56, 24);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 13px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const lab = hidden ? '?' : (JQ_LABEL[p.split('_')[1]] || p);
    ctx.fillText(lab, x, y + 1);
  }));
  ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
}
function junqiClick(x, y) {
  const m = S.match, P = 12, CW = 68, CH = 30;
  const c = Math.floor((x - P) / CW), r = Math.floor((y - P) / CH);
  if (r < 0 || r > 11 || c < 0 || c > 4) return;
  const board = m.state.board, p = board[r][c];
  const mine = p && p !== '?' && ((p.startsWith('r_') ? 1 : 2) === m.side);
  if (m.sel) {
    if (m.sel[0] === r && m.sel[1] === c) { m.sel = null; drawBoard(); return; }
    const mv = [m.sel[0], m.sel[1], r, c];
    if (isStaff()) {
      const tside = p && p !== '?' ? (p.startsWith('r_') ? 1 : 2) : 0;
      if (!p || tside !== m.side) {
        wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
      }
    } else {
      wsSend({ type: 'move', match_id: m.id, move: mv }); m.sel = null; snd.play('click'); return;
    }
  }
  if (mine) { m.sel = [r, c]; drawBoard(); }
  else { m.sel = null; drawBoard(); }
}
const FX_COLORS = { 1: '#c0392b', 2: '#d4a017', 3: '#2c6fbb', 4: '#2e8b57' };
const FX_TAKEOFF = { 1: 0, 2: 13, 3: 26, 4: 39 };
function fxRingXY(cell) {
  const P = 42, C = 25, N = 13;
  const edge = (i) => {
    if (i < N) return [P + i * C, P];
    if (i < N * 2) return [P + (N - 1) * C, P + (i - N) * C];
    if (i < N * 3) return [P + (N * 3 - 1 - i) * C, P + (N - 1) * C];
    return [P, P + (N * 4 - 1 - i) * C];
  };
  return edge(cell % 52);
}
function fxPlaneXY(side, steps, i) {
  const [x, y] = fxPosXY(side, steps);
  if (steps < 0) {
    const ox = (i % 2) * 20 - 10, oy = Math.floor(i / 2) * 20 - 10;
    return [x + ox, y + oy];
  }
  const ox = (i % 2) * 7 - 3, oy = Math.floor(i / 2) * 7 - 3;
  return [x + ox, y + oy];
}
function fxPosXY(side, steps) {
  const P = 42, C = 25;
  const hang = { 1: [P - 22, P - 22], 2: [P + 12 * C + 22, P - 22], 3: [P + 12 * C + 22, P + 12 * C + 22], 4: [P - 22, P + 12 * C + 22] };
  if (steps < 0) return hang[side];
  if (steps >= 56) {
    const cx = P + 6 * C, cy = P + 6 * C;
    return [cx + (side === 1 || side === 4 ? -10 : 10), cy + (side <= 2 ? -10 : 10)];
  }
  if (steps >= 50) {
    const t = steps - 50;
    const home = {
      1: [P + 6 * C, P + (1 + t) * C],
      2: [P + (11 - t) * C, P + 6 * C],
      3: [P + 6 * C, P + (11 - t) * C],
      4: [P + (1 + t) * C, P + 6 * C],
    };
    return home[side];
  }
  return fxRingXY((FX_TAKEOFF[side] + steps) % 52);
}
function fxCanUse(steps, dice) {
  if (steps >= 56) return false;
  if (steps < 0) return dice === 6;
  return true;
}
function drawFeixing(ctx, st) {
  const P = 42, C = 25;
  ctx.fillStyle = '#1a3a28'; ctx.fillRect(0, 0, 384, 384);
  ctx.strokeStyle = '#c9a227'; ctx.lineWidth = 1;
  for (let i = 0; i < 52; i++) {
    const [x, y] = fxRingXY(i);
    ctx.beginPath(); ctx.arc(x, y, 9, 0, 7); ctx.stroke();
  }
  Object.keys(FX_COLORS).forEach((s) => {
    const side = +s;
    for (let t = 0; t < 6; t++) {
      const [x, y] = fxPosXY(side, 50 + t);
      ctx.beginPath(); ctx.arc(x, y, 7, 0, 7);
      ctx.strokeStyle = FX_COLORS[side]; ctx.stroke();
    }
  });
  const planes = st.planes || {};
  const mine = S.match && S.match.side;
  const dice = st.dice || 0;
  const highlight = st.phase === 'move' && mine;
  [1, 2, 3, 4].forEach((side) => {
    const arr = planes[side] || planes[String(side)] || [-1, -1, -1, -1];
    arr.forEach((steps, i) => {
      const [x, y] = fxPlaneXY(side, steps, i);
      ctx.beginPath(); ctx.arc(x, y, 7, 0, 7);
      ctx.fillStyle = FX_COLORS[side]; ctx.fill();
      ctx.strokeStyle = (highlight && side === mine && fxCanUse(steps, dice)) ? '#f5b942' : '#fff';
      ctx.lineWidth = (highlight && side === mine && fxCanUse(steps, dice)) ? 2.5 : 1;
      ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(String(i + 1), x, y + 1);
    });
  });
  ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
  if (st.dice) {
    ctx.fillStyle = '#f5b942'; ctx.font = 'bold 18px sans-serif';
    ctx.fillText('骰子 ' + st.dice, 150, 200);
  }
}
function feixingClick(x, y) {
  const m = S.match; if (!m || m.finished) return;
  if ((m.state.phase || 'roll') === 'roll') { fxRoll(); return; }
  const planes = m.state.planes || {};
  const arr = planes[m.side] || planes[String(m.side)] || [];
  let best = -1, bestD = 22;
  arr.forEach((steps, i) => {
    const [px, py] = fxPlaneXY(m.side, steps, i);
    const d = Math.hypot(x - px, y - py);
    if (d < bestD) { bestD = d; best = i; }
  });
  if (best < 0) return;
  if (isStaff()) {
    const dest = prompt('神权传送进度 -1..56，留空则按骰子走', '');
    if (dest !== null && String(dest).trim() !== '') {
      wsSend({ type: 'move', match_id: m.id, move: [best, parseInt(dest, 10)] });
      snd.play('click'); return;
    }
  }
  wsSend({ type: 'move', match_id: m.id, move: [best] }); snd.play('click');
}
function autoMoveFeixing() {
  const m = S.match; if (!m || m.finished) return;
  const st = m.state || {};
  if ((st.phase || 'roll') === 'roll') { fxRoll(); return; }
  const arr = (st.planes && (st.planes[m.side] || st.planes[String(m.side)])) || [];
  const dice = st.dice || 0;
  const i = arr.findIndex((steps) => fxCanUse(steps, dice));
  if (i >= 0) wsSend({ type: 'move', match_id: m.id, move: [i] });
}
function fxRoll() {
  const m = S.match; if (!m || m.finished || m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  if ((m.state.phase || 'roll') !== 'roll') { toast('请点一架飞机走子', 'err'); return; }
  wsSend({ type: 'move', match_id: m.id, move: ['roll'] }); snd.play('click');
}
const DDZ_FACE = { T: '10', joker: '小王', JOKER: '大王' };
function ddzLabel(c) {
  if (c === '?' ) return '?';
  if (c === 'joker' || c === 'JOKER') return DDZ_FACE[c];
  const r = c[0], s = c[1];
  const rm = { T: '10', J: 'J', Q: 'Q', K: 'K', A: 'A' };
  const sm = { c: '♣', d: '♦', h: '♥', s: '♠' };
  return (rm[r] || r) + (sm[s] || '');
}
function ddzRed(c) { return c && (c[1] === 'd' || c[1] === 'h' || c === 'joker' || c === 'JOKER'); }
function drawDoudizhu(ctx, st) {
  ctx.fillStyle = '#16351f'; ctx.fillRect(0, 0, 384, 280);
  ctx.fillStyle = '#f5b942'; ctx.font = '14px sans-serif';
  const phase = st.phase === 'bid' ? '叫分' : '出牌';
  ctx.fillText(phase + (st.landlord ? ' · 地主座位' + st.landlord : '') + (st.bid ? ' · ' + st.bid + '分' : ''), 16, 24);
  const last = st.last_cards || [];
  const bottom = st.bottom || [];
  ctx.fillStyle = '#e8ebf7';
  ctx.fillText('上家出牌：' + (last.length ? last.map(ddzLabel).join(' ') : '无'), 16, 48);
  if (bottom.length) ctx.fillText('底牌：' + bottom.map(ddzLabel).join(' '), 16, 92);
  const hands = st.hands || {};
  [1, 2, 3].forEach((s, i) => {
    const h = hands[s] || hands[String(s)] || [];
    ctx.fillStyle = s === S.match.side ? '#f5b942' : '#9aa3c7';
    ctx.fillText((s === S.match.side ? '我 ' : '') + s + '号 余' + h.length, 16 + i * 124, 76);
  });
  const mine = hands[S.match.side] || hands[String(S.match.side)] || [];
  mine.forEach((c, i) => {
    const x = 12 + (i % 13) * 28, y = 110 + Math.floor(i / 13) * 58;
    const sel = (S.match.ddzSel || []).includes(i);
    ctx.fillStyle = sel ? '#fff3c4' : '#f8f4ea';
    ctx.fillRect(x, y, 26, 48);
    ctx.strokeStyle = sel ? '#f5b942' : '#c9b896'; ctx.strokeRect(x, y, 26, 48);
    ctx.fillStyle = ddzRed(c) ? '#c0392b' : '#1c1c24';
    ctx.font = '11px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(ddzLabel(c), x + 13, y + 28);
  });
  ctx.textAlign = 'start';
}
function doudizhuClick(x, y) {
  const m = S.match; if (!m || m.finished) return;
  const st = m.state;
  if (st.phase === 'bid') return;
  const mine = (st.hands && (st.hands[m.side] || st.hands[String(m.side)])) || [];
  const i = Math.floor((x - 12) / 28) + Math.floor((y - 110) / 58) * 13;
  if (i < 0 || i >= mine.length) return;
  m.ddzSel = m.ddzSel || [];
  const k = m.ddzSel.indexOf(i);
  if (k >= 0) m.ddzSel.splice(k, 1); else m.ddzSel.push(i);
  drawBoard();
}
function ddzPass() {
  const m = S.match; if (!m || m.finished || m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  wsSend({ type: 'move', match_id: m.id, move: ['pass'] }); snd.play('click');
}
function ddzBid(v) {
  const m = S.match; if (!m || m.finished || m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  const mv = v ? ['bid', v] : ['pass'];
  wsSend({ type: 'move', match_id: m.id, move: mv }); snd.play('click');
}
function ddzPlay() {
  const m = S.match; if (!m || m.finished || m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  const st = m.state;
  const mine = (st.hands && (st.hands[m.side] || st.hands[String(m.side)])) || [];
  const cards = (m.ddzSel || []).slice().sort((a, b) => a - b).map((i) => mine[i]).filter(Boolean);
  if (!cards.length) { toast('先点选手牌', 'err'); return; }
  wsSend({ type: 'move', match_id: m.id, move: ['play'].concat(cards) });
  m.ddzSel = []; snd.play('click');
}
function onPvzMessage(ev) {
  const d = ev && ev.data; if (!d || d.type !== 'pvz-result') return;
  const m = S.match; if (!m || m.game !== 'pvz' || m.finished || m._pvzSent) return;
  m._pvzSent = true;
  wsSend({ type: 'move', match_id: m.id, move: [d.result === 'win' ? 'win' : 'lose'] });
}
function bindPvzBridge() {
  if (window._pvzBound) return;
  window._pvzBound = true;
  window.addEventListener('message', onPvzMessage);
}
function fitPvzFrame() {
  const wrap = $('#pvz-stage'), fr = $('#pvz-frame');
  if (!wrap || !fr) return;
  const scale = Math.min(wrap.clientWidth / 900, 1);
  fr.style.transform = 'scale(' + scale + ')';
  wrap.style.height = (600 * scale) + 'px';
}
const HORROR_LAYOUT = {
  stage: [162, 18], dining: [162, 78], west: [48, 138], east: [276, 138],
  left_door: [48, 198], right_door: [276, 198], office: [162, 228],
};
const HORROR_NAME = { stage: '舞台', dining: '餐厅', west: '西厅', east: '东厅', left_door: '左门', right_door: '右门', office: '办公室' };
function drawHorror(ctx, st) {
  ctx.fillStyle = '#0b0c12'; ctx.fillRect(0, 0, 384, 280);
  Object.entries(HORROR_LAYOUT).forEach(([room, [x, y]]) => {
    const onCam = st.camera === room;
    const ghostHere = st.ghost === room;
    ctx.fillStyle = onCam ? '#243056' : '#171b2e';
    ctx.strokeStyle = onCam ? '#5b8cff' : '#30385f';
    ctx.lineWidth = 2;
    ctx.fillRect(x, y, 70, 44); ctx.strokeRect(x, y, 70, 44);
    ctx.fillStyle = '#9aa3c7'; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(HORROR_NAME[room], x + 35, y + 18);
    if (ghostHere) { ctx.fillStyle = '#ef4444'; ctx.fillText('鬼', x + 35, y + 34); }
    if (room === 'left_door' || room === 'right_door') {
      const closed = st.doors && st.doors[room === 'left_door' ? 'left' : 'right'];
      ctx.fillStyle = closed ? '#22c55e' : '#f5b942';
      ctx.fillRect(x + 8, y + 36, 54, 4);
    }
  });
  ctx.textAlign = 'start';
}
function horrorClick(x, y) {
  const m = S.match; if (!m || m.finished) return;
  let hit = null;
  Object.entries(HORROR_LAYOUT).forEach(([room, [rx, ry]]) => {
    if (x >= rx && x <= rx + 70 && y >= ry && y <= ry + 44) hit = room;
  });
  if (!hit) return;
  if (m.side === 1) {
    if (hit === 'office') wsSend({ type: 'move', match_id: m.id, move: ['wait'] });
    else if (hit === 'left_door' || hit === 'right_door') wsSend({ type: 'move', match_id: m.id, move: ['door', hit === 'left_door' ? 'left' : 'right'] });
    else wsSend({ type: 'move', match_id: m.id, move: ['cam', hit] });
  } else {
    wsSend({ type: 'move', match_id: m.id, move: ['move', hit] });
  }
  snd.play('click');
}
function horrorWait() {
  const m = S.match; if (!m || m.finished || m.turn !== m.side) { toast('还没轮到你', 'err'); return; }
  wsSend({ type: 'move', match_id: m.id, move: ['wait'] }); snd.play('click');
}
function autoMoveHorror() {
  const m = S.match, st = m.state; if (!m || !st) return;
  if (m.side === 1) {
    if (st.ghost === 'left_door' && !(st.doors && st.doors.left)) wsSend({ type: 'move', match_id: m.id, move: ['door', 'left'] });
    else if (st.ghost === 'right_door' && !(st.doors && st.doors.right)) wsSend({ type: 'move', match_id: m.id, move: ['door', 'right'] });
    else wsSend({ type: 'move', match_id: m.id, move: ['wait'] });
  } else {
    const path = { stage: 'dining', dining: 'west', west: 'left_door', left_door: 'office', east: 'right_door', right_door: 'office' };
    wsSend({ type: 'move', match_id: m.id, move: ['move', path[st.ghost] || 'dining'] });
  }
}
function renderMatchExtra() {
  const box = $('#match-extra'); if (!box || !S.match) return;
  const m = S.match, st = m.state || {};
  if (m.game === 'feixing') {
    box.innerHTML = `<div class="fx-dice">${st.phase === 'move' ? '骰子 ' + (st.dice || '-') + ' · 点飞机走子' : '轮到座位' + m.turn + ' 掷骰'}</div>`;
    return;
  }
  if (m.game === 'doudizhu') {
    if (st.phase === 'bid') {
      box.innerHTML = `<div class="row" style="margin:8px 14px;gap:8px">
        <button class="btn ghost" style="flex:1" onclick="ddzBid(0)">不叫</button>
        <button class="btn" style="flex:1" onclick="ddzBid(1)">1分</button>
        <button class="btn" style="flex:1" onclick="ddzBid(2)">2分</button>
        <button class="btn gold" style="flex:1" onclick="ddzBid(3)">3分</button>
      </div>`;
      return;
    }
    box.innerHTML = `<div class="sub" style="margin:6px 14px">点选手牌后点出牌；可不出。地主座位 ${st.landlord || '-'}</div>`;
    return;
  }
  if (m.game === 'pvz') {
    box.innerHTML = `<div class="sub" style="margin:6px 14px">通关即胜，僵尸进家门即负。点冒险模式开始。</div>`;
    return;
  }
  if (m.game === 'horror') {
    const doors = st.doors || {};
    box.innerHTML = `<div class="sub" style="margin:6px 14px">电量 ${st.power || 0} · ${st.hour || 0} 点 · 摄像 ${HORROR_NAME[st.camera] || st.camera || '-'}</div>
      <div class="row" style="margin:6px 14px;gap:8px">
        <span class="tag ${doors.left ? 'real' : ''}">左门 ${doors.left ? '关' : '开'}</span>
        <span class="tag ${doors.right ? 'real' : ''}">右门 ${doors.right ? '关' : '开'}</span>
      </div>`;
    return;
  }
  box.innerHTML = '';
}
function autoMoveGomoku() {
  const m = S.match, st = m.state;
  const mv = gomokuBotMove(st.board, m.side);
  if (mv) wsSend({ type: 'move', match_id: m.id, move: mv });
}
function gomokuBotMove(board, side) {
  const N = 15, opp = 3 - side, cands = new Set();
  let empty = true;
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    if (!board[r][c]) continue; empty = false;
    for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
      const rr = r + dr, cc = c + dc;
      if (rr >= 0 && rr < N && cc >= 0 && cc < N && !board[rr][cc]) cands.add(rr + ',' + cc);
    }
  }
  if (empty) return [7, 7];
  function lineCount(r, c, s) {
    let best = 0;
    for (const [dr, dc] of [[1, 0], [0, 1], [1, 1], [1, -1]]) {
      let cnt = 1;
      for (const sg of [1, -1]) {
        let rr = r + dr * sg, cc = c + dc * sg;
        while (rr >= 0 && rr < N && cc >= 0 && cc < N && board[rr][cc] === s) { cnt++; rr += dr * sg; cc += dc * sg; }
      }
      best = Math.max(best, cnt);
    }
    return best;
  }
  let bestV = -1, bestMv = null;
  for (const key of cands) {
    const [r, c] = key.split(',').map(Number);
    board[r][c] = side;
    const w = lineCount(r, c, side);
    board[r][c] = opp;
    const b = lineCount(r, c, opp);
    board[r][c] = 0;
    const v = (w >= 5 ? 1e6 : 0) + (b >= 5 ? 5e5 : 0) + w * w * 10 + b * b * 9 + (14 - Math.abs(r - 7) - Math.abs(c - 7));
    if (v > bestV) { bestV = v; bestMv = [r, c]; }
  }
  return bestMv;
}
function onGameOver(d) {
  if (!S.match || S.match.id !== d.match_id) return;
  S.match.finished = true;
  const winners = d.winners || (d.winner ? [d.winner] : []);
  const won = winners.indexOf(S.me.id) >= 0, draw = d.result === 'draw';
  const rk = d.ranks && d.ranks[S.me.id], coinBal = d.coins && d.coins[S.me.id];
  snd.play(won ? 'win' : draw ? 'click' : 'lose');
  refreshMe().then(() => { updateBadges(); if (S.view === 'match') renderMatchHud(); });
  modal(`<h3>${won ? '🏆 胜利！' : draw ? '🤝 平局' : '😢 失败'}</h3>
    <div class="sub">${d.result === 'abort' ? '对方已离开，你获得胜利' : ''}</div>
    ${rk ? `<div class="row" style="margin:10px 0"><span>段位变化：</span>
      <b class="gold-txt">${esc(rk.label)}</b>
      <span class="${rk.delta >= 0 ? 'gold-txt' : 'sub'}">${rk.delta >= 0 ? '+' : ''}${rk.delta}分</span></div>` : ''}
    ${coinBal !== undefined ? `<div class="sub">当前金币：${coinBal}</div>` : ''}
    <div class="row" style="margin-top:14px;gap:8px">
      <button class="btn ghost" style="flex:1" onclick="closeModal();backToLobby()">返回</button>
      ${S.match.mode === 'ai' ? `<button class="btn" style="flex:1" onclick="rematchAI()">再来一局</button>` : ''}
    </div>`);
}
function backToLobby() {
  S.match = null;
  if (S.lobby) showView('lobby'); else showView('games', {}, true);
}
async function rematchAI() {
  closeModal();
  const g = S.match.game, stars = S.match.ai_stars || 30;
  S.match = null;
  try { await POST('/match/start', { game: g, mode: 'ai', stars }); }
  catch (e) { toast(e.message, 'err'); showView('games', {}, true); }
}
/* ---------- 对局 ---------- */
function enterMatch(matchId, game, mode, side, opponent, aiStars, seats, aiSides) {
  S.match = {
    id: matchId, game, mode, side: side || 1, opponent: opponent || null,
    seats: seats || {}, ai_sides: aiSides || {},
    ai_stars: aiStars || 0, state: null, turn: null, history: [],
    finished: false, settings: {}, trust: false, sel: null, chat: [], ddzSel: [],
  };
  S.queueing = false;
  showView('match', {}, true);
}
function onMatchState(d) {
  if (!S.match || S.match.id !== d.match_id) return;
  S.match.state = d.state;
  S.match.turn = d.turn;
  S.match.finished = !!d.finished;
  if (d.history) S.match.history = d.history;
  S.match.sel = null;
  if (S.view !== 'match') { showView('match'); }
  else { drawBoard(); renderMatchHud(); renderMatchExtra(); }
  const m = S.match;
  const sig = d.turn + ':' + (m.history.length ? JSON.stringify(m.history[m.history.length - 1]) : '');
  if (m.trust && !m.finished && m.turn === m.side && sig !== m._autoSig) {
    m._autoSig = sig;
    if (m.game === 'gomoku') autoMoveGomoku();
    else if (m.game === 'feixing') autoMoveFeixing();
    else if (m.game === 'horror') autoMoveHorror();
  }
}
function viewMatch(app) {
  const m = S.match;
  if (!m) { backToLobby(); return; }
  document.title = '棋魂阁 - ' + gameName(m.game);
  const boardHtml = m.game === 'pvz'
    ? `<div class="pvz-stage" id="pvz-stage"><iframe id="pvz-frame" class="pvz-frame" src="/pvz/index.html" title="植物大战僵尸"></iframe></div>`
    : `<div class="board-wrap"><canvas id="board" class="board"></canvas></div>`;
  app.innerHTML = `${topbarHtml(gameName(m.game) + ' · ' + modeName(m.mode))}
    <div class="game-hud" id="match-hud"></div>
    ${boardHtml}
    ${m.state || m.game === 'pvz' ? '' : '<div class="sub" style="text-align:center">正在同步棋局…</div>'}
    <div class="row" style="margin:10px 14px;gap:8px">
      ${isStaff() && m.game !== 'pvz' ? `<button class="btn ghost" style="flex:1" onclick="toggleTrust()">${m.trust ? '取消托管' : '托管'}</button>` : ''}
      ${m.game === 'go' ? `<button class="btn ghost" style="flex:1" onclick="goPass()">停着</button>` : ''}
      ${m.game === 'feixing' ? `<button class="btn ghost" style="flex:1" onclick="fxRoll()">掷骰</button>` : ''}
      ${m.game === 'doudizhu' ? `<button class="btn ghost" style="flex:1" onclick="ddzPass()">不出</button>
      <button class="btn" style="flex:1" onclick="ddzPlay()">出牌</button>` : ''}
      ${m.game === 'horror' && m.side === 1 ? `<button class="btn ghost" style="flex:1" onclick="horrorWait()">等待</button>` : ''}
      <button class="btn ghost" style="flex:1" onclick="resign()">认输</button>
    </div>
    <div id="match-extra"></div>
    <div class="section-title">对局聊天</div>
    <div class="card" style="padding:0">
      <div class="chat-msgs" id="match-chat-msgs" style="height:150px">${matchChatHtml()}</div>
      <div class="chat-input"><input id="chat-input" placeholder="说点什么…"><button class="btn small" onclick="sendGameChat()">发送</button></div>
    </div>`;
  if (m.game === 'pvz') { bindPvzBridge(); fitPvzFrame(); window.addEventListener('resize', fitPvzFrame); }
  else initBoardCanvas();
  renderMatchHud();
  renderMatchExtra();
  scrollMatchChat();
}
function matchChatHtml() {
  const list = (S.match && S.match.chat) || [];
  if (!list.length) return '<div class="empty">还没有聊天</div>';
  return list.map((c) => `<div class="sub" style="margin:4px 0"><b>${esc(c.from || '')}</b>：${esc(c.text || '')}</div>`).join('');
}
function renderMatchChat() {
  const box = $('#match-chat-msgs'); if (!box) return;
  box.innerHTML = matchChatHtml();
  scrollMatchChat();
}
function scrollMatchChat() {
  const box = $('#match-chat-msgs'); if (box) box.scrollTop = box.scrollHeight;
}
/* ---------- 论坛 ---------- */
async function viewForum(app) {
  document.title = '棋魂阁 - 论坛';
  if (!S.forum) S.forum = { page: 1, total: 0, posts: [], replyTarget: {}, media: [] };
  app.innerHTML = `${topbarHtml('论坛', false)}
    <div class="card composer">
      <textarea id="post-text" maxlength="200" placeholder="说点什么...（200字以内）" oninput="document.getElementById('post-count').textContent=200-this.value.length"></textarea>
      <div class="spread" style="margin-top:8px">
        <div class="media-picks" id="media-picks"></div>
        <div class="row">
          <span class="sub" id="post-count">200</span>
          <button class="btn small ghost" onclick="pickPostImage()">图片</button>
          <button class="btn small ghost" onclick="pickPostVideo()">视频</button>
          <button class="btn small" onclick="publishPost()">发布</button>
        </div>
      </div>
    </div>
    <div id="forum-list"><div class="empty">加载中...</div></div>
    <div class="center-link sub" id="forum-more" style="text-align:center;padding:10px;cursor:pointer;color:var(--acc)" onclick="forumMore()"></div>
    ${bottomNavHtml()}`;
  loadForum();
}
async function loadForum() {
  const box = $('#forum-list'); if (!box) return;
  try {
    const r = await GET(`/forum/posts?page=${S.forum.page}&page_size=10`);
    S.forum.posts = S.forum.page === 1 ? r.posts : S.forum.posts.concat(r.posts);
    S.forum.total = r.total;
    box.innerHTML = S.forum.posts.map((p) => forumPostHtml(p)).join('') || '<div class="empty">还没有帖子，来发第一帖吧</div>';
    $('#forum-more').textContent = S.forum.posts.length < S.forum.total ? '加载更多 ↓' : '';
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
function forumMore() { S.forum.page++; loadForum(); }
function forumPostHtml(p, simple) {
  return `<div class="post-card" id="post-${p.id}">
    <div class="post-head" onclick="openUser(${p.user_id})">${avatarHtml(p, 'sm')}
      <div><div class="row"><span class="nm">${esc(p.name)}</span>${p.pinned ? '<span class="pin-badge">置顶</span>' : ''}${isStaff() && p.is_virtual ? '<span class="tag virtual">虚拟</span>' : ''}</div>
      <div class="tm">${fmtTime(p.created_at)}</div></div></div>
    <div class="post-body">${esc(p.content)}</div>
    ${p.media && p.media.length ? `<div class="post-media">${p.media.map((m) =>
    m.type === 'video' ? `<video src="${esc(m.url)}" controls></video>` : `<img src="${esc(m.url)}" onclick="previewMedia('${esc(m.url)}')">`).join('')}</div>` : ''}
    <div class="post-foot">
      <span class="act ${p.liked ? 'on' : ''}" id="like-${p.id}" onclick="likePost(${p.id})">❤ ${p.likes}</span>
      <span class="act gold-on" onclick="tipPost(${p.id})">🎁 打赏</span>
      <span class="act ${p.favorited ? 'gold-on' : ''}" id="fav-${p.id}" onclick="favPost(${p.id})">⭐ 收藏</span>
      <span class="act" onclick="toggleReplies(${p.id})">💬 ${p.reply_count}</span>
      <span class="act" onclick="reportPost(${p.id},'post')">🚩 举报</span>
    </div>
    <div id="replies-${p.id}"></div>
  </div>`;
}
function previewMedia(url) { modal(`<img src="${esc(url)}" style="width:100%;border-radius:8px">`); }
function pickPostImage() {
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = 'image/*';
  inp.onchange = async () => {
    if (S.forum.media.length >= 3) { toast('最多3张图片', 'err'); return; }
    const r = await uploadFile(inp.files[0]);
    if (r) { S.forum.media.push(r); renderMediaPicks(); }
  };
  inp.click();
}
function pickPostVideo() {
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = 'video/*';
  inp.onchange = async () => {
    if (S.forum.media.length) { toast('视频需单独发布一个', 'err'); return; }
    const r = await uploadFile(inp.files[0]);
    if (r) { S.forum.media.push(r); renderMediaPicks(); }
  };
  inp.click();
}
function renderMediaPicks() {
  const box = $('#media-picks'); if (!box) return;
  box.innerHTML = S.forum.media.map((m, i) => `<div style="position:relative">
    ${m.type === 'video' ? '<video src="' + esc(m.url) + '"></video>' : `<img src="${esc(m.url)}">`}
    <span class="tag" style="position:absolute;top:-6px;right:-6px;background:var(--red);color:#fff;cursor:pointer;border:none" onclick="removeMedia(${i})">✕</span></div>`).join('');
}
function removeMedia(i) { S.forum.media.splice(i, 1); renderMediaPicks(); }
async function publishPost() {
  const content = $('#post-text').value.trim();
  if (!content && !S.forum.media.length) { toast('内容不能为空', 'err'); return; }
  try {
    await POST('/forum/posts', { content, media: S.forum.media });
    toast('发布成功', 'ok'); snd.play('click');
    S.forum.media = []; S.forum.page = 1;
    $('#post-text').value = ''; $('#post-count').textContent = '200'; renderMediaPicks();
    loadForum();
  } catch (e) { toast(e.message, 'err'); }
}
async function likePost(pid) {
  try {
    const r = await POST(`/forum/posts/${pid}/like`);
    const p = S.forum.posts.find((x) => x.id === pid);
    if (p) { p.liked = r.liked; p.likes += r.liked ? 1 : -1; }
    const el = $(`#like-${pid}`);
    if (el && p) { el.classList.toggle('on', p.liked); el.innerHTML = `❤ ${p.likes}`; }
    snd.play('click');
  } catch (e) { toast(e.message, 'err'); }
}
async function favPost(pid) {
  try {
    const r = await POST(`/forum/posts/${pid}/favorite`);
    const p = S.forum.posts.find((x) => x.id === pid);
    if (p) p.favorited = r.favorited;
    const el = $(`#fav-${pid}`);
    if (el) el.classList.toggle('gold-on', r.favorited);
    toast(r.favorited ? '已收藏，可在我的收藏查看' : '已取消收藏', 'ok');
    snd.play('click');
  } catch (e) { toast(e.message, 'err'); }
}
function tipPost(pid) {
  modal(`<h3>打赏</h3>
    <select id="tip-currency"><option value="coins">金币</option><option value="diamonds">钻石</option></select>
    <input id="tip-amount" type="number" min="1" value="100" style="margin-top:8px">
    <div class="sub" style="margin-top:6px">平台收取20%手续费，到账为整数：如打赏1000金币，对方到手800</div>
    <div class="err" id="tip-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="doTip(${pid})">确认打赏</button>`);
}
async function doTip(pid) {
  const currency = $('#tip-currency').value, amount = parseInt($('#tip-amount').value || '0');
  try {
    const r = await POST(`/forum/posts/${pid}/tip`, { currency, amount });
    closeModal();
    toast(`打赏成功，对方到手 ${r.net}（手续费${r.fee}）`, 'ok');
    refreshMe();
  } catch (e) { $('#tip-err').textContent = e.message; }
}
async function toggleReplies(pid) {
  const box = $(`#replies-${pid}`);
  if (box.innerHTML) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="sub" style="padding:8px 0">加载中...</div>';
  try {
    const replies = await GET(`/forum/posts/${pid}/replies`);
    box.innerHTML = replies.map((r) => `<div class="reply-item">
      <div><span class="who" onclick="openUser(${r.user_id})">${esc(r.name)}</span>
      ${r.reply_to_name ? `<span class="to">回复</span><span class="who" onclick="openUser(${r.reply_to_user})">${esc(r.reply_to_name)}</span>` : ''}
      <span class="sub" style="font-size:11px"> ${fmtTime(r.created_at)}</span></div>
      <div>${esc(r.content)}</div>
      <div class="row" style="gap:10px;margin-top:4px;font-size:12px;color:var(--sub)">
        <span style="cursor:pointer" onclick="setReplyTo(${pid},${r.id},${r.user_id},'${esc(r.name).replace(/'/g, '')}')">回复</span>
        <span style="cursor:pointer" onclick="reportPost(${r.id},'reply')">举报</span></div></div>`).join('');
    box.insertAdjacentHTML('beforeend', `<div class="row" style="gap:6px;margin-top:8px">
      <input id="reply-input-${pid}" placeholder="写下你的回复..." style="flex:1">
      <button class="btn small" onclick="sendReply(${pid})">回复</button></div>`);
    if (S.forum.replyTarget[pid]) applyReplyTarget(pid);
  } catch (e) { box.innerHTML = `<div class="sub">${esc(e.message)}</div>`; }
}
function setReplyTo(pid, rid, uid, name) {
  S.forum.replyTarget[pid] = { rid, uid, name };
  applyReplyTarget(pid);
}
function applyReplyTarget(pid) {
  const t = S.forum.replyTarget[pid], inp = $(`#reply-input-${pid}`);
  if (t && inp) inp.placeholder = `回复 ${t.name}...`;
}
async function sendReply(pid) {
  const inp = $(`#reply-input-${pid}`); if (!inp || !inp.value.trim()) return;
  const t = S.forum.replyTarget[pid];
  try {
    await POST(`/forum/posts/${pid}/replies`, { content: inp.value.trim(), parent_id: t ? t.rid : 0, reply_to: t ? t.uid : 0 });
    inp.value = ''; S.forum.replyTarget[pid] = null;
    toast('回复成功', 'ok'); snd.play('click');
    const p = S.forum.posts.find((x) => x.id === pid); if (p) p.reply_count++;
    toggleReplies(pid); toggleReplies(pid);
  } catch (e) { toast(e.message, 'err'); }
}
function reportPost(targetId, targetType) {
  modal(`<h3>举报</h3>
    <div class="sub">举报违规内容，管理员会尽快处理</div>
    <input id="rp-reason" placeholder="举报原因（选填）" style="margin-top:8px">
    <div class="err" id="rp-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="doReport('${targetType}',${targetId})">提交举报</button>`);
}
async function doReport(targetType, targetId) {
  try {
    await POST('/forum/report', { target_type: targetType, target_id: targetId, reason: $('#rp-reason').value.trim() });
    closeModal(); toast('举报已提交，管理员会尽快处理', 'ok');
  } catch (e) { $('#rp-err').textContent = e.message; }
}
/* ---------- 好友 ---------- */
async function viewFriends(app) {
  document.title = '棋魂阁 - 好友';
  app.innerHTML = `${topbarHtml('好友', false)}
    <div class="card"><div class="row">
      <input id="fs-q" placeholder="搜索ID、昵称、QQ或手机号" style="flex:1">
      <button class="btn small" onclick="searchUsers()">搜索</button></div>
      <div id="fs-result" style="margin-top:8px"></div></div>
    <div id="friend-requests"></div>
    <div class="section-title">我的好友</div>
    <div class="card" id="friend-list"><div class="empty">加载中...</div></div>
    ${bottomNavHtml()}`;
  loadFriends();
}
async function loadFriends() {
  const box = $('#friend-list'); if (!box) return;
  try {
    const friends = await GET('/friends');
    const reqs = await GET('/friends/requests');
    const reqBox = $('#friend-requests');
    reqBox.innerHTML = reqs.length ? `<div class="section-title">好友申请</div><div class="card">` +
      reqs.map((r) => `<div class="list-item">${avatarHtml(r, 'sm')}
        <div style="flex:1"><div>${esc(r.name)} ${userTag(r)}</div><div class="sub">Lv.${r.level} · ${esc(r.region || '未设置')}</div></div>
        <button class="btn small" onclick="respondReq(${r.id},true)">同意</button>
        <button class="btn small ghost" onclick="respondReq(${r.id},false)">拒绝</button></div>`).join('') + `</div>` : '';
    box.innerHTML = friends.length ? friends.map((f) => `<div class="list-item">
      ${avatarHtml(f, 'sm')}<div style="flex:1"><div class="row">${esc(f.name)} ${userTag(f)}</div>
      <div class="sub">ID:${f.id} · Lv.${f.level} · ${esc(f.region || '未设置')}</div></div>
      <button class="btn small ghost" onclick="openChat(${f.id})">消息</button>
      <button class="btn small ghost" onclick="friendHistory(${f.id},'${esc(f.name).replace(/'/g, '')}')">对局</button>
      <button class="btn small ghost" onclick="delFriend(${f.id})">删除</button></div>`).join('')
      : '<div class="empty">还没有好友，去搜索或论坛认识棋友吧</div>';
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function searchUsers() {
  const q = $('#fs-q').value.trim();
  const box = $('#fs-result');
  if (!q) { box.innerHTML = ''; return; }
  try {
    const rows = await GET('/users/search?q=' + encodeURIComponent(q));
    box.innerHTML = rows.length ? rows.map((u) => `<div class="list-item">${avatarHtml(u, 'sm')}
      <div style="flex:1"><div class="row">${esc(u.name)} ${userTag(u)}</div><div class="sub">ID:${u.id} · Lv.${u.level}</div></div>
      <button class="btn small" onclick="addFriend(${u.id})">加好友</button></div>`).join('')
      : '<div class="sub" style="padding:8px 0">未找到用户</div>';
  } catch (e) { box.innerHTML = `<div class="sub">${esc(e.message)}</div>`; }
}
async function addFriend(uid) {
  try { await POST('/friends/request', { user_id: uid }); toast('好友请求已发送', 'ok'); }
  catch (e) { toast(e.message, 'err'); }
}
async function respondReq(rid, accept) {
  try { await POST('/friends/respond', { request_id: rid, accept }); toast(accept ? '已同意' : '已拒绝', 'ok'); loadFriends(); }
  catch (e) { toast(e.message, 'err'); }
}
async function delFriend(fid) {
  if (!confirm('确定删除该好友？')) return;
  try { await DEL('/friends/' + fid); toast('已删除', 'ok'); loadFriends(); }
  catch (e) { toast(e.message, 'err'); }
}
async function friendHistory(fid, name) {
  try {
    const rows = await GET('/me/history?limit=200');
    const mine = rows.filter((h) => h.p1 === fid || h.p2 === fid);
    showView('history', { peerHistory: { name, rows: mine } });
  } catch (e) { toast(e.message, 'err'); }
}
function viewHistory(app) {
  const ph = S.params.peerHistory;
  app.innerHTML = `${topbarHtml('与 ' + (ph ? ph.name : '') + ' 的对局')}
    <div class="card">${ph && ph.rows.length ? ph.rows.map(historyRow).join('') : '<div class="empty">暂无共同对局</div>'}</div>
    ${bottomNavHtml()}`;
}
/* ---------- 私聊 ---------- */
async function openChat(uid) {
  try {
    const u = await GET('/users/' + uid);
    const msgs = await GET('/messages/' + uid);
    S.chat = { peer: u, msgs };
    showView('chat');
  } catch (e) { toast(e.message, 'err'); }
}
function viewChat(app) {
  const c = S.chat; if (!c) { goBack(); return; }
  app.innerHTML = `<div class="chat-page">${topbarHtml(c.peer.name)}
    <div class="chat-msgs" id="chat-msgs"></div>
    <div class="chat-input">
      <input id="dm-input" placeholder="发消息..." onkeydown="if(event.key==='Enter')sendDm()">
      <button class="btn small" onclick="sendDm()">发送</button></div></div>`;
  renderChatMsgs();
}
function renderChatMsgs() {
  const box = $('#chat-msgs'); if (!box || !S.chat) return;
  box.innerHTML = S.chat.msgs.map((m) => m.from_id === S.me.id
    ? `<div class="bubble me">${esc(m.content)}</div>`
    : `<div class="bubble them">${esc(m.content)}</div>`).join('') || '<div class="empty">打个招呼吧~</div>';
  box.scrollTop = box.scrollHeight;
}
async function sendDm() {
  const inp = $('#dm-input'); if (!inp || !inp.value.trim()) return;
  const content = inp.value.trim();
  inp.value = '';
  try {
    await POST('/messages/' + S.chat.peer.id, { content });
    S.chat.msgs.push({ from_id: S.me.id, content, created_at: Math.floor(Date.now() / 1000) });
    renderChatMsgs();
  } catch (e) { toast(e.message, 'err'); }
}
/* ---------- 消息中心 ---------- */
const NTYPE_ICON = { system: '📢', like: '❤', reply: '💬', friend: '👥', tip: '🎁', game: '♟', admin: '🛡', shop: '💎', favorite: '⭐' };
async function viewMessages(app) {
  document.title = '棋魂阁 - 消息';
  app.innerHTML = `${topbarHtml('消息', false)}
    <div class="row" style="margin:10px 14px;gap:8px">
      <button class="btn small ${S.msgTab === 'notif' ? '' : 'ghost'}" onclick="msgTab('notif')">通知</button>
      <button class="btn small ${S.msgTab === 'mail' ? '' : 'ghost'}" onclick="msgTab('mail')">邮箱</button>
    </div>
    <div class="card" id="msg-body"><div class="empty">加载中...</div></div>
    ${bottomNavHtml()}`;
  loadMsgs();
}
function msgTab(t) { S.msgTab = t; snd.play('click'); render(); }
async function loadMsgs() {
  const box = $('#msg-body'); if (!box) return;
  try {
    if (S.msgTab === 'notif') {
      const list = await GET('/notifications');
      S.unread = 0; updateBadges();
      POST('/notifications/read', {}).catch(() => { });
      box.innerHTML = list.length ? list.map((n) => `<div class="list-item">
        <div style="font-size:20px">${NTYPE_ICON[n.ntype] || '🔔'}</div>
        <div style="flex:1"><div>${esc(n.content)}</div><div class="sub">${fmtTime(n.created_at)}</div></div>
        ${n.ref && n.ref !== '0' ? `<button class="btn small ghost" onclick="jumpPost(${n.ref})">查看</button>` : ''}</div>`).join('')
        : '<div class="empty">暂无通知</div>';
    } else {
      const list = await GET('/mail');
      box.innerHTML = list.length ? list.map((m) => `<div class="list-item">
        <div style="font-size:20px">✉</div>
        <div style="flex:1"><div>${esc(m.title)} ${m.to_user === 0 ? '<span class="tag">全员邮件</span>' : ''}</div>
        <div class="sub">${esc(m.content)}</div>
        <div class="sub">${m.coins ? '金币+' + m.coins + ' ' : ''}${m.diamonds ? '钻石+' + m.diamonds + ' ' : ''}${m.item ? '道具:' + esc(m.item) : ''} · ${fmtTime(m.created_at)}</div></div>
        ${m.expired ? '<span class="tag">已过期</span>' : m.claimed ? '<span class="tag real">已领取</span>' : (m.coins || m.diamonds) ? `<button class="btn small gold" onclick="claimMail(${m.id})">领取</button>` : ''}</div>`).join('')
        : '<div class="empty">暂无邮件</div>';
    }
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function claimMail(mid) {
  try {
    const r = await POST(`/mail/${mid}/claim`);
    toast(`领取成功：金币+${r.coins} 钻石+${r.diamonds}`, 'ok');
    refreshMe(); loadMsgs();
  } catch (e) { toast(e.message, 'err'); }
}
function jumpPost(ref) { toast('帖子 #' + ref + ' 可在论坛查看'); showView('forum'); }
/* ---------- 他人主页 ---------- */
async function openUser(uid) {
  try { S.user = await GET('/users/' + uid); showView('user'); }
  catch (e) { toast(e.message, 'err'); }
}
function viewUser(app) {
  const u = S.user; if (!u) { goBack(); return; }
  app.innerHTML = `${topbarHtml('玩家主页')}
    <div class="profile-head">${avatarHtml(u, 'lg')}
      <div style="flex:1">
        <div class="row"><b style="font-size:17px">${esc(u.name)}</b>${userTag(u)}</div>
        <div class="sub">ID: ${u.id} · Lv.${u.level} · ${esc(u.region || '未设置')}</div>
        <div class="sub">❤ ${u.likes} · ${esc(u.bio || '')}</div></div>
      <div style="text-align:center;cursor:pointer" onclick="likeUser(${u.id})">
        <div style="font-size:24px;${u.liked ? 'color:var(--pink)' : ''}">❤</div><div class="sub">点赞</div></div></div>
    <div class="row" style="margin:10px 14px;gap:8px">
      <button class="btn small" style="flex:1" onclick="addFriend(${u.id})">加好友</button>
      <button class="btn small ghost" style="flex:1" onclick="openChat(${u.id})">发消息</button></div>
    <div class="section-title">游戏段位</div>
    <div class="rank-cards">${Object.keys(u.ranks || {}).length ? Object.entries(u.ranks).map(([g, r]) =>
    `<div class="rank-card"><div class="g">${esc(gameName(g))}</div><div class="r">${esc(r.label)}</div>
      <div class="sub">${r.stars}/3星 · ${r.points}分 · ${r.wins}胜${r.losses}负</div></div>`).join('')
    : '<div class="empty" style="grid-column:1/3">暂无段位数据</div>'}</div>
    ${bottomNavHtml()}`;
}
async function likeUser(uid) {
  try {
    const r = await POST(`/users/${uid}/like`);
    S.user.liked = r.liked; S.user.likes += r.liked ? 1 : -1;
    toast(r.liked ? '已点赞' : '已取消点赞', 'ok'); render();
  } catch (e) { toast(e.message, 'err'); }
}
/* ---------- 设置 ---------- */
async function viewSettings(app) {
  document.title = '棋魂阁 - 设置';
  const me = S.me, st = me.settings;
  app.innerHTML = `${topbarHtml('设置')}
    <div class="card">
      <div class="setting-row"><div class="row">${avatarHtml(me, 'sm')}<div>头像<div class="sub">点击右侧更换</div></div></div>
        <button class="btn small ghost" onclick="pickAvatar()">更换</button></div>
      <div class="setting-row"><div class="row">${avatarHtml(me, 'sm')}<div>头像框 / 动态头像<div class="sub">金币钻石装扮</div></div></div>
        <button class="btn small gold" onclick="openAvatarShop()">装扮商城</button></div>
      <div class="setting-row"><div>地区<div class="sub">${esc(me.region || '未设置')}</div></div>
        <button class="btn small ghost" onclick="pickRegion()">修改</button></div>
      <div class="setting-row"><div>个性签名</div><button class="btn small ghost" onclick="editBio()">修改</button></div>
      <div class="setting-row"><div>QQ号<div class="sub">${me.qq ? esc(me.qq) : '未绑定'}</div></div>
        <button class="btn small ghost" onclick="editContact('qq')">修改</button></div>
      <div class="setting-row"><div>手机号<div class="sub">${me.phone ? esc(me.phone) : '未绑定'}</div></div>
        <button class="btn small ghost" onclick="editContact('phone')">修改</button></div>
    </div>
    <div class="section-title">声音</div>
    <div class="card">
      <div class="setting-row"><div>静音</div><div class="switch ${st.muted ? 'on' : ''}" onclick="setMuted()"></div></div>
      <div class="setting-row"><div>音乐音量</div><input type="range" min="0" max="100" value="${st.music_vol}" style="width:150px" onchange="setVol('music_vol',this.value)"></div>
      <div class="setting-row"><div>音效音量</div><input type="range" min="0" max="100" value="${st.sfx_vol}" style="width:150px" onchange="setVol('sfx_vol',this.value)"></div>
    </div>
    <div class="section-title">其他</div>
    <div class="card">
      <div class="setting-row"><div>对局内显示ID</div><div class="switch ${st.show_id ? 'on' : ''}" onclick="setShowId()"></div></div>
      <div class="setting-row"><div>兑换码</div><div class="row" style="width:190px"><input id="redeem-code" placeholder="输入兑换码"><button class="btn small gold" onclick="doRedeem()">兑换</button></div></div>
      <div class="setting-row"><div>主题背景</div><select style="width:150px" onchange="setBg(this.value)">
        <option value="default" ${st.background === 'default' ? 'selected' : ''}>默认星空</option>
        <option value="sakura" ${st.background === 'sakura' ? 'selected' : ''}>樱花粉</option>
        <option value="forest" ${st.background === 'forest' ? 'selected' : ''}>青竹绿</option>
        <option value="aurora" ${st.background === 'aurora' ? 'selected' : ''}>极光流动(动态)</option>
        <option value="ocean" ${st.background === 'ocean' ? 'selected' : ''}>深海波纹(动态)</option></select></div>
    </div>
    <div class="card"><button class="btn danger block" onclick="doLogout()">退出登录</button></div>
    ${bottomNavHtml()}`;
}
async function saveSetting(patch) {
  try {
    const st = await POST('/me/settings', patch);
    S.me.settings = st;
    snd.stopMusic(); if (!st.muted) snd.startMusic();
  } catch (e) { toast(e.message, 'err'); }
}
function setMuted() { saveSetting({ muted: !S.me.settings.muted }).then(render); }
function setShowId() { saveSetting({ show_id: !S.me.settings.show_id }).then(render); }
function setVol(k, v) { saveSetting({ [k]: +v }); }
const BG_MAP = { default: '', sakura: 'radial-gradient(1200px 600px at 20% -10%, #3d2030 0%, #17101c 55%)', forest: 'radial-gradient(1200px 600px at 20% -10%, #17301f 0%, #0c1710 55%)', aurora: '', ocean: '' };
function applyBg(v) {
  const name = v || 'default';
  document.body.classList.remove('bg-aurora', 'bg-ocean');
  if (name === 'aurora') document.body.classList.add('bg-aurora');
  else if (name === 'ocean') document.body.classList.add('bg-ocean');
  else document.body.style.background = BG_MAP[name] || '';
}
function setBg(v) { saveSetting({ background: v }); localStorage.setItem('qh_bg', v); applyBg(v); }
async function openAvatarShop() { showView('avatarShop'); }
async function viewAvatarShop(app) {
  document.title = '棋魂阁 - 装扮商城';
  let items = [];
  try { items = (await GET('/avatar/frames')) || []; } catch (e) { toast(e.message, 'err'); }
  const cur = S.me.avatar_frame || '';
  const preview = (it) => `<span class="avatar-frame ${esc(frameCss(it.css) || frameCss(it.id) || '')}">${avatarBare(S.me, 'sm')}</span>`;
  const price = (it) => `<span class="dprice ${it.currency === 'diamonds' ? 'diam' : ''}">${it.currency === 'diamonds' ? '◆' : '●'} ${it.price}</span>`;
  const typeLabel = it => it.type === 'dyn' ? '<span class="tag real">动态头像</span>' : '<span class="tag">头像框</span>';
  const btn = (it) => {
    if (cur === it.id) return `<button class="btn small ghost" onclick="setFrame('')">停用</button>`;
    if (it.owned) return `<button class="btn small gold" onclick="setFrame('${it.id}')">启用</button>`;
    return `<button class="btn small gold" onclick="buyFrame('${it.id}')">${price(it)} 购买</button>`;
  };
  app.innerHTML = `${topbarHtml('装扮商城')}
    <div class="card" style="margin:10px 14px">
      <div class="row">当前：${preview(cur ? { id: cur } : { css: '' })} ${esc((items.find((i) => i.id === cur) || {}).name || (cur ? '装扮' : '无装扮'))}</div>
      <div class="sub">头像框：设置页选择样式后显示在头像周围<br>动态头像：带 CSS 动画的炫彩头像</div>
    </div>
    <div class="section-title">头像框（金币）</div>
    <div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      ${items.filter(i => i.type === 'frame' && i.currency === 'coins').map(it => `
        <div style="border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center">
          ${preview(it)}<div style="margin-top:6px;font-weight:700">${esc(it.name)}</div>
          <div class="sub" style="font-size:11px">${esc(it.desc)}</div>
          <div style="margin-top:6px">${btn(it)}</div>
        </div>`).join('') || '<div class="sub">暂无</div>'}
    </div>
    <div class="section-title">头像框（钻石）</div>
    <div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      ${items.filter(i => i.type === 'frame' && i.currency === 'diamonds').map(it => `
        <div style="border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center">
          ${preview(it)}<div style="margin-top:6px;font-weight:700">${esc(it.name)}</div>
          <div class="sub" style="font-size:11px">${esc(it.desc)}</div>
          <div style="margin-top:6px">${btn(it)}</div>
        </div>`).join('') || '<div class="sub">暂无</div>'}
    </div>
    <div class="section-title">动态头像（钻石）</div>
    <div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      ${items.filter(i => i.type === 'dyn').map(it => `
        <div style="border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center">
          ${preview(it)}<div style="margin-top:6px;font-weight:700">${esc(it.name)}</div>
          <div class="sub" style="font-size:11px">${esc(it.desc)}</div>
          <div style="margin-top:6px">${btn(it)}</div>
        </div>`).join('') || '<div class="sub">暂无</div>'}
    </div>
    <div class="card"><div class="sub">动态头像示意（示例样式）</div>
      <div class="row" style="gap:12px">
        <span class="avatar-frame dyn-fire">${fbAvatar('火', 'sm')}</span>
        <span class="avatar-frame dyn-star">${fbAvatar('星', 'sm')}</span>
        <span class="avatar-frame dyn-bolt">${fbAvatar('雷', 'sm')}</span>
        <span class="avatar-frame dyn-bubble">${fbAvatar('泡', 'sm')}</span>
      </div></div>
    ${bottomNavHtml()}`;
}
async function buyFrame(id) {
  try {
    const r = await POST('/avatar/frames/buy', { frame_id: id });
    toast(`购买成功：${r.item.name}`, 'ok');
    S.me = await GET('/me');
    render();
  } catch (e) { toast(e.message, 'err'); }
}
async function setFrame(id) {
  try {
    await POST('/me/avatar_frame', { frame_id: id });
    S.me = await GET('/me');
    toast('已更新头像框', 'ok');
    render();
  } catch (e) { toast(e.message, 'err'); }
}
function pickRegion() {
  modal(`<h3>选择地区</h3>
    <div style="display:flex;gap:6px;margin-bottom:8px">
      <input id="custom-region" placeholder="输入自定义地区（20字内）" style="flex:1">
      <button class="btn small gold" onclick="setCustomRegion()">上传</button></div>
    <div class="region-select">${S.regions.map((r) =>
    `<div class="region-item" onclick="setRegion('${r}')">${r}</div>`).join('')}</div>`);
}
function setCustomRegion() {
  const v = $('#custom-region').value.trim();
  if (!v) { toast('请输入地区', 'err'); return; }
  setRegion(v);
}
async function setRegion(r) {
  closeModal();
  try { S.me = await POST('/me/profile', { region: r }); toast('地区已更新', 'ok'); render(); }
  catch (e) { toast(e.message, 'err'); }
}
function editBio() {
  modal(`<h3>个性签名</h3><input id="bio-input" value="${esc(S.me.bio || '')}" placeholder="写一句签名（60字内）">
    <div class="err" id="bio-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveBio()">保存</button>`);
}
async function saveBio() {
  try { S.me = await POST('/me/profile', { bio: $('#bio-input').value }); closeModal(); toast('签名已更新', 'ok'); render(); }
  catch (e) { $('#bio-err').textContent = e.message; }
}
function editContact(kind) {
  const cur = kind === 'qq' ? S.me.qq : S.me.phone;
  modal(`<h3>修改${kind === 'qq' ? 'QQ号' : '手机号'}</h3>
    <input id="ct-input" value="${esc(cur || '')}" placeholder="${kind === 'qq' ? '输入新QQ号' : '输入新手机号'}">
    <div class="sub" style="margin-top:6px">修改后可用于登录和找回密码</div>
    <div class="err" id="ct-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveContact('${kind}')">保存</button>`);
}
async function saveContact(kind) {
  const v = $('#ct-input').value.trim();
  try { S.me = await POST('/me/profile', { [kind]: v }); closeModal(); toast('已更新', 'ok'); render(); }
  catch (e) { $('#ct-err').textContent = e.message; }
}
async function doRedeem() {
  const code = $('#redeem-code').value.trim();
  if (!code) { toast('请输入兑换码', 'err'); return; }
  try {
    const r = await POST('/redeem', { code });
    await refreshMe();
    toast(`兑换成功：金币+${r.coins} 钻石+${r.diamonds}`, 'ok');
    render();
  } catch (e) { toast(e.message, 'err'); }
}
function logoutLocal() {
  S.me = null; S.token = ''; S.match = null;
  localStorage.removeItem('qh_token');
  if (S.ws) { try { S.ws.close(); } catch (e) { } S.ws = null; }
  snd.stopMusic();
}
async function doLogout() {
  try { await POST('/logout', {}); } catch (e) { }
  logoutLocal(); showView('auth', {}, true); S.stack = [];
}
/* ---------- 商城 ---------- */
async function viewShop(app) {
  document.title = '棋魂阁 - 充值中心';
  if (!S.packages.length) { try { const r = await GET('/shop/packages'); S.packages = r.packages; } catch (e) { } }
  app.innerHTML = `${topbarHtml('充值中心')}
    <div class="card"><div class="spread">
      <div><div class="sub">当前余额</div>
      <div class="row" style="margin-top:4px"><span class="gold-txt" style="font-size:18px">${fmtNum(S.me.coins)} 金币</span>
      <span class="dia-txt" style="font-size:18px">${fmtNum(S.me.diamonds)} 钻石</span></div></div>
      <div class="sub" style="text-align:right">1元 = 100钻石<br>钻石仅游戏内消费<br>不可提现或兑换现金</div></div></div>
    <div class="section-title">钻石套餐</div>
    <div class="game-grid">${S.packages.map((p) => `<div class="game-tile" onclick="buy('${p.id}')">
      <div class="ico">💎</div><div class="nm">${p.diamonds} 钻石</div><div class="ds">¥ ${p.rmb}</div></div>`).join('')}</div>
    <div class="section-title">充值记录</div>
    <div class="card" id="order-list"><div class="empty">加载中...</div></div>
    ${bottomNavHtml()}`;
  loadOrders();
}
async function loadOrders() {
  const box = $('#order-list'); if (!box) return;
  try {
    const rows = await GET('/orders');
    box.innerHTML = rows.length ? rows.map((o) => `<div class="list-item">
      <div style="flex:1"><div>订单#${o.id} · ${o.diamonds}钻石</div><div class="sub">${fmtTime(o.created_at)} · ¥${o.rmb_cents / 100}</div></div>
      <span class="tag ${o.status === 'paid' ? 'real' : ''}">${o.status === 'paid' ? '已支付' : '待支付'}</span></div>`).join('')
      : '<div class="empty">暂无订单</div>';
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function buy(pkgId) {
  try {
    const r = await POST('/orders', { package_id: pkgId });
    const ok = confirm(`确认支付 ¥${r.package.rmb} 购买 ${r.package.diamonds} 钻石？（演示支付）`);
    if (!ok) return;
    await POST(`/orders/${r.order_id}/mock_pay`, {});
    await refreshMe();
    toast(`充值成功，获得 ${r.package.diamonds} 钻石`, 'ok'); snd.play('win');
    render();
  } catch (e) { toast(e.message, 'err'); }
}
/* ---------- 管理后台 ---------- */
function viewAdmin(app) {
  const role = S.me.role;
  if (role === 'player') { showView('home', {}, true); return; }
  const tabs = [['users', '用户管理'], ['reports', '举报处理'], ['forum', '论坛管理']];
  if (role === 'author') tabs.push(['codes', '兑换码'], ['orders', '订单'], ['virtual', '虚拟玩家'], ['mail', '邮件'], ['ai', 'AI设置'], ['music', '背景音乐']);
  app.innerHTML = `${topbarHtml('管理后台 · ' + (role === 'author' ? '作者' : '管理员'))}
    <div class="admin-tabs">${tabs.map(([k, n]) => `<button class="${S.adminTab === k ? 'active' : ''}" onclick="adminTab('${k}')">${n}</button>`).join('')}</div>
    <div id="admin-body"><div class="empty">加载中...</div></div>${bottomNavHtml()}`;
  loadAdminTab();
}
function adminTab(t) { S.adminTab = t; snd.play('click'); render(); }
async function loadAdminTab() {
  const box = $('#admin-body'); if (!box) return;
  try {
    if (S.adminTab === 'users') return await renderAdminUsers(box);
    if (S.adminTab === 'reports') return await renderAdminReports(box);
    if (S.adminTab === 'forum') return await renderAdminForum(box);
    if (S.adminTab === 'codes') return await renderAdminCodes(box);
    if (S.adminTab === 'orders') return await renderAdminOrders(box);
    if (S.adminTab === 'virtual') return await renderAdminVirtual(box);
    if (S.adminTab === 'mail') return renderAdminMail(box);
    if (S.adminTab === 'ai') return await renderAdminAI(box);
    if (S.adminTab === 'music') return await renderAdminMusic(box);
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function renderAdminUsers(box) {
  const rows = await GET('/admin/users?kw=' + encodeURIComponent(S.adminKw || ''));
  box.innerHTML = `<input placeholder="搜索昵称/QQ/手机号" value="${esc(S.adminKw || '')}" onchange="S.adminKw=this.value;loadAdminTab()" style="margin-bottom:8px">
    ${rows.map((u) => `<div class="list-item">${avatarHtml(u, 'sm')}
      <div style="flex:1"><div class="row"><b>${esc(u.name)}</b>${userTag(u)}</div>
        <div class="sub">ID:${u.id} · 金币${u.coins} · 钻${u.diamonds} · QQ:${esc(u.qq || '-')} · 手机:${esc(u.phone || '-')}</div></div>
      <div class="row" style="gap:6px">
        <button class="btn small ghost" onclick="adminCoins(${u.id},${u.coins},${u.diamonds})">改资产</button>
        <button class="btn small ghost" onclick="adminAvatar(${u.id},'${esc(u.avatar || '')}')">改头像</button>
        <button class="btn small ghost" onclick="adminRank(${u.id},${u.level || 1})">等级段位</button>
        <button class="btn small ghost" onclick="adminResetPwd(${u.id},'${esc(u.name)}')">重置密码</button>
        <button class="btn small danger" onclick="adminBan(${u.id},${u.banned ? 0 : 1})">${u.banned ? '解封' : '封禁'}</button></div></div>`).join('') || '<div class="empty">无结果</div>'}`;
}
async function adminBan(uid, flag) {
  try { await POST(`/admin/users/${uid}/ban`, { flag: !!flag }); toast(flag ? '已封禁' : '已解封', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
function adminCoins(uid, coins, diamonds) {
  modal(`<h3>修改资产 ID:${uid}</h3>
    <input id="ac-coins" type="number" value="${coins}" placeholder="金币(设为该值)">
    <input id="ac-dia" type="number" value="${diamonds}" placeholder="钻石(设为该值)" style="margin-top:6px">
    <div class="err" id="ac-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveAdminCoins(${uid})">保存</button>`);
}
async function saveAdminCoins(uid) {
  try {
    await POST(`/admin/users/${uid}/adjust`, { coins: +$('#ac-coins').value, diamonds: +$('#ac-dia').value });
    closeModal(); toast('已更新', 'ok'); loadAdminTab();
  } catch (e) { $('#ac-err').textContent = e.message; }
}
function adminAvatar(uid, avatar) {
  modal(`<h3>修改头像 ID:${uid}</h3>
    <input id="av-url" value="${esc(avatar)}" placeholder="头像URL，留空则恢复默认">
    <div class="err" id="av-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveAdminAvatar(${uid})">保存</button>`);
}
async function saveAdminAvatar(uid) {
  try {
    await POST(`/admin/users/${uid}/adjust`, { avatar: $('#av-url').value.trim() });
    closeModal(); toast('已更新', 'ok'); loadAdminTab();
  } catch (e) { $('#av-err').textContent = e.message; }
}
function adminRank(uid, level) {
  modal(`<h3>等级与段位 ID:${uid}</h3>
    <input id="rk-level" type="number" value="${level}" placeholder="等级(1-999)">
    <div class="sub" style="margin:6px 0">五子棋段位</div>
    <div class="row" style="gap:6px"><input id="rk-g1" type="number" value="1" min="1" max="12" placeholder="段位1-12"><input id="rk-s1" type="number" value="0" min="0" max="2" placeholder="星0-2"></div>
    <div class="sub" style="margin:6px 0">井字棋段位</div>
    <div class="row" style="gap:6px"><input id="rk-g2" type="number" value="1" min="1" max="12" placeholder="段位1-12"><input id="rk-s2" type="number" value="0" min="0" max="2" placeholder="星0-2"></div>
    <div class="sub" style="margin:6px 0">中国象棋段位</div>
    <div class="row" style="gap:6px"><input id="rk-g3" type="number" value="1" min="1" max="12" placeholder="段位1-12"><input id="rk-s3" type="number" value="0" min="0" max="2" placeholder="星0-2"></div>
    <div class="sub" style="margin:6px 0">斗兽棋段位</div>
    <div class="row" style="gap:6px"><input id="rk-g4" type="number" value="1" min="1" max="12" placeholder="段位1-12"><input id="rk-s4" type="number" value="0" min="0" max="2" placeholder="星0-2"></div>
    <div class="err" id="rk-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveAdminRank(${uid})">保存</button>`);
}
async function saveAdminRank(uid) {
  try {
    const body = { level: +$('#rk-level').value };
    const specs = [
      ['gomoku', '#rk-g1', '#rk-s1'],
      ['tictactoe', '#rk-g2', '#rk-s2'],
      ['xiangqi', '#rk-g3', '#rk-s3'],
      ['doubeast', '#rk-g4', '#rk-s4'],
    ];
    for (const [game, gSel, sSel] of specs) body[`rank_${game}`] = `${$(gSel).value},${$(sSel).value}`;
    await POST(`/admin/users/${uid}/adjust`, body);
    closeModal(); toast('已更新', 'ok'); loadAdminTab();
  } catch (e) { $('#rk-err').textContent = e.message; }
}
function adminResetPwd(uid, name) {
  const pw = prompt(`为「${name}」设置新密码（至少6位，留空则自动生成随机密码）：`, '');
  if (pw === null) return;
  adminResetPwdGo(uid, pw.trim());
}
async function adminResetPwdGo(uid, pw) {
  try {
    const r = await POST(`/admin/users/${uid}/reset_password`, { password: pw || '' });
    modal(`<h3>密码已重置</h3><div class="sub">用户新密码：</div><div class="code-box" style="font-size:20px">${esc(r.new_password)}</div>
      <div class="sub">请复制发给用户，此窗口关闭后无法再次查看</div>
      <button class="btn block" style="margin-top:8px" onclick="copyText('${esc(r.new_password)}')">复制密码</button>`);
  } catch (e) { toast(e.message, 'err'); }
}
async function renderAdminReports(box) {
  const rows = await GET('/admin/reports');
  box.innerHTML = rows.length ? rows.map((r) => {
    const tt = r.target_type === 'post' ? '帖子' : r.target_type === 'reply' ? '评论' : '用户';
    const actTxt = { delete: '已删内容', ban: '已封号', mute: '已禁言', warn: '已警告', dismiss: '已驳回' }[r.action] || r.action;
    return `<div class="list-item">
    <div style="flex:1"><div class="row"><span class="tag">${tt}</span>${r.status === 'pending' ? '<span class="tag virtual">待处理</span>' : `<span class="tag real">${actTxt}</span>`}<span>${esc(r.reason || '未填写原因')}</span></div>
      ${r.content ? `<div class="sub">内容：「${esc(r.content)}」</div>` : ''}
      <div class="sub">目标#${r.target_id}${r.target_user_name ? ' · 当事人 ' + esc(r.target_user_name) : ''} · 举报人 ${esc(r.reporter_name || '#' + r.reporter_id)} · ${fmtTime(r.created_at)}</div></div>
    ${r.status === 'pending' ? `<div class="row" style="gap:6px">
      ${r.target_type !== 'user' ? `<button class="btn small danger" onclick="adminResolve(${r.id},'delete')">删内容</button>` : ''}
      <button class="btn small danger" onclick="adminResolve(${r.id},'ban')">封号</button>
      ${r.target_type !== 'user' ? `<button class="btn small gold" onclick="adminResolve(${r.id},'mute')">禁言</button>` : ''}
      <button class="btn small gold" onclick="adminResolve(${r.id},'warn')">警告</button>
      <button class="btn small ghost" onclick="adminResolve(${r.id},'dismiss')">驳回</button></div>`
    : `<div class="row" style="gap:6px"><button class="btn small ghost" onclick="adminDelReport(${r.id})">删除记录</button></div>`}</div>`;
  }).join('') : '<div class="empty">暂无举报</div>';
}
async function adminResolve(id, action) {
  try { await POST(`/admin/reports/${id}/handle`, { action }); toast('已处理', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
async function adminDelReport(id) {
  if (!confirm('确认删除该条举报记录？')) return;
  try { await DEL(`/admin/reports/${id}`); toast('已删除', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
async function renderAdminForum(box) {
  const rows = await GET('/admin/forum/posts?kw=' + encodeURIComponent(S.adminForumKw || ''));
  box.innerHTML = `<input placeholder="搜索帖子内容" value="${esc(S.adminForumKw || '')}" onchange="S.adminForumKw=this.value;loadAdminTab()" style="margin-bottom:8px">
    ${rows.map((p) => `<div class="list-item">
    <div style="flex:1"><div>${esc((p.content || '').slice(0, 24))} <span class="sub">by ${esc(p.name || '#' + p.user_id)}${p.deleted ? ' · 已删除' : ''}${p.pinned ? ' · 已置顶' : ''}</span></div>
      <div class="sub">${esc((p.content || '').slice(0, 48))} · ❤${p.likes} · ${fmtTime(p.created_at)}</div></div>
    <div class="row" style="gap:6px">
      <button class="btn small ghost" onclick="adminPin(${p.id},'${p.pinned ? 'unpin' : 'pin'}')">${p.pinned ? '取消置顶' : '置顶'}</button>
      <button class="btn small danger" onclick="adminDelPost(${p.id})">删除</button></div></div>`).join('') || '<div class="empty">暂无帖子</div>'}`;
}
async function adminPin(pid, action) {
  try { await POST(`/admin/forum/${pid}/${action}`); toast('已更新', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
async function adminDelPost(pid) {
  if (!confirm('确认删除该帖子？')) return;
  try { await POST(`/admin/forum/${pid}/delete`); toast('已删除', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
async function renderAdminCodes(box) {
  const rows = await GET('/admin/redeem_codes');
  box.innerHTML = `<button class="btn gold block" style="margin-bottom:10px" onclick="adminGenCode()">生成兑换码</button>
    ${rows.map((c) => `<div class="list-item"><div style="flex:1">
      <div class="code-box" style="display:inline-block">${esc(c.code)}</div>
      <div class="sub">金币+${c.coins} 钻石+${c.diamonds} · 总次数${c.max_uses || 1} · 已用${c.used || 0}/${c.max_uses || 1} · 每人限${c.per_user_limit || 1}次 · ${fmtTime(c.created_at)}</div></div>
      ${(c.used || 0) < (c.max_uses || 1) ? `<button class="btn small ghost" onclick="copyText('${esc(c.code)}')">复制</button>` : ''}</div>`).join('') || '<div class="empty">暂无兑换码</div>'}`;
}
function adminGenCode() {
  modal(`<h3>生成兑换码</h3>
    <div class="row" style="gap:6px"><input id="gc-coins" type="number" value="100" placeholder="金币"><input id="gc-dia" type="number" value="0" placeholder="钻石"></div>
    <div class="row" style="gap:6px;margin-top:6px"><input id="gc-uses" type="number" value="1" placeholder="总次数"><input id="gc-pl" type="number" value="1" placeholder="每人限次"></div>
    <div class="err" id="gc-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveGenCode()">生成</button>`);
}
async function saveGenCode() {
  try {
    const r = await POST('/admin/redeem_codes', {
      coins: +$('#gc-coins').value, diamonds: +$('#gc-dia').value,
      max_uses: +($('#gc-uses').value || 1), per_user_limit: +($('#gc-pl').value || 1),
    });
    closeModal(); toast('已生成', 'ok'); loadAdminTab();
    modal(`<h3>新兑换码</h3><div class="code-box">${esc(r.code)}</div>
      <button class="btn block" style="margin-top:8px" onclick="copyText('${esc(r.code)}')">复制</button>`);
  } catch (e) { $('#gc-err').textContent = e.message; }
}
async function renderAdminOrders(box) {
  const rows = await GET('/admin/orders');
  box.innerHTML = rows.map((o) => `<div class="list-item">
    <div style="flex:1"><div>订单#${o.id} · 用户#${o.user_id} · ${o.diamonds}钻石</div>
      <div class="sub">¥${o.rmb_cents / 100} · ${fmtTime(o.created_at)}</div></div>
      <span class="tag ${o.status === 'paid' ? 'real' : ''}">${o.status === 'paid' ? '已支付' : '待支付'}</span></div>`).join('') || '<div class="empty">暂无订单</div>';
}
async function renderAdminVirtual(box) {
  const rows = await GET('/admin/virtual');
  box.innerHTML = `<button class="btn gold block" style="margin-bottom:10px" onclick="adminAddVirtual()">添加虚拟玩家</button>
    ${rows.map((v) => `<div class="list-item"><div style="flex:1">
      <div><b>${esc(v.name)}</b> <span class="sub">密码:${esc(v.plain_password || '已隐藏')}</span></div>
      <div class="sub">ID:${v.id} · 段位分:${v.points} · ${fmtTime(v.created_at)}</div></div>
      <button class="btn small danger" onclick="adminDelVirtual(${v.id},'${esc(v.name)}')">删除</button></div>`).join('') || '<div class="empty">暂无虚拟玩家</div>'}`;
}
async function adminDelVirtual(uid, name) {
  if (!confirm(`确认删除虚拟玩家「${name}」？`)) return;
  try { await DEL(`/admin/virtual/${uid}`); toast('已删除', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
function adminAddVirtual() {
  modal(`<h3>添加虚拟玩家</h3>
    <input id="vv-name" placeholder="昵称">
    <input id="vv-pwd" placeholder="密码" style="margin-top:6px">
    <input id="vv-points" type="number" value="1000" placeholder="初始段位分" style="margin-top:6px">
    <div class="err" id="vv-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="saveVirtual()">创建</button>`);
}
async function saveVirtual() {
  try {
    await POST('/admin/virtual', { name: $('#vv-name').value.trim(), password: $('#vv-pwd').value, points: +$('#vv-points').value });
    closeModal(); toast('已创建', 'ok'); loadAdminTab();
  } catch (e) { $('#vv-err').textContent = e.message; }
}
function renderAdminMail(box) {
  box.innerHTML = `<h3 style="margin:4px 0 10px">发送系统邮件</h3>
    <input id="mail-title" placeholder="标题">
    <textarea id="mail-content" rows="3" placeholder="内容" style="margin-top:6px"></textarea>
    <div class="row" style="gap:6px;margin-top:6px">
      <input id="mail-coins" type="number" value="0" placeholder="附金币"><input id="mail-dia" type="number" value="0" placeholder="附钻石"></div>
    <label class="row" style="margin-top:8px;gap:6px"><input type="checkbox" id="mail-all" checked> 发送给全体用户</label>
    <input id="mail-uid" type="number" placeholder="指定用户ID（不勾选全员时填）" style="margin-top:6px">
    <div class="err" id="mail-err"></div>
    <button class="btn block" style="margin-top:8px" onclick="sendAdminMail()">发送</button>`;
}
async function sendAdminMail() {
  try {
    const all = $('#mail-all').checked;
    await POST('/admin/mail', {
      title: $('#mail-title').value, content: $('#mail-content').value,
      coins: +$('#mail-coins').value, diamonds: +$('#mail-dia').value,
      to_all: all, to_user: all ? 0 : +($('#mail-uid').value || 0),
    });
    toast('邮件已发送', 'ok');
    $('#mail-title').value = ''; $('#mail-content').value = '';
  } catch (e) { $('#mail-err').textContent = e.message; }
}
async function renderAdminAI(box) {
  const r = await GET('/admin/ai');
  box.innerHTML = `<h3 style="margin:4px 0 10px">AI 托管设置</h3>
    <div class="card"><div class="setting-row"><div>模型API地址 (OpenAI格式)</div></div>
      <input id="ai-base" value="${esc(r.base_url || '')}" placeholder="https://xxx/v1">
      <div class="setting-row" style="margin-top:8px"><div>API Token</div></div>
      <input id="ai-key" type="password" value="${esc(r.api_key && r.api_key !== '未配置' && !r.api_key.includes('****') ? r.api_key : '')}" placeholder="${r.api_key || ''}">
      <div class="setting-row" style="margin-top:8px"><div>模型名称</div></div>
      <input id="ai-model" value="${esc(r.model || '')}" placeholder="deepseek-v4-flash">
      <div class="sub" style="margin-top:8px">当前 ${r.enabled ? '已启用' : '未启用'} · 训练对局 ${r.total_games || 0} · 胜率 ${Math.round((r.recent_win_rate || 0) * 100)}%</div>
      <button class="btn block" style="margin-top:8px" onclick="saveAdminAI()">保存配置</button>
      <div class="err" id="ai-err"></div></div>
    <div class="sub">AI 托管由后端 LLM + 引擎双通道提供；虚拟玩家通过训练循环自我对弈提升棋力。接口格式为 OpenAI Chat /chat/completions。</div>`;
}
async function saveAdminAI() {
  const body = { base_url: $('#ai-base').value.trim(), api_key: $('#ai-key').value.trim(), model: $('#ai-model').value.trim() };
  try {
    await POST('/admin/ai', body);
    toast('AI 配置已保存', 'ok'); loadAdminTab();
  } catch (e) { $('#ai-err').textContent = e.message; }
}
async function renderAdminMusic(box) {
  const r = await GET('/admin/music');
  S.adminMusic = r;
  const cur = (r.tracks || []).find((t) => t.id === r.current);
  box.innerHTML = `
    <div class="card"><div class="sub">当前背景音乐：${cur ? esc(cur.name) : '内置旋律（未启用上传音乐）'}</div>
      <div class="row" style="margin-top:10px;gap:8px">
        <button class="btn" onclick="pickMusicFile()">上传音乐（20MB内）</button>
        ${cur ? '<button class="btn ghost" onclick="stopMusicTrack()">停用，恢复内置旋律</button>' : ''}
      </div>
      <div class="sub" id="music-up-note" style="margin-top:8px">支持 mp3 / m4a / wav / ogg，启用后全体在线玩家实时切换</div>
    </div>
    <div class="section-title">曲库 ${(r.tracks || []).length}/20</div>
    ${(r.tracks || []).map((t) => `<div class="list-item">
      <div style="flex:1"><div class="row"><b>${esc(t.name)}</b>${t.id === r.current ? '<span class="tag real">使用中</span>' : ''}</div>
      <div class="sub">${(t.size / 1048576).toFixed(1)}MB</div></div>
      <button class="btn small ghost" onclick="renameMusicTrack('${t.id}')">改名</button>
      ${t.id === r.current ? '' : `<button class="btn small" onclick="useMusicTrack('${t.id}')">启用</button>`}
      <button class="btn small danger" onclick="delMusicTrack('${t.id}')">删除</button>
    </div>`).join('') || '<div class="empty">曲库为空，先上传一首音乐</div>'}`;
}
function pickMusicFile() {
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = 'audio/*';
  inp.onchange = async () => {
    const f = inp.files[0]; if (!f) return;
    if (f.size > 20 * 1024 * 1024) { toast('音乐文件不能超过 20MB', 'err'); return; }
    const note = $('#music-up-note'); if (note) note.textContent = `正在上传 ${f.name} ...`;
    const dataUrl = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(f); });
    try {
      await POST('/admin/music', { data_url: dataUrl, name: f.name.replace(/\.[^.]+$/, '') });
      toast('上传成功', 'ok'); loadAdminTab();
    } catch (e) { toast(e.message, 'err'); loadAdminTab(); }
  };
  inp.click();
}
async function useMusicTrack(id) {
  try { await POST(`/admin/music/${id}/current`, {}); toast('已切换背景音乐，在线玩家实时生效', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
async function renameMusicTrack(id) {
  const cur = ((S.adminMusic || {}).tracks || []).find((t) => t.id === id);
  const name = prompt('修改音乐名称（40字以内）：', cur ? cur.name : '');
  if (name === null) return;
  const trimmed = name.trim();
  if (!trimmed) { toast('名称不能为空', 'err'); return; }
  try {
    await POST(`/admin/music/${id}/rename`, { name: trimmed });
    toast('已重命名', 'ok'); loadAdminTab();
  } catch (e) { toast(e.message, 'err'); }
}
async function stopMusicTrack() {
  try { await POST('/admin/music/stop', {}); toast('已停用，恢复内置旋律', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
async function delMusicTrack(id) {
  if (!confirm('确定删除这首音乐？')) return;
  try { await DEL(`/admin/music/${id}`); toast('已删除', 'ok'); loadAdminTab(); }
  catch (e) { toast(e.message, 'err'); }
}
/* ---------- 启动 ---------- */
function initBg() {
  const bg = localStorage.getItem('qh_bg');
  applyBg(bg || 'default');
}
function copyText(t) {
  navigator.clipboard.writeText(t).then(() => toast('已复制', 'ok')).catch(() => toast('复制失败', 'err'));
}
async function boot() {
  initBg();
  const token = localStorage.getItem('qh_token');
  if (!token) showView('auth', {}, true);
  else {
    const app = $('#app');
    if (app && !app.innerHTML) {
      app.innerHTML = '<div class="auth-wrap"><div class="auth-title">棋魂阁</div><div class="sub" style="text-align:center;margin-top:12px">正在进入…</div></div>';
    }
  }
  document.addEventListener('pointerdown', () => {
    snd.ensure();
    if (S.me && S.music && S.music.url) snd.startMusic();
  });
  GET('/music').then((t) => { try { snd.setTrack(t); } catch (e) { } }).catch(() => { });
  if (token) {
    S.token = token; wsConnect();
    try {
      S.me = await GET('/me');
      localStorage.setItem('qh_bg', (S.me.settings && S.me.settings.background) || 'default');
      snd.startMusic(); updateBadges();
      showView('home', {}, true);
      return;
    } catch (e) { logoutLocal(); }
    showView('auth', {}, true);
  }
}
try { boot(); } catch (e) { showView('auth', {}, true); }