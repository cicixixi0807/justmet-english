// Just Met 宇宙登录页、宇宙大厅、资料库详情页与素材导入弹窗
import { LIBRARIES, DICTIONARY, UPSELL_PACKS, lookupWord } from './data.js';
import { store, showToast, USER_AVATARS } from './store.js';

function escapeHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function renderHeader(activeRoute) {
  const user = store.state.user;
  return `
    <header class="site-header">
      <div class="site-header-inner">
        <a href="#/universe" class="brand-lockup">
          <img class="brand-icon" src="./assets/icon-192.png" alt="Just met" />
          <div>
            <div class="brand-title">刚认识不久 Just met</div>
            <div class="brand-sub">cici · Eddie 刚认识小屋</div>
          </div>
        </a>
        <nav class="site-nav">
          <a href="#/universe" class="nav-link ${activeRoute === 'universe' ? 'active' : ''}">小屋大厅</a>
          <a href="#/library" class="nav-link ${activeRoute === 'library' ? 'active' : ''}">英语自习室</a>
          <a href="#/vocab" class="nav-link ${activeRoute === 'vocab' ? 'active' : ''}">生词本 (${store.state.vocabBook.length})</a>
          <a href="#/membership" class="nav-link ${activeRoute === 'membership' ? 'active' : ''}">✦ 进阶权益与积分</a>
          <a href="https://justmet.pages.dev" target="_blank" rel="noopener" class="nav-link">恋综模拟器 ↗</a>
        </nav>
        <div class="header-right">
          <a href="#/membership" class="pill" title="AI 评测积分余额与进阶权益">💎 积分 ${store.state.credits}${store.state.unlockedPremium ? ' · PRO' : ''}</a>
          ${
            user
              ? `<div class="user-chip">
                   <img src="${user.avatar}" alt="avatar" />
                   <span>${escapeHtml(user.name)}</span>
                 </div>
                 <button class="btn btn-outline" id="btn-logout" style="padding:7px 14px;font-size:12px;">退出</button>`
              : `<a href="#/login" class="btn btn-primary" style="padding:8px 16px;font-size:13px;">进入小屋</a>`
          }
        </div>
      </div>
    </header>
  `;
}

function renderMobileBottomNav(activeKey) {
  return `
    <nav class="tt-bottom-nav" aria-label="移动端底部导航">
      <a class="tt-bnav-item ${activeKey === 'studio' ? 'active' : ''}" href="#/studio">
        <span class="tt-bnav-ic">⌂</span>
        <span>自习室</span>
      </a>
      <a class="tt-bnav-item ${activeKey === 'library' ? 'active' : ''}" href="#/library">
        <span class="tt-bnav-ic">▤</span>
        <span>课程</span>
      </a>
      <a class="tt-bnav-item ${activeKey === 'vocab' ? 'active' : ''}" href="#/vocab">
        <span class="tt-bnav-ic">🔖</span>
        <span>生词</span>
      </a>
      <a class="tt-bnav-item ${activeKey === 'membership' ? 'active' : ''}" href="#/membership">
        <span class="tt-bnav-ic">☺</span>
        <span>我的</span>
      </a>
    </nav>
  `;
}

function getUserSafeAvatar() {
  const av = store.state.user?.avatar;
  return USER_AVATARS.includes(av) ? av : USER_AVATARS[1];
}

