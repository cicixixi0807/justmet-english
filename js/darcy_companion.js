// Darcy 雪纳瑞悬浮陪读球 + 陪读小窝 + 拍立得打卡图（无人物头像，统一暖奶油珊瑚红风格）
import { store, showToast } from './store.js';

const DARCY_STORAGE_KEY = 'justmet_darcy_companion_v1';

const ACCESSORIES = [
  { id: 'headphones', icon: '🎧', label: '陪读耳机' },
  { id: 'scarf', icon: '🧣', label: '暖红围巾' },
  { id: 'glasses', icon: '🕶️', label: '酷酷墨镜' },
  { id: 'cap', icon: '🎓', label: '学士帽' },
];

const WHISPERS = [
  '慢慢听，听懂一句就是今天的进步 ✨',
  '不用追求一遍全懂，磨耳朵本身就在悄悄积累。',
  '开口跟读的那一秒，你就已经超过 90% 只看不练的人啦！',
  '今天也来小屋坐 10 分钟，Darcy 一直趴在旁边陪你。',
  '遇到卡壳的长句别慌，调到 0.8x 拆开听两遍就顺了。',
];

const PET_LINES = [
  '汪！摸摸头收到啦，继续听下一句吧 🐾',
  '耳朵竖起来了！这一句的连读超地道 🎧',
  '尾巴摇成小风扇～今天也在认真打卡 ✨',
  'Darcy 帮你记着进度呢，再听 2 分钟就达标啦！',
];

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}

function loadDarcyState() {
  try {
    const raw = JSON.parse(localStorage.getItem(DARCY_STORAGE_KEY) || '{}');
    const today = todayStr();
    const isNewDay = raw.lastDate !== today;
    return {
      lastDate: today,
      todaySec: isNewDay ? 0 : Number(raw.todaySec || 0),
      intimacy: Number(raw.intimacy || 12),
      treatsFed: Number(raw.treatsFed || 0),
      accessoryIdx: Number(raw.accessoryIdx || 0) % ACCESSORIES.length,
      streakDays: Math.max(1, Number(raw.streakDays || 1)),
    };
  } catch {
    return {
      lastDate: todayStr(),
      todaySec: 0,
      intimacy: 12,
      treatsFed: 0,
      accessoryIdx: 0,
      streakDays: 1,
    };
  }
}

function saveDarcyState(st) {
  try {
    localStorage.setItem(DARCY_STORAGE_KEY, JSON.stringify(st));
  } catch {}
}

let darcyState = loadDarcyState();
let nestOpen = false;
let bubbleTipTimer = null;
let studyTicker = null;

function getLevelInfo() {
  const lv = Math.min(9, 1 + Math.floor(darcyState.intimacy / 25));
  const goalSec = 600; // 今日 10 分钟目标
  const pct = Math.min(100, Math.round((darcyState.todaySec / goalSec) * 100));
  const mins = Math.floor(darcyState.todaySec / 60);
  return { lv, pct, mins, goalMins: 10 };
}

