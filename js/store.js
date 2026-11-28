// 本地持久化状态管理（登录信息、学习进度、生词本、收藏句、评测记录、偏好设置）
import { THEMES } from './data.js';

export const USER_AVATARS = [
  './assets/avatars/animal_01.png',
  './assets/avatars/animal_02.png',
  './assets/avatars/animal_03.png',
  './assets/avatars/animal_04.png',
  './assets/avatars/animal_05.png',
  './assets/avatars/animal_06.png',
  './assets/avatars/animal_07.png',
  './assets/avatars/animal_08.png',
];

const STORAGE_KEY = 'justmet_universe_state_v1';

const defaultState = {
  user: null, // { name, email, avatar }
  themeId: 'justmet-blush',
  fontSize: 18,
  showIpa: false,
  autoContinue: true,
  inVideoSubtitle: false,
  blindListening: false,
  screenVocab: false,
  playbackRate: 1.0,
  loopCount: 1, // 1,2,3,5,10,0(∞)
  audioOnly: false,
  vocabBook: [
    { key: 'on the same page', addedAt: '2026-11-25' },
    { key: 'break the ice', addedAt: '2026-11-25' }
  ],
  starredSentences: {}, // `${epId}:${sentenceId}` -> true
  learnedEpisodes: {}, // epId -> true
  episodeProgress: {},
  favoriteEpisodes: {},
  evalScores: {}, // `${epId}:${sentenceId}` -> evalResult
  credits: 5, // AI 发音评测积分余额
  unlockedPremium: false, // 是否已解锁进阶专享剧集
  redeemedCodes: []
};

class Store {
  constructor() {
    this.state = this.load();
    this.listeners = new Set();
  }

  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return structuredClone(defaultState);
      return { ...structuredClone(defaultState), ...JSON.parse(raw) };
    } catch {
      return structuredClone(defaultState);
    }
  }

  save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
    } catch {}
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  notify() {
    this.save();
    this.listeners.forEach((fn) => fn(this.state));
  }

  set(patch) {
    Object.assign(this.state, patch);
    this.notify();
  }

  login({ name, email, avatar }) {
    const safeAvatar = USER_AVATARS.includes(avatar) ? avatar : USER_AVATARS[1];
    this.state.user = {
      name: name?.trim() || 'Mila',
      email: email?.trim() || 'guest@justmet.universe',
      avatar: safeAvatar
    };
    this.notify();
  }

  updateProfile({ name, avatar }) {
    if (!this.state.user) {
      this.login({ name, avatar });
      return;
    }
    if (name && name.trim()) this.state.user.name = name.trim();
    if (avatar && USER_AVATARS.includes(avatar)) this.state.user.avatar = avatar;
    this.notify();
  }

  logout() {
    this.state.user = null;
    this.notify();
  }

  toggleVocab(wordKey) {
    const k = wordKey.toLowerCase();
    const exists = this.state.vocabBook.findIndex((item) => item.key === k);
    if (exists >= 0) {
      this.state.vocabBook.splice(exists, 1);
      this.notify();
      return false;
    } else {
      this.state.vocabBook.unshift({ key: k, addedAt: new Date().toISOString().slice(0, 10) });
      this.notify();
      return true;
    }
  }

  hasVocab(wordKey) {
    const k = wordKey.toLowerCase();
    return this.state.vocabBook.some((item) => item.key === k);
  }

  toggleStarSentence(epId, sentenceId) {
    const k = `${epId}:${sentenceId}`;
    this.state.starredSentences[k] = !this.state.starredSentences[k];
    if (!this.state.starredSentences[k]) delete this.state.starredSentences[k];
    this.notify();
    return !!this.state.starredSentences[k];
  }

  toggleLearnedEpisode(epId) {
    this.state.learnedEpisodes[epId] = !this.state.learnedEpisodes[epId];
    if (this.state.learnedEpisodes[epId]) {
      this.state.episodeProgress[epId] = 100;
    }
    this.notify();
    return !!this.state.learnedEpisodes[epId];
  }

  toggleFavoriteEpisode(epId) {
    this.state.favoriteEpisodes[epId] = !this.state.favoriteEpisodes[epId];
    this.notify();
    return !!this.state.favoriteEpisodes[epId];
  }

  updateEpisodeProgress(epId, percent) {
    const prev = this.state.episodeProgress[epId] || 0;
    if (percent > prev) {
      this.state.episodeProgress[epId] = Math.min(100, Math.round(percent));
      this.notify();
    }
  }

  saveEvalScore(epId, sentenceId, evalResult) {
    this.state.evalScores[`${epId}:${sentenceId}`] = evalResult;
    this.notify();
  }

  consumeCredit() {
    if (this.state.credits <= 0) return false;
    this.state.credits -= 1;
    this.notify();
    return true;
  }

  redeemCode(rawCode) {
    const code = String(rawCode || '').trim().toUpperCase();
    if (!code) return { ok: false, message: '请输入有效的权益兑换码' };
    if (code === 'JM-AI-30') {
      this.state.credits += 30;
      this.state.redeemedCodes.push(code);
      this.notify();
      return { ok: true, message: '兑换成功！已到账 30 点 AI 发音评测积分 🎉' };
    }
    if (code === 'JM-PRO-2026') {
      this.state.unlockedPremium = true;
      this.state.credits += 30;
      this.state.redeemedCodes.push(code);
      this.notify();
      return { ok: true, message: '兑换成功！已解锁全部进阶专享剧集 + 到账 30 点 AI 评测积分 🎉' };
    }
    if (code === 'JM-VIP-2026') {
      this.state.unlockedPremium = true;
      this.state.credits += 80;
      this.state.redeemedCodes.push(code);
      this.notify();
      return { ok: true, message: '兑换成功！已激活刚认识小屋进阶年卡权益 + 到账 80 点积分 ✦' };
    }
    return { ok: false, message: '兑换码无效，可尝试体验码：JM-PRO-2026 或 JM-AI-30' };
  }

  getTheme() {
    return THEMES.find((t) => t.id === this.state.themeId) || THEMES[0];
  }
}

export const store = new Store();

export function applyThemeVars(theme) {
  const root = document.documentElement;
  root.style.setProperty('--bg', theme.bg);
  root.style.setProperty('--card', theme.card);
  root.style.setProperty('--border', theme.border);
  root.style.setProperty('--text', theme.text);
  root.style.setProperty('--muted', theme.muted);
  root.style.setProperty('--accent', theme.accent);
  root.style.setProperty('--accent-soft', theme.accentSoft);
  root.dataset.dark = theme.dark ? 'true' : 'false';
}

export function showToast(message) {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const el = document.createElement('div');
  el.className = 'toast-item';
  el.textContent = message;
  root.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 260);
  }, 2400);
}