// 1. 登录 / 进场页（只需写下名字，系统自动分配专属小动物头像）
export function renderLoginPage(root, navigate) {
  root.innerHTML = `
    <div class="tt-enter-mobile">
      <div class="tt-enter-card">
        <img class="tt-enter-logo" src="./assets/icon-192.png" alt="JM" />
        <h1 class="tt-enter-title">Justmet · TalkTalk</h1>
        <div class="tt-enter-sub">刚认识小屋 · 英语自习室</div>

        <form id="tt-enter-form" class="tt-enter-form">
          <label class="tt-field-label" for="tt-enter-name">写下你的名字</label>
          <input class="tt-name-input" id="tt-enter-name" type="text" placeholder="例如：Mila" value="${escapeHtml(store.state.user?.name || '')}" required />

          <button type="submit" class="tt-enter-cta">进入自习室</button>
        </form>

        <div class="tt-enter-credit">cici · Eddie</div>
      </div>
    </div>

    <div class="login-shell tt-enter-desktop">
      <div class="login-topbar">
        <div class="brand-lockup">
          <img class="brand-icon" src="./assets/icon-192.png" alt="Just met logo" />
          <div>
            <div class="brand-title">刚认识不久 Just met</div>
            <div class="brand-sub">JUST MET UNIVERSE · 播客 · 恋综 · 英语听说</div>
          </div>
        </div>
        <div style="display:flex;gap:10px;align-items:center;">
          <a href="https://justmet.pages.dev" target="_blank" rel="noopener" class="btn btn-outline" style="padding:8px 15px;font-size:13px;">打开恋综模拟器 ↗</a>
          <button class="btn btn-soft" id="top-guest-enter" style="padding:8px 15px;font-size:13px;">直接进入英语自习室</button>
        </div>
      </div>

      <main class="login-grid">
        <section>
          <div class="universe-hero-tag">✦ 刚认识不久 Just met · 专属内容与工具宇宙</div>
          <h1 class="universe-headline">
            从一场轻松的对话开始，<br />
            探索 <span>Just met 宇宙</span> 的全部可能
          </h1>
          <p class="universe-lead">
            由 <strong>cici · Eddie</strong> 共同主理，小屋管家 <strong>Darcy</strong> 陪伴。在这里，你可以体验沉浸式《重生之我上恋综了》互动测评，也可以在全新上线的「刚认识小屋 · 英语自习室」里每天精听、跟读、练就地道口语。
          </p>

          <div class="hosts-strip">
            <div class="avatar-stack">
              <img src="./assets/hosts/darcy_round.webp" alt="Darcy" title="陪读管家 Darcy" />
            </div>
            <div class="hosts-meta">
              <strong>cici · Eddie</strong> 主理 &amp; <strong>Darcy</strong> 陪读陪伴<br />
              所有产品一个账号统一通行
            </div>
          </div>

          <div class="product-showcase-grid">
            <article class="product-card featured">
              <div class="product-badge-row">
                <span class="pill">全新上线</span>
                <span style="font-size:12px;color:var(--muted);">精听 · 跟读 · 评测</span>
              </div>
              <h3 class="product-title">刚认识小屋 · 英语自习室</h3>
              <p class="product-desc">
                双语动态字幕、逐句跟读录音、AI 音素级发音评分、挖空听写、AB 片段复读、盲听与生词本一站式配齐，每天 10 分钟沉浸磨耳朵。
              </p>
              <div class="product-actions">
                <button class="btn btn-primary" id="card-enter-english" style="padding:8px 16px;font-size:13px;">进入英语自习室 →</button>
              </div>
            </article>

            <article class="product-card romance">
              <div class="product-badge-row">
                <span class="pill" style="background:#F8DFEA;color:#9D3C66;">人气体验</span>
                <span style="font-size:12px;color:var(--muted);">37道剧情 · 18种人格</span>
              </div>
              <h3 class="product-title">重生之我上恋综了</h3>
              <p class="product-desc">
                代入一档虚构恋综女嘉宾，走完 DAY 0 问卷与 DAY 1–6 剧情选择，解锁你的专属恋综人格类型与深度个性化报告。
              </p>
              <div class="product-actions">
                <a href="https://justmet.pages.dev" target="_blank" rel="noopener" class="btn btn-outline" style="padding:8px 16px;font-size:13px;">前往体验恋综模拟器 ↗</a>
              </div>
              <div class="disclaimer-tiny">※ 娱乐化互动体验，依恋与关系倾向内容并非专业心理诊断</div>
            </article>

            <article class="product-card product-card-wide">
              <div>
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                  <span class="pill">播客宇宙</span>
                  <strong style="font-family:var(--font-serif);font-size:15px;">《刚认识不久 Just met》播客 &amp; 更多新产品</strong>
                </div>
                <p class="product-desc">探讨个人成长、亲密关系与都市职场表达；更多 Just met 宇宙成员产品将持续入驻这里。</p>
              </div>
              <button class="btn btn-soft" id="card-enter-universe" style="flex-shrink:0;padding:8px 14px;font-size:13px;">浏览小屋大厅</button>
            </article>
          </div>
        </section>

        <section class="auth-panel">
          <div class="auth-header">
            <img src="./assets/icon-192.png" alt="JM" />
            <h2>Justmet · TalkTalk</h2>
            <p>刚认识小屋 · 英语自习室</p>
          </div>

          <form id="login-form">
            <div class="form-group">
              <label class="form-label" for="login-email">写下你的名字</label>
              <input class="form-input" id="login-email" type="text" placeholder="例如：Mila" value="${escapeHtml(store.state.user?.name || '')}" required />
            </div>
            <button type="submit" class="tt-enter-cta" style="margin-top:6px;">
              进入自习室
            </button>
          </form>

          <div class="auth-divider">或者快捷直达</div>

          <div class="quick-entry-grid">
            <button class="btn btn-soft" id="quick-english">🎧 直接练英语</button>
            <a class="btn btn-outline" href="https://justmet.pages.dev" target="_blank" rel="noopener">💌 玩恋综模拟器</a>
          </div>

          <p style="text-align:center;font-size:12px;color:var(--muted);margin-top:16px;">
            cici · Eddie · 学习进度与生词本将自动保存在本地浏览器中
          </p>
        </section>
      </main>
    </div>
  `;

  const pickAnimalAvatarForName = (name) => {
    let hash = 0;
    const str = String(name || 'Mila');
    for (let i = 0; i < str.length; i++) hash = (hash * 31 + str.charCodeAt(i)) >>> 0;
    return USER_AVATARS[hash % USER_AVATARS.length];
  };

  const enterAs = (targetHash, inputId = 'login-email') => {
    const emailVal = document.getElementById(inputId)?.value || 'Mila';
    const name = emailVal.includes('@') ? emailVal.split('@')[0] : emailVal;
    const autoAvatar = pickAnimalAvatarForName(name);
    store.login({ name, email: emailVal, avatar: autoAvatar });
    showToast(`欢迎来到自习室，${name}`);
    navigate(targetHash);
  };

  document.getElementById('tt-enter-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    enterAs('#/studio', 'tt-enter-name');
  });
  document.getElementById('login-form').addEventListener('submit', (e) => {
    e.preventDefault();
    enterAs('#/studio', 'login-email');
  });
  document.getElementById('top-guest-enter').addEventListener('click', () => enterAs('#/library'));
  document.getElementById('card-enter-english').addEventListener('click', () => enterAs('#/library'));
  document.getElementById('card-enter-universe').addEventListener('click', () => enterAs('#/universe'));
  document.getElementById('quick-english').addEventListener('click', () => {
    const firstId = LIBRARIES[0].episodes[0]?.id;
    enterAs(firstId ? `#/episode/${firstId}` : '#/library');
  });
}