function renderPolaroidModal() {
  const { mins } = getLevelInfo();
  const vocab = (store.state.vocabBook || []).slice(0, 3).map((v) => v.key);
  const samplePhrases = vocab.length ? vocab : ['give it a try', 'for here or to go', 'first time'];
  const day = todayStr();
  const whisper = WHISPERS[new Date().getDate() % WHISPERS.length];

  const modalRoot = document.getElementById('modal-root');
  if (!modalRoot) return;
  modalRoot.innerHTML = `
    <div class="modal-backdrop" id="darcy-pol-bg">
      <div class="modal-card darcy-polaroid-modal">
        <div class="modal-header">
          <h3>📸 今日陪读拍立得打卡</h3>
          <button class="icon-circle-sm" id="darcy-pol-close">✕</button>
        </div>
        <div class="modal-body" style="align-items:center;">
          <div class="polaroid-frame" id="polaroid-preview">
            <div class="polaroid-photo">
              <img src="./assets/icon-dog-180.png" alt="Darcy" class="polaroid-darcy-img" />
              <div class="polaroid-stamp">🐾 连续陪读 ${darcyState.streakDays} 天</div>
              <div class="polaroid-brand">刚认识不久 Just met</div>
              <div class="polaroid-sub">今日精听 ${Math.max(1, mins)} 分钟 · Darcy 盖章认证</div>
            </div>
            <div class="polaroid-caption">
              <div class="polaroid-phrases">
                ${samplePhrases.map((p) => `<span class="polaroid-chip">${p}</span>`).join('')}
              </div>
              <div class="polaroid-note">“${whisper}”</div>
              <div class="polaroid-footer">
                <span>cici · Eddie</span>
                <span>${day}</span>
              </div>
            </div>
          </div>
          <div style="display:flex;gap:10px;width:100%;margin-top:6px;">
            <button class="btn btn-primary" id="darcy-pol-download" style="flex:1;">⬇️ 保存打卡图（适合小红书/朋友圈）</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.getElementById('darcy-pol-close')?.addEventListener('click', () => { modalRoot.innerHTML = ''; });
  document.getElementById('darcy-pol-bg')?.addEventListener('click', (e) => {
    if (e.target.id === 'darcy-pol-bg') modalRoot.innerHTML = '';
  });

  document.getElementById('darcy-pol-download')?.addEventListener('click', () => {
    downloadPolaroidPng(samplePhrases, whisper, Math.max(1, mins), day);
  });
}

function downloadPolaroidPng(phrases, whisper, mins, day) {
  const canvas = document.createElement('canvas');
  canvas.width = 720;
  canvas.height = 920;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Warm cream card background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, 720, 920);
  ctx.strokeStyle = '#EAD8D1';
  ctx.lineWidth = 4;
  ctx.strokeRect(2, 2, 716, 916);

  // Soft blush photo box
  ctx.fillStyle = '#FBF7F2';
  ctx.fillRect(38, 38, 644, 520);

  const finishDraw = (img) => {
    if (img) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(360, 225, 118, 0, Math.PI * 2);
      ctx.closePath();
      ctx.clip();
      ctx.drawImage(img, 242, 107, 236, 236);
      ctx.restore();
      ctx.strokeStyle = '#C86A5B';
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.arc(360, 225, 122, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Stamp pill
    ctx.fillStyle = '#F6E3DE';
    ctx.fillRect(230, 368, 260, 44);
    ctx.fillStyle = '#A95143';
    ctx.font = 'bold 22px -apple-system, PingFang SC, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`🐾 连续陪读 ${darcyState.streakDays} 天`, 360, 398);

    // Title
    ctx.fillStyle = '#2B1F1B';
    ctx.font = 'bold 38px Georgia, Noto Serif SC, serif';
    ctx.fillText('刚认识不久 Just met', 360, 466);

    ctx.fillStyle = '#755E57';
    ctx.font = '22px -apple-system, PingFang SC, sans-serif';
    ctx.fillText(`今日精听 ${mins} 分钟 · Darcy 盖章认证`, 360, 512);

    // Learned phrases
    ctx.fillStyle = '#C86A5B';
    ctx.font = 'bold 20px -apple-system, PingFang SC, sans-serif';
    ctx.fillText(`今日收获表达：${phrases.join('  ·  ')}`, 360, 626);

    // Whisper note
    ctx.fillStyle = '#2B1F1B';
    ctx.font = '24px Georgia, Noto Serif SC, serif';
    ctx.fillText(`“${whisper.slice(0, 24)}”`, 360, 710);

    // Footer
    ctx.strokeStyle = '#EAD8D1';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(48, 800);
    ctx.lineTo(672, 800);
    ctx.stroke();

    ctx.textAlign = 'left';
    ctx.fillStyle = '#755E57';
    ctx.font = 'bold 22px -apple-system, sans-serif';
    ctx.fillText('cici · Eddie', 48, 856);

    ctx.textAlign = 'right';
    ctx.fillText(day, 672, 856);

    const a = document.createElement('a');
    a.download = `Justmet-Darcy-${day.replace(/\//g, '-')}.png`;
    a.href = canvas.toDataURL('image/png');
    a.click();
    showToast('打卡拍立得已保存！快去分享吧 📸');
  };

  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => finishDraw(img);
  img.onerror = () => finishDraw(null);
  img.src = './assets/icon-dog-180.png';
}

function updateDarcyUI() {
  const wrap = document.getElementById('darcy-companion-root');
  if (!wrap) return;
  const isEnterPage = !window.location.hash || window.location.hash === '#/login';
  wrap.style.display = isEnterPage ? 'none' : 'block';
  if (isEnterPage) {
    nestOpen = false;
    return;
  }
  const { lv, pct, mins, goalMins } = getLevelInfo();
  const acc = ACCESSORIES[darcyState.accessoryIdx];
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  const whisper = WHISPERS[new Date().getDate() % WHISPERS.length];

  wrap.innerHTML = `
    <div class="darcy-nest-panel ${nestOpen ? 'open' : ''}" id="darcy-nest-panel" aria-hidden="${!nestOpen}">
      <div class="darcy-nest-head">
        <div>
          <div class="darcy-nest-title">🐾 Darcy 的陪读小窝</div>
          <div class="darcy-nest-sub">Lv.${lv} 陪读搭档 · 亲密度 ${darcyState.intimacy}</div>
        </div>
        <button class="icon-circle-sm" id="darcy-nest-close" title="收起小窝">✕</button>
      </div>

      <div class="darcy-stage">
        <div class="darcy-cushion">
          <img src="./assets/icon-dog-180.png" alt="Darcy" class="darcy-stage-img" id="darcy-pet-img" />
          <span class="darcy-acc-badge" title="${acc.label}">${acc.icon}</span>
        </div>
        <div class="darcy-speech" id="darcy-speech-text">
          汪！今天已经陪你学了 <strong>${mins}</strong> 分钟，离 ${goalMins} 分钟小目标还差 ${Math.max(0, goalMins - mins)} 分钟 ✨
        </div>
      </div>

      <div class="darcy-energy">
        <div class="darcy-energy-row">
          <span>今日陪伴能量</span>
          <strong>${mins}/${goalMins} 分钟 (${pct}%)</strong>
        </div>
        <div class="darcy-energy-track">
          <div class="darcy-energy-fill" style="width:${Math.max(8, pct)}%;"></div>
        </div>
      </div>

      <div class="darcy-actions-grid">
        <button class="darcy-act-btn" id="darcy-act-pet">🐾 摸摸头</button>
        <button class="darcy-act-btn" id="darcy-act-treat">🍪 喂小饼干</button>
        <button class="darcy-act-btn" id="darcy-act-dress">${acc.icon} 换装扮</button>
        <button class="darcy-act-btn primary" id="darcy-act-polaroid">📸 打卡拍立得</button>
      </div>

      <div class="darcy-whisper-box">
        <div class="darcy-whisper-label">cici · Eddie 今日悄悄话</div>
        <div class="darcy-whisper-text">${whisper}</div>
      </div>
    </div>

    <div class="darcy-fab-wrap" id="darcy-fab-wrap">
      <div class="darcy-mini-bubble" id="darcy-mini-bubble"></div>
      <button class="darcy-fab" id="darcy-fab-btn" title="点开 Darcy 陪读小窝（支持拖拽）">
        <svg class="darcy-ring" viewBox="0 0 64 64">
          <circle class="darcy-ring-bg" cx="32" cy="32" r="${radius}" />
          <circle class="darcy-ring-fg" cx="32" cy="32" r="${radius}" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" />
        </svg>
        <img src="./assets/icon-dog-180.png" alt="Darcy" class="darcy-fab-img" />
        <span class="darcy-fab-acc">${acc.icon}</span>
      </button>
    </div>
  `;

  const fabBtn = document.getElementById('darcy-fab-btn');
  const closeBtn = document.getElementById('darcy-nest-close');
  const speechEl = document.getElementById('darcy-speech-text');
  const petImg = document.getElementById('darcy-pet-img');

  // 支持轻点展开 & 简单拖拽移动
  let dragStart = null;
  let moved = false;
  const fabWrap = document.getElementById('darcy-fab-wrap');

  fabBtn?.addEventListener('pointerdown', (e) => {
    dragStart = { x: e.clientX, y: e.clientY, rect: fabWrap.getBoundingClientRect() };
    moved = false;
    fabBtn.setPointerCapture?.(e.pointerId);
  });

  fabBtn?.addEventListener('pointermove', (e) => {
    if (!dragStart) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
      moved = true;
      const right = Math.max(12, Math.min(window.innerWidth - 76, window.innerWidth - (dragStart.rect.right + dx)));
      const bottom = Math.max(18, Math.min(window.innerHeight - 86, window.innerHeight - (dragStart.rect.bottom + dy)));
      fabWrap.style.right = `${right}px`;
      fabWrap.style.bottom = `${bottom}px`;
    }
  });

  fabBtn?.addEventListener('pointerup', () => {
    const wasMoved = moved;
    dragStart = null;
    moved = false;
    if (!wasMoved) {
      nestOpen = !nestOpen;
      updateDarcyUI();
    }
  });

  closeBtn?.addEventListener('click', () => {
    nestOpen = false;
    updateDarcyUI();
  });

  document.getElementById('darcy-act-pet')?.addEventListener('click', () => {
    darcyState.intimacy += 2;
    saveDarcyState(darcyState);
    const line = PET_LINES[Math.floor(Math.random() * PET_LINES.length)];
    if (speechEl) speechEl.textContent = line;
    petImg?.classList.remove('darcy-bounce');
    void petImg?.offsetWidth;
    petImg?.classList.add('darcy-bounce');
  });

  document.getElementById('darcy-act-treat')?.addEventListener('click', () => {
    darcyState.intimacy += 5;
    darcyState.treatsFed += 1;
    saveDarcyState(darcyState);
    if (speechEl) speechEl.textContent = `咔嚓咔嚓 🍪 谢谢投喂！亲密度 +5（累计投喂 ${darcyState.treatsFed} 次）`;
    petImg?.classList.remove('darcy-bounce');
    void petImg?.offsetWidth;
    petImg?.classList.add('darcy-bounce');
    showToast('Darcy 开心吃掉了小饼干 🍪 亲密度 +5');
  });

  document.getElementById('darcy-act-dress')?.addEventListener('click', () => {
    darcyState.accessoryIdx = (darcyState.accessoryIdx + 1) % ACCESSORIES.length;
    saveDarcyState(darcyState);
    const nextAcc = ACCESSORIES[darcyState.accessoryIdx];
    showToast(`已给 Darcy 换上「${nextAcc.icon} ${nextAcc.label}」`);
    updateDarcyUI();
  });

  document.getElementById('darcy-act-polaroid')?.addEventListener('click', () => {
    nestOpen = false;
    updateDarcyUI();
    renderPolaroidModal();
  });
}