// 1.5 专属自习室页面（严格对照 02_screen_studio.png）
export function renderStudioPage(root, navigate) {
  const lib = LIBRARIES[0];
  const userName = store.state.user?.name || 'Mila';
  const userAvatar = getUserSafeAvatar();
  const progressMap = store.state.episodeProgress || {};
  const startedEps = lib.episodes.filter((ep) => (progressMap[ep.id] || 0) > 0);
  const resumeEp = startedEps[0] || lib.episodes[0];
  const resumePct = Math.max(12, Math.round(progressMap[resumeEp?.id] || 35));
  const learnedCount = Object.keys(store.state.learnedEpisodes || {}).length || Math.max(1, startedEps.length);

  let studyMins = 28;
  try {
    const dRaw = JSON.parse(localStorage.getItem('justmet_darcy_companion_v1') || '{}');
    if (dRaw.todaySec) studyMins = Math.max(1, Math.round(dRaw.todaySec / 60));
  } catch {}

  root.innerHTML = `
    <div class="tt-desktop-only-header">${renderHeader('studio')}</div>
    <main class="tt-studio-page">
      <div class="tt-brand-overline">Justmet · TalkTalk</div>

      <div class="tt-studio-hero">
        <div class="tt-studio-avatar-ring">
          <img src="${userAvatar}" alt="${escapeHtml(userName)}" />
        </div>
        <h1 class="tt-studio-name">${escapeHtml(userName)} 的自习室</h1>
        <button class="tt-darcy-chip" id="studio-darcy-chip">
          <img src="./assets/icon-dog-180.png" alt="Darcy" />
          <span>小屋管家 Darcy 陪读中</span>
        </button>
      </div>

      ${
        resumeEp
          ? `<section class="tt-studio-section">
               <div class="tt-section-label">继续学习</div>
               <article class="tt-continue-card" id="studio-continue-card" data-ep="${resumeEp.id}">
                 <div class="tt-continue-thumb" style="background:${resumeEp.coverGradient};">
                   ${resumeEp.coverImage ? `<img src="${resumeEp.coverImage}" alt="" />` : ''}
                 </div>
                 <div class="tt-continue-info">
                   <div class="tt-continue-speaker">${escapeHtml(resumeEp.speaker)}</div>
                   <div class="tt-continue-sub">${escapeHtml(resumeEp.title)} · ${resumeEp.durationLabel}</div>
                   <div class="tt-progress-track"><div class="tt-progress-fill" style="width:${resumePct}%;"></div></div>
                 </div>
               </article>
             </section>`
          : ''
      }

      <section class="tt-studio-stats">
        <button class="tt-stat-card" id="studio-stat-courses">
          <div class="tt-stat-val">${learnedCount}</div>
          <div class="tt-stat-lbl">本周课程</div>
        </button>
        <button class="tt-stat-card" id="studio-stat-mins">
          <div class="tt-stat-val">${studyMins}</div>
          <div class="tt-stat-lbl">学习分钟</div>
        </button>
        <button class="tt-stat-card" id="studio-stat-vocab">
          <div class="tt-stat-val">${store.state.vocabBook.length}</div>
          <div class="tt-stat-lbl">生词</div>
        </button>
      </section>

      <div class="tt-studio-quick-links">
        <button class="btn btn-outline" id="studio-go-courses" style="font-size:13px;">浏览全部 ${lib.episodes.length} 节课程 →</button>
        <button class="btn btn-soft" id="studio-go-universe" style="font-size:13px;">🏠 小屋大厅</button>
      </div>
    </main>
    ${renderMobileBottomNav('studio')}
  `;

  bindHeaderEvents(navigate);
  document.getElementById('studio-darcy-chip')?.addEventListener('click', () => {
    document.getElementById('darcy-fab-btn')?.click();
  });
  document.getElementById('studio-continue-card')?.addEventListener('click', (e) => {
    const epId = e.currentTarget.dataset.ep;
    if (epId) navigate(`#/episode/${epId}`);
  });
  document.getElementById('studio-stat-courses')?.addEventListener('click', () => navigate('#/library'));
  document.getElementById('studio-stat-mins')?.addEventListener('click', () => document.getElementById('darcy-fab-btn')?.click());
  document.getElementById('studio-stat-vocab')?.addEventListener('click', () => navigate('#/vocab'));
  document.getElementById('studio-go-courses')?.addEventListener('click', () => navigate('#/library'));
  document.getElementById('studio-go-universe')?.addEventListener('click', () => navigate('#/universe'));
}

// 2. 宇宙大厅页面
export function renderUniverseHub(root, navigate) {
  const lib = LIBRARIES[0];
  const learnedCount = Object.values(store.state.learnedEpisodes).filter(Boolean).length;
  const avgProg = Math.round(
    lib.episodes.reduce((sum, ep) => sum + (store.state.episodeProgress[ep.id] || 0), 0) / lib.episodes.length
  );

  root.innerHTML = `
    ${renderHeader('universe')}
    <main class="page-container">
      <section style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:24px;">
        <div>
          <span class="pill" style="margin-bottom:8px;">✦ 刚认识小屋 · Just met</span>
          <h1 style="font-family:var(--font-serif);font-size:28px;">你好，${escapeHtml(store.state.user?.name || '旅人')} 👋</h1>
          <p style="font-size:14px;color:var(--muted);margin-top:4px;">欢迎回到刚认识小屋，选择今天想体验的空间模块</p>
        </div>
        <div style="display:flex;gap:10px;">
          <button class="btn btn-primary" id="hub-continue-ep">继续上次精听 →</button>
        </div>
      </section>

      <section class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">小屋已开放空间</div>
          <div class="kpi-value">3</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">英语平均进度</div>
          <div class="kpi-value">${avgProg}%</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">已学完剧集</div>
          <div class="kpi-value">${learnedCount} / ${lib.episodes.length}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">生词本收藏</div>
          <div class="kpi-value">${store.state.vocabBook.length}</div>
        </div>
      </section>

      <section class="product-showcase-grid" style="margin-bottom:28px;">
        <article class="product-card featured" style="padding:26px;">
          <div class="product-badge-row">
            <span class="pill">核心产品 · 听说训练</span>
            <span style="font-size:12px;color:var(--muted);">已更新 ${lib.episodes.length} 期</span>
          </div>
          <h2 class="product-title" style="font-size:22px;">刚认识小屋 · 英语自习室</h2>
          <p class="product-desc">
            完整配备双语精听、逐句跟读录音、AI 发音评分、挖空、听写词、点词查词、AB 片段复读、盲听模式、12 套护眼主题与 PDF 讲义导出。
          </p>
          <div class="product-actions">
            <button class="btn btn-primary" id="hub-go-library">进入英语自习室</button>
            <button class="btn btn-soft" id="hub-go-ep1">继续最新一期精听</button>
          </div>
        </article>

        <article class="product-card romance" style="padding:26px;">
          <div class="product-badge-row">
            <span class="pill" style="background:#F8DFEA;color:#9D3C66;">互动测评 · 已上线</span>
            <span style="font-size:12px;color:var(--muted);">justmet.pages.dev</span>
          </div>
          <h2 class="product-title" style="font-size:22px;">《刚认识不久》· 重生之我上恋综了</h2>
          <p class="product-desc">
            cici · Eddie 搭档主持，小屋管家 Darcy 暖心营业。37 道沉浸式恋综剧情选择，测出你的 18 种恋综人格类型并解锁专属完整报告。
          </p>
          <div class="product-actions">
            <a href="https://justmet.pages.dev" target="_blank" rel="noopener" class="btn btn-primary" style="background:#B5527A;">进入恋综模拟器 ↗</a>
          </div>
          <div class="disclaimer-tiny">※ 节目名仅作情境说明，依恋与恋爱脑相关内容为娱乐概括，非专业诊断</div>
        </article>
      </section>
    </main>
  `;

  bindHeaderEvents(navigate);
  const firstEpHash = lib.episodes[0] ? `#/episode/${lib.episodes[0].id}` : '#/library';
  document.getElementById('hub-continue-ep').addEventListener('click', () => navigate(firstEpHash));
  document.getElementById('hub-go-library').addEventListener('click', () => navigate('#/library'));
  document.getElementById('hub-go-ep1').addEventListener('click', () => navigate(firstEpHash));
  document.getElementById('hub-import-btn').addEventListener('click', () => openImportModal(navigate));
}

// 3. 资料库详情与剧集网格（对应 SayBreeze /library/45）
export function renderLibraryPage(root, navigate) {
  const lib = LIBRARIES[0];
  let filterText = '';
  let filterDifficulty = 'all';
  let filterTag = 'all';
  let filterSpeaker = 'all';
  let filterDuration = 'all';
  let sortBy = 'latest';

  const allTags = Array.from(
    new Set(['日常对话', '生活英语', '美食', '旅行', '名人访谈', '购物', '个人成长', '生活', ...lib.episodes.flatMap((e) => e.tags)])
  );
  const allSpeakers = Array.from(new Set(lib.episodes.map((e) => e.speaker)));

  const renderInner = () => {
    const avgProg = Math.round(
      lib.episodes.reduce((sum, ep) => sum + (store.state.episodeProgress[ep.id] || 0), 0) / lib.episodes.length
    );

    let list = [...lib.episodes];
    if (filterText.trim()) {
      const q = filterText.trim().toLowerCase();
      list = list.filter(
        (ep) =>
          ep.title.toLowerCase().includes(q) ||
          ep.speaker.toLowerCase().includes(q) ||
          ep.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    if (filterDifficulty !== 'all') {
      list = list.filter((ep) => String(ep.difficulty) === filterDifficulty);
    }
    if (filterTag !== 'all') {
      list = list.filter((ep) => ep.tags.includes(filterTag));
    }
    if (filterSpeaker !== 'all') {
      list = list.filter((ep) => ep.speaker === filterSpeaker);
    }
    if (filterDuration === 'short') {
      list = list.filter((ep) => ep.durationSec <= 180);
    } else if (filterDuration === 'medium') {
      list = list.filter((ep) => ep.durationSec > 180 && ep.durationSec <= 420);
    } else if (filterDuration === 'long') {
      list = list.filter((ep) => ep.durationSec > 420);
    }
    if (sortBy === 'difficulty') {
      list.sort((a, b) => b.difficulty - a.difficulty);
    } else if (sortBy === 'duration') {
      list.sort((a, b) => b.durationSec - a.durationSec);
    }

    root.innerHTML = `
      <div class="tt-desktop-only-header">${renderHeader('library')}</div>
      <main class="page-container tt-courses-page">
        <div class="tt-mobile-courses-head">
          <div class="tt-brand-overline">Justmet · TalkTalk</div>
          <h1 class="tt-courses-title">英语自习室</h1>
        </div>
        <section class="library-hero">
          <div class="library-cover" style="background:linear-gradient(145deg, #F6E3DE 0%, #E7B3A4 55%, #C86A5B 100%);">
            <div style="display:flex;align-items:center;justify-content:space-between;z-index:2;">
              <span class="ep-badge">Just met 严选</span>
              <img src="./assets/icon-192.png" alt="JM" style="width:28px;height:28px;border-radius:50%;border:2px solid rgba(255,255,255,0.8);" />
            </div>
            <div style="z-index:2;display:flex;align-items:flex-end;justify-content:space-between;gap:8px;">
              <div>
                <div style="font-size:11px;opacity:0.92;letter-spacing:0.04em;">JUST MET HOUSE</div>
                <div style="font-family:var(--font-serif);font-size:20px;font-weight:700;margin-top:2px;">英语自习室</div>
              </div>
              <img src="./assets/icon-dog-180.png" alt="Darcy" style="width:54px;height:54px;border-radius:50%;border:2px solid rgba(255,255,255,0.88);box-shadow:0 4px 12px rgba(43,31,27,0.22);object-fit:cover;" />
            </div>
          </div>
          <div>
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
              <div>
                <span class="pill" style="margin-bottom:6px;">✦ ${lib.subtitle}</span>
                <h1 style="font-family:var(--font-serif);font-size:24px;">${lib.title}</h1>
              </div>
            </div>
            <p style="font-size:14px;color:var(--muted);margin:10px 0 16px;">${lib.description}</p>
            <div style="display:grid;grid-template-columns:repeat(4,minmax(100px,1fr));gap:12px;">
              <div class="kpi-card" style="padding:12px 14px;">
                <div class="kpi-label">学习进度</div>
                <div class="kpi-value" style="font-size:20px;">${avgProg}%</div>
              </div>
              <div class="kpi-card" style="padding:12px 14px;">
                <div class="kpi-label">已更新剧集</div>
                <div class="kpi-value" style="font-size:20px;">${lib.episodes.length}/${lib.totalPlanned}期</div>
              </div>
              <div class="kpi-card" style="padding:12px 14px;">
                <div class="kpi-label">最近更新</div>
                <div class="kpi-value" style="font-size:16px;padding-top:4px;">${lib.updatedAt}</div>
              </div>
              <div class="kpi-card" style="padding:12px 14px;">
                <div class="kpi-label">生词本</div>
                <div class="kpi-value" style="font-size:20px;">${store.state.vocabBook.length} 词</div>
              </div>
            </div>
          </div>
        </section>

        <section class="darcy-banner">
          <div class="darcy-banner-left">
            <img src="./assets/hosts/darcy_round.webp" alt="Darcy" />
            <div style="font-size:13px;">
              <strong>小屋管家 Darcy 陪读中：</strong>
              <span style="color:var(--muted);">每天精听 1 期 + 跟读 5 句，不知不觉就能开口说地道英语。学累了也可以去隔壁</span>
              <a href="https://justmet.pages.dev" target="_blank" rel="noopener" style="color:var(--accent);font-weight:600;text-decoration:underline;">《重生之我上恋综了》</a>
              <span style="color:var(--muted);">放松一下～</span>
            </div>
          </div>
          <button class="btn btn-soft" id="open-darcy-banner-btn" style="flex-shrink:0;padding:7px 14px;font-size:12px;">
            🐾 打开 Darcy 小窝
          </button>
        </section>

        <section class="filter-bar">
          <input id="lib-search" class="filter-input" type="text" placeholder="搜索剧集标题、博主或话题标签..." value="${escapeHtml(filterText)}" />
          <select id="lib-dur" class="filter-select">
            <option value="all" ${filterDuration === 'all' ? 'selected' : ''}>全部时长</option>
            <option value="short" ${filterDuration === 'short' ? 'selected' : ''}>3 分钟以内</option>
            <option value="medium" ${filterDuration === 'medium' ? 'selected' : ''}>3 – 7 分钟</option>
            <option value="long" ${filterDuration === 'long' ? 'selected' : ''}>7 分钟以上</option>
          </select>
          <select id="lib-diff" class="filter-select">
            <option value="all" ${filterDifficulty === 'all' ? 'selected' : ''}>全部难度（1–5星）</option>
            <option value="1" ${filterDifficulty === '1' ? 'selected' : ''}>★ 1星 · 零基础入门</option>
            <option value="2" ${filterDifficulty === '2' ? 'selected' : ''}>★★ 2星 · 生活轻松听</option>
            <option value="3" ${filterDifficulty === '3' ? 'selected' : ''}>★★★ 3星 · 日常进阶</option>
            <option value="4" ${filterDifficulty === '4' ? 'selected' : ''}>★★★★ 4星 · 访谈/演讲</option>
            <option value="5" ${filterDifficulty === '5' ? 'selected' : ''}>★★★★★ 5星 · 深度挑战</option>
          </select>
          <select id="lib-tag" class="filter-select">
            <option value="all">全部标签</option>
            ${allTags.map((t) => `<option value="${escapeHtml(t)}" ${filterTag === t ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
          </select>
          <select id="lib-speaker" class="filter-select">
            <option value="all">全部博主</option>
            ${allSpeakers.map((sp) => `<option value="${escapeHtml(sp)}" ${filterSpeaker === sp ? 'selected' : ''}>${escapeHtml(sp)}</option>`).join('')}
          </select>
          <select id="lib-sort" class="filter-select">
            <option value="latest" ${sortBy === 'latest' ? 'selected' : ''}>最新优先</option>
            <option value="difficulty" ${sortBy === 'difficulty' ? 'selected' : ''}>难度从高到低</option>
            <option value="duration" ${sortBy === 'duration' ? 'selected' : ''}>时长从长到短</option>
          </select>
          <button class="btn btn-outline" id="lib-reset" style="padding:8px 14px;font-size:13px;">重置</button>
        </section>

        <section class="episode-grid">
          ${list
            .map((ep) => {
              const prog = store.state.episodeProgress[ep.id] || 0;
              const isLearned = !!store.state.learnedEpisodes[ep.id];
              const isFav = !!store.state.favoriteEpisodes[ep.id];
              const isLocked = !!ep.premium && !store.state.unlockedPremium;
              const stars = '★'.repeat(ep.difficulty) + '☆'.repeat(5 - ep.difficulty);
              const epNum = ep.number.replace(/^EP\s*/i, '');
              const epBadgeLabel = /^\d+$/.test(epNum) ? `第 ${Number(epNum)} 期` : ep.number;
              const speakerInitial = (ep.speaker || 'J').trim().charAt(0).toUpperCase();
              return `
                <article class="episode-card" data-ep-id="${ep.id}" data-locked="${isLocked ? '1' : '0'}">
                  <div class="episode-thumb" style="background:${ep.coverImage ? `url('${ep.coverImage}') center/cover no-repeat` : ep.coverGradient};overflow:hidden;">
                    ${
                      !ep.coverImage && ep.mediaUrl && ep.mediaKind !== 'audio'
                        ? `<video src="${ep.mediaUrl}#t=4" muted playsinline preload="metadata" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0;filter:brightness(0.86);"></video>`
                        : ''
                    }
                    <div class="episode-thumb-top" style="position:relative;z-index:2;">
                      <span class="ep-badge">${epBadgeLabel}${isLocked ? ' · 🔒' : ''}</span>
                      <div style="display:flex;gap:6px;align-items:center;">
                        <button class="icon-circle-sm fav-ep-btn ${isFav ? 'active' : ''}" data-fav-ep="${ep.id}" title="收藏剧集">${isFav ? '★' : '☆'}</button>
                        <span class="ep-status ${isLearned ? 'done' : ''}">${isLocked ? '需解锁' : isLearned ? '已学完' : prog > 0 ? '学习中' : '未开始'}</span>
                      </div>
                    </div>
                    <div style="display:flex;align-items:center;justify-content:flex-start;font-size:12px;position:relative;z-index:2;">
                      <span class="stage-pill">${ep.region}</span>
                    </div>
                  </div>
                  <div class="episode-body">
                    <h3 class="episode-title">${escapeHtml(ep.title)}</h3>
                    <div class="episode-meta">
                      <span style="color:var(--accent);letter-spacing:1.5px;font-size:13px;">${stars}</span>
                      <div class="speaker-row">
                        <span class="creator-monogram">${escapeHtml(speakerInitial)}</span>
                        <span>${escapeHtml(ep.speaker)} · ${escapeHtml(ep.region)}</span>
                      </div>
                    </div>
                    <div class="tag-row">
                      ${ep.tags.slice(0, 3).map((t) => `<span class="tag-chip">${escapeHtml(t)}</span>`).join('')}
                      ${ep.tags.length > 3 ? `<span class="tag-chip">+${ep.tags.length - 3}</span>` : ''}
                    </div>
                    <div class="episode-meta episode-meta-duration">
                      <span>${ep.durationLabel}</span>
                    </div>
                    <div class="ep-progress-row">
                      <div class="progress-track">
                        <div class="progress-fill" style="width:${prog}%;"></div>
                      </div>
                      <span class="ep-progress-pct">${prog}%</span>
                    </div>
                  </div>
                </article>
              `;
            })
            .join('')}
        </section>
      </main>
      ${renderMobileBottomNav('library')}
    `;

    bindHeaderEvents(navigate);
    document.getElementById('btn-open-import')?.addEventListener('click', () => openImportModal(navigate));
    document.getElementById('lib-search')?.addEventListener('input', (e) => {
      filterText = e.target.value;
      renderInner();
    });
    document.getElementById('lib-dur')?.addEventListener('change', (e) => {
      filterDuration = e.target.value;
      renderInner();
    });
    document.getElementById('lib-diff')?.addEventListener('change', (e) => {
      filterDifficulty = e.target.value;
      renderInner();
    });
    document.getElementById('lib-tag')?.addEventListener('change', (e) => {
      filterTag = e.target.value;
      renderInner();
    });
    document.getElementById('lib-speaker')?.addEventListener('change', (e) => {
      filterSpeaker = e.target.value;
      renderInner();
    });
    document.getElementById('lib-sort')?.addEventListener('change', (e) => {
      sortBy = e.target.value;
      renderInner();
    });
    document.getElementById('lib-reset')?.addEventListener('click', () => {
      filterText = '';
      filterDifficulty = 'all';
      filterTag = 'all';
      filterSpeaker = 'all';
      filterDuration = 'all';
      sortBy = 'latest';
      renderInner();
    });

    root.querySelectorAll('.episode-card').forEach((card) => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.fav-ep-btn')) return;
        if (card.dataset.locked === '1') {
          openUpsellModal(() => renderInner());
          return;
        }
        navigate(`#/episode/${card.dataset.epId}`);
      });
    });

    root.querySelectorAll('.fav-ep-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const added = store.toggleFavoriteEpisode(btn.dataset.favEp);
        showToast(added ? '已收藏该剧集' : '已取消收藏');
        renderInner();
      });
    });
  };

  renderInner();
}