export function showDarcyMiniTip(text) {
  const el = document.getElementById('darcy-mini-bubble');
  if (!el || nestOpen) return;
  el.textContent = text;
  el.classList.add('show');
  if (bubbleTipTimer) clearTimeout(bubbleTipTimer);
  bubbleTipTimer = setTimeout(() => el.classList.remove('show'), 3600);
}

export function mountDarcyCompanion() {
  if (!document.getElementById('darcy-companion-root')) {
    const el = document.createElement('div');
    el.id = 'darcy-companion-root';
    document.body.appendChild(el);
    document.addEventListener('click', (e) => {
      if (e.target.closest?.('#open-darcy-banner-btn')) {
        nestOpen = true;
        updateDarcyUI();
      }
    });
    window.addEventListener('hashchange', () => updateDarcyUI());
  }
  updateDarcyUI();

  if (!studyTicker) {
    studyTicker = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      if (window.location.hash.startsWith('#/episode/')) {
        darcyState.todaySec += 15;
        if (darcyState.todaySec % 120 === 0) {
          darcyState.intimacy += 1;
          showDarcyMiniTip(`汪！已专注精听 ${Math.floor(darcyState.todaySec / 60)} 分钟啦 ✨`);
        }
        saveDarcyState(darcyState);
        if (!nestOpen) {
          const { pct } = getLevelInfo();
          const fg = document.querySelector('.darcy-ring-fg');
          if (fg) {
            const c = 2 * Math.PI * 28;
            fg.setAttribute('stroke-dashoffset', String(c * (1 - pct / 100)));
          }
        }
      }
    }, 15000);
  }
}