// 4. 全局生词本页面
export function renderVocabPage(root, navigate) {
  const renderInner = () => {
    const items = store.state.vocabBook;
    root.innerHTML = `
      <div class="tt-desktop-only-header">${renderHeader('vocab')}</div>
      <main class="page-container tt-mobile-padded-page">
        <div class="tt-mobile-courses-head">
          <div class="tt-brand-overline">Justmet · TalkTalk</div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
          <div>
            <h1 style="font-family:var(--font-serif);font-size:26px;">我的生词本</h1>
            <p style="font-size:14px;color:var(--muted);">共收藏 ${items.length} 个重点词汇与地道表达</p>
          </div>
          <a href="#/library" class="btn btn-primary">返回英语自习室</a>
        </div>
        <div class="product-showcase-grid">
          ${
            items.length === 0
              ? `<div class="kpi-card" style="grid-column:1/-1;text-align:center;padding:40px;">还没有收藏生词，去精听工作台点击任意单词即可加入生词本！</div>`
              : items
                  .map((item) => {
                    const entry = lookupWord(item.key) || {
                      headword: item.key,
                      pos: 'word',
                      us: '',
                      meanings: [{ zh: '已收藏词条' }],
                      exampleEn: ''
                    };
                    return `
                      <article class="product-card">
                        <div class="product-badge-row">
                          <strong style="font-size:18px;color:var(--accent);">${escapeHtml(entry.headword)}</strong>
                          <span class="pill">${escapeHtml(entry.pos)}</span>
                        </div>
                        <div style="font-size:12px;color:var(--muted);">US ${escapeHtml(entry.us)} · 收藏于 ${item.addedAt}</div>
                        <p class="product-desc">${escapeHtml(entry.meanings[0]?.zh || '')}</p>
                        ${entry.exampleEn ? `<p style="font-size:12px;color:var(--muted);font-style:italic;">"${escapeHtml(entry.exampleEn)}"</p>` : ''}
                        <div class="product-actions">
                          <button class="btn btn-outline remove-vocab-btn" data-key="${escapeHtml(item.key)}" style="padding:6px 12px;font-size:12px;">移出生词本</button>
                        </div>
                      </article>
                    `;
                  })
                  .join('')
          }
        </div>
      </main>
      ${renderMobileBottomNav('vocab')}
    `;
    bindHeaderEvents(navigate);
    root.querySelectorAll('.remove-vocab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        store.toggleVocab(btn.dataset.key);
        showToast('已移出生词本');
        renderInner();
      });
    });
  };
  renderInner();
}

// 5. 自有素材导入弹窗（支持粘贴双语台词快速生成新剧集）
export function openImportModal(navigate) {
  const modalRoot = document.getElementById('modal-root');
  modalRoot.innerHTML = `
    <div class="modal-backdrop" id="import-backdrop">
      <div class="modal-card" style="max-width:600px;">
        <div class="modal-header">
          <h3>导入自定义英语素材（新建剧集）</h3>
          <button class="icon-circle-sm" id="close-import">✕</button>
        </div>
        <div class="modal-body">
          <p style="font-size:13px;color:var(--muted);">
            你可以将自己原创或拥有授权的英文演讲、播客双语台词粘贴到下方（每两行为一句：第一行英文，第二行中文），保存后立刻生成可精听、跟读、评测的专属剧集。
          </p>
          <div class="form-group">
            <label class="form-label">剧集标题</label>
            <input class="form-input" id="imp-title" placeholder="例如：EP 07 · 职场英语精听实战" />
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div class="form-group">
              <label class="form-label">选择本地视频/音频（可选 MP4 / MP3）</label>
              <input class="form-input" id="imp-media-file" type="file" accept="video/*,audio/*" style="padding:8px;" />
            </div>
            <div class="form-group">
              <label class="form-label">选择本地字幕文件（可选 .srt / .vtt / .txt）</label>
              <input class="form-input" id="imp-srt-file" type="file" accept=".srt,.vtt,.txt" style="padding:8px;" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">或者直接粘贴双语字幕内容（支持 SRT 格式，或每两行：英文换行中文）</label>
            <textarea class="form-input" id="imp-script" rows="5" placeholder="Welcome back to Just met House!\n欢迎回到刚认识小屋 · 英语自习室！\nLet's practice speaking naturally every single day.\n让我们每天一起自然地练习英语口语。"></textarea>
          </div>
          <div style="font-size:12px;color:var(--muted);background:var(--bg);padding:9px 12px;border-radius:10px;border:1px solid var(--border);">
            💡 提示：如需永久上架到本地资料库，只需把视频和 <code>.srt</code> 放入项目的 <code>content/episodes/你的剧集名/</code> 文件夹并运行 <code>python3 scripts/sync_episodes.py</code> 即可！
          </div>
          <div style="display:flex;justify-content:flex-end;gap:10px;">
            <button class="btn btn-outline" id="cancel-import">取消</button>
            <button class="btn btn-primary" id="save-import">生成并立即学习</button>
          </div>
        </div>
      </div>
    </div>
  `;

  const close = () => { modalRoot.innerHTML = ''; };
  document.getElementById('close-import').addEventListener('click', close);
  document.getElementById('cancel-import').addEventListener('click', close);
  document.getElementById('import-backdrop').addEventListener('click', (e) => {
    if (e.target.id === 'import-backdrop') close();
  });

  const parseClientSrt = (rawText) => {
    const text = rawText.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
    const toSec = (ts) => {
      const parts = ts.replace(',', '.').split(':');
      if (parts.length === 3) return Number(parts[0]) * 3600 + Number(parts[1]) * 60 + Number(parts[2]);
      if (parts.length === 2) return Number(parts[0]) * 60 + Number(parts[1]);
      return 0;
    };
    const timeRe = /(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})/;
    if (timeRe.test(text)) {
      const blocks = text.split(/\n{2,}/);
      const out = [];
      blocks.forEach((b) => {
        const lines = b.split('\n').map((l) => l.trim()).filter(Boolean);
        const tIdx = lines.findIndex((l) => timeRe.test(l));
        if (tIdx === -1) return;
        const m = lines[tIdx].match(timeRe);
        const content = lines.slice(tIdx + 1).map((l) => l.replace(/<[^>]+>/g, '').trim()).filter(Boolean);
        if (!content.length) return;
        let en = content[0];
        let zh = content.slice(1).join(' ');
        if (zh && /[\u4e00-\u9fff]/.test(en) && !/[\u4e00-\u9fff]/.test(zh)) [en, zh] = [zh, en];
        out.push({
          id: out.length + 1,
          start: Number(toSec(m[1]).toFixed(2)),
          end: Math.max(Number(toSec(m[2]).toFixed(2)), Number(toSec(m[1]).toFixed(2)) + 1.5),
          speaker: 'Speaker',
          en,
          ipa: '',
          zh,
          highlights: []
        });
      });
      return out;
    }
    const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
    const out = [];
    for (let i = 0; i < lines.length; i += 2) {
      const idx = out.length + 1;
      out.push({
        id: idx,
        start: (idx - 1) * 7,
        end: idx * 7,
        speaker: 'Speaker',
        en: lines[i],
        ipa: '',
        zh: lines[i + 1] || '',
        highlights: []
      });
    }
    return out;
  };

  document.getElementById('imp-srt-file')?.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    document.getElementById('imp-script').value = text;
    if (!document.getElementById('imp-title').value.trim()) {
      document.getElementById('imp-title').value = file.name.replace(/\.[^.]+$/, '');
    }
    showToast(`已读取字幕文件：${file.name}`);
  });

  document.getElementById('save-import').addEventListener('click', () => {
    const mediaFile = document.getElementById('imp-media-file')?.files?.[0] || null;
    const mediaUrl = mediaFile ? URL.createObjectURL(mediaFile) : '';
    const mediaKind = mediaFile ? (mediaFile.type.startsWith('audio') ? 'audio' : 'video') : '';
    const title =
      document.getElementById('imp-title').value.trim() ||
      (mediaFile ? mediaFile.name.replace(/\.[^.]+$/, '') : '自定义精听练习剧集');
    const raw = document.getElementById('imp-script').value.trim();
    let sentences = raw ? parseClientSrt(raw) : [];
    if (sentences.length === 0 && !mediaUrl) {
      showToast('请选择视频/音频，或输入双语字幕内容');
      return;
    }
    if (sentences.length === 0) {
      sentences = [{ id: 1, start: 0, end: 15, speaker: 'Speaker', en: 'Media loaded — add an .srt subtitle file for synced lines.', ipa: '', zh: '视频已加载，导入 .srt 字幕即可实现逐句同步精听。', highlights: [] }];
    }
    const durSec = Math.max(10, Math.round(sentences[sentences.length - 1].end || 60));
    const newId = `ep-custom-${Date.now()}`;
    const lib = LIBRARIES[0];
    lib.episodes.unshift({
      id: newId,
      number: `EP ${String(lib.episodes.length + 1).padStart(2, '0')}`,
      title,
      speaker: store.state.user?.name || 'Just Met',
      speakerAvatar: './assets/hosts/cici_round.webp',
      region: mediaUrl ? '本地视频' : '自定义素材',
      difficulty: 3,
      durationSec: durSec,
      durationLabel: `${String(Math.floor(durSec / 60)).padStart(2, '0')}:${String(durSec % 60).padStart(2, '0')}`,
      date: new Date().toISOString().slice(0, 10).replace(/-/g, '/'),
      tags: ['本地导入', mediaUrl ? '真实视频' : '精听跟读'],
      coverGradient: 'linear-gradient(135deg, #E8C5B8 0%, #B86B5A 100%)',
      mediaUrl,
      mediaKind,
      sceneBadge: mediaUrl ? '本地真实视频同步精听' : 'Custom Studio · 自建素材',
      sentences
    });
    close();
    showToast('新剧集已创建！');
    navigate(`#/episode/${newId}`);
  });
}

function bindHeaderEvents(navigate) {
  document.getElementById('btn-logout')?.addEventListener('click', () => {
    store.logout();
    showToast('已退出登录');
    navigate('#/login');
  });
}

// 6. 二次付费：Just Met 宇宙进阶权益与 AI 评测积分中心
export function renderMembershipPage(root, navigate) {
  const renderInner = () => {
    root.innerHTML = `
      <div class="tt-desktop-only-header">${renderHeader('membership')}</div>
      <main class="page-container tt-mobile-padded-page">
        <div class="tt-mobile-courses-head">
          <div class="tt-brand-overline">Justmet · TalkTalk</div>
        </div>
        <section style="display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:24px;">
          <div>
            <span class="pill" style="margin-bottom:8px;">✦ 300 期精听课程已包含在基础权益 · 以下为进阶提效增值服务</span>
            <h1 style="font-family:var(--font-serif);font-size:28px;">Just Met 进阶功能与积分中心</h1>
            <p style="font-size:14px;color:var(--muted);margin-top:4px;">300 期精听跟读内容无需二次解锁；可按需加购 AI 精评、1v1 口语陪练与深度精讲工具</p>
          </div>
          <div class="kpi-card" style="padding:12px 18px;display:flex;align-items:center;gap:16px;">
            <div>
              <div class="kpi-label">当前 AI 评测积分</div>
              <div class="kpi-value" style="font-size:22px;color:var(--accent);">${store.state.credits} 点</div>
            </div>
            <div style="width:1px;height:32px;background:var(--border);"></div>
            <div>
              <div class="kpi-label">进阶提效插件</div>
              <div style="font-size:14px;font-weight:700;color:${store.state.unlockedPremium ? '#166534' : 'var(--muted)'};">
                ${store.state.unlockedPremium ? '✓ 已激活 PRO 提效' : '标准版（已享全部 300 期）'}
              </div>
            </div>
          </div>
        </section>

        <section class="episode-grid" style="margin-bottom:26px;">
          ${UPSELL_PACKS.map(
            (p) => `
            <article class="product-card ${p.id === 'pack-ai-coach' ? 'featured' : ''}" style="padding:24px;">
              <div class="product-badge-row">
                <span class="pill">${escapeHtml(p.badge)}</span>
                <span style="font-size:12px;color:var(--muted);">演示码：${escapeHtml(p.demoCode)}</span>
              </div>
              <h3 class="product-title" style="font-size:19px;">${escapeHtml(p.title)}</h3>
              <div style="margin:6px 0;">
                <span style="font-family:var(--font-serif);font-size:30px;font-weight:700;color:var(--accent);">${escapeHtml(p.price)}</span>
                <span style="font-size:13px;color:var(--muted);">${escapeHtml(p.unit)}</span>
              </div>
              <p class="product-desc">${escapeHtml(p.desc)}</p>
              <ul style="list-style:none;display:flex;flex-direction:column;gap:6px;margin:8px 0 14px;font-size:13px;">
                ${p.perks.map((perk) => `<li>✓ ${escapeHtml(perk)}</li>`).join('')}
              </ul>
              <div class="product-actions">
                <button class="btn btn-primary demo-redeem-btn" data-code="${escapeHtml(p.demoCode)}" style="width:100%;">
                  立即体验兑换解锁（${escapeHtml(p.demoCode)}）
                </button>
              </div>
            </article>
          `
          ).join('')}
        </section>

        <section class="kpi-card" style="padding:24px;">
          <h3 style="font-family:var(--font-serif);font-size:18px;margin-bottom:6px;">已有小红书橱窗 / 官方权益兑换码？</h3>
          <p style="font-size:13px;color:var(--muted);margin-bottom:14px;">输入兑换码立即激活对应进阶剧集或 AI 评测积分（演示体验码：<code>JM-PRO-2026</code> / <code>JM-AI-30</code> / <code>JM-VIP-2026</code>）</p>
          <div style="display:flex;gap:10px;max-width:520px;">
            <input class="form-input" id="redeem-input" placeholder="输入权益兑换码，例如 JM-PRO-2026" />
            <button class="btn btn-primary" id="redeem-submit" style="flex-shrink:0;">立即兑换</button>
          </div>
        </section>
      </main>
      ${renderMobileBottomNav('membership')}
    `;

    bindHeaderEvents(navigate);
    root.querySelectorAll('.demo-redeem-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const res = store.redeemCode(btn.dataset.code);
        showToast(res.message);
        renderInner();
      });
    });
    document.getElementById('redeem-submit')?.addEventListener('click', () => {
      const val = document.getElementById('redeem-input').value;
      const res = store.redeemCode(val);
      showToast(res.message);
      if (res.ok) renderInner();
    });
  };
  renderInner();
}

export function openUpsellModal(onUnlocked) {
  const modalRoot = document.getElementById('modal-root');
  modalRoot.innerHTML = `
    <div class="modal-backdrop" id="upsell-bg">
      <div class="modal-card" style="max-width:580px;">
        <div class="modal-header">
          <h3>🔒 解锁 Just Met 进阶专享权益</h3>
          <button class="icon-circle-sm" id="upsell-close">✕</button>
        </div>
        <div class="modal-body">
          <p style="font-size:14px;color:var(--muted);">
            本内容属于 <strong>刚认识小屋 · 英语自习室进阶功能</strong>（含 AI 逐词音素级精评、情景口语陪练与深度精讲插件）。
          </p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            ${UPSELL_PACKS.slice(0, 2)
              .map(
                (p) => `
                <div style="background:var(--bg);border:1px solid var(--border);border-radius:14px;padding:14px;">
                  <span class="pill" style="margin-bottom:6px;">${escapeHtml(p.badge)}</span>
                  <div style="font-weight:700;font-size:14px;margin-bottom:4px;">${escapeHtml(p.title)}</div>
                  <div style="font-family:var(--font-serif);font-size:22px;color:var(--accent);font-weight:700;margin-bottom:8px;">${escapeHtml(p.price)} <span style="font-size:12px;color:var(--muted);">${escapeHtml(p.unit)}</span></div>
                  <button class="btn btn-soft quick-unlock-btn" data-code="${escapeHtml(p.demoCode)}" style="width:100%;padding:7px 10px;font-size:12px;">体验激活 (${escapeHtml(p.demoCode)})</button>
                </div>
              `
              )
              .join('')}
          </div>
          <div style="display:flex;gap:8px;margin-top:4px;">
            <input class="form-input" id="modal-redeem-input" placeholder="输入兑换码（如 JM-PRO-2026）" />
            <button class="btn btn-primary" id="modal-redeem-btn" style="flex-shrink:0;">兑换解锁</button>
          </div>
        </div>
      </div>
    </div>
  `;
  const close = () => { modalRoot.innerHTML = ''; };
  document.getElementById('upsell-close').addEventListener('click', close);
  document.getElementById('upsell-bg').addEventListener('click', (e) => { if (e.target.id === 'upsell-bg') close(); });
  const doRedeem = (code) => {
    const res = store.redeemCode(code);
    showToast(res.message);
    if (res.ok) {
      close();
      if (onUnlocked) onUnlocked();
    }
  };
  document.getElementById('modal-redeem-btn').addEventListener('click', () => {
    doRedeem(document.getElementById('modal-redeem-input').value);
  });
  modalRoot.querySelectorAll('.quick-unlock-btn').forEach((b) => {
    b.addEventListener('click', () => doRedeem(b.dataset.code));
  });
}
