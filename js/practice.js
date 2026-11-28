// 沉浸式英语精听与跟读工作台（完整复刻 SayBreeze 全部核心交互）
import { LIBRARIES, THEMES, findEpisodeById, lookupWord, saveCachedWord, isCleanDictEntry } from './data.js';
import { store, applyThemeVars, showToast } from './store.js';
import { speechEngine } from './speech.js';
import { openUpsellModal } from './views.js';

function escapeHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function renderPracticeWorkspace(root, episodeId, navigate) {
  const { library, episode } = findEpisodeById(episodeId);

  // Local workspace UI state
  let isDisposed = false;
  let currentIdx = 0;
  let isPlaying = false;
  let mode = 'bilingual'; // 'bilingual' | 'shadow' | 'cloze' | 'dictation'
  let langDisplay = 'both'; // 'both' (双语) | 'en' (EN) | 'zh' (ZH)
  let savedAutoContinue = store.state.autoContinue;
  let showTopNav = false;
  let pipMode = false;
  let abRange = null; // { startIdx, endIdx }
  let currentLoopRemaining = 0;
  let recordingSentenceId = null;
  let precisionTimer = null;
  let stallPauseTimer = null;
  let seekGuardUntil = 0;
  let userManualScrollUntil = 0;
  let isProgrammaticScroll = false;
  let lastListSignature = '';
  const revealedCloze = new Set();
  const dictationAnswers = {}; // `${sentId}:${hIdx}` -> string
  const dictationReveal = new Set();

  // 确保进入普通模式时默认开启连播（避免上次在跟读模式留下的句停锁死连续播放）
  if (!store.state.autoContinue) {
    store.set({ autoContinue: true });
    savedAutoContinue = true;
  }

  // Persistent HTML5 video/audio elements — mounted ONCE in mountShell() and NEVER detached on sentence change or audioOnly toggle
  const hasRealMedia = Boolean(episode.mediaUrl);
  const skipRanges = Array.isArray(episode.skipRanges) ? episode.skipRanges : [];
  let mediaEl = null;
  let companionAudioEl = null;

  // 纯音频模式下以伴音 companionAudioEl 作为主时钟，彻底与隐藏视频解耦（即使视频卡顿也不影响纯音频播放）
  function isAudioClockMode() {
    return Boolean(store.state.audioOnly && companionAudioEl);
  }

  function getClockEl() {
    return isAudioClockMode() ? companionAudioEl : mediaEl;
  }

  function syncAudioRate() {
    const rate = store.state.playbackRate;
    if (mediaEl) mediaEl.playbackRate = rate;
    if (companionAudioEl) companionAudioEl.playbackRate = rate;
  }

  function clearStallTimer() {
    if (stallPauseTimer) {
      clearTimeout(stallPauseTimer);
      stallPauseTimer = null;
    }
  }

  function seekMediaTo(targetSec, autoPlay = true) {
    const clockEl = getClockEl();
    if (!clockEl) return;
    const rate = store.state.playbackRate;
    const safeSec = Math.max(0, targetSec);
    seekGuardUntil = Date.now() + 480;
    clearStallTimer();

    if (isAudioClockMode()) {
      // 纯音频主钟模式：仅驱动 companionAudioEl，保持隐藏 video 暂停不拖累性能
      if (mediaEl && !mediaEl.paused) mediaEl.pause();
      companionAudioEl.playbackRate = rate;
      companionAudioEl.currentTime = safeSec;
      if (autoPlay) companionAudioEl.play().catch(() => {});
      return;
    }

    mediaEl.playbackRate = rate;
    mediaEl.currentTime = safeSec;
    if (companionAudioEl) {
      companionAudioEl.playbackRate = rate;
      companionAudioEl.currentTime = safeSec;
    }
    if (autoPlay) {
      mediaEl.play().catch(() => {});
      if (companionAudioEl && mediaEl.readyState >= 2) {
        companionAudioEl.play().catch(() => {});
      }
    }
  }

  function handleAudioOnlyModeChange() {
    if (!mediaEl || !companionAudioEl) return;
    const rate = store.state.playbackRate;
    seekGuardUntil = Date.now() + 450;
    if (isAudioClockMode()) {
      const t = mediaEl.currentTime;
      mediaEl.pause();
      companionAudioEl.playbackRate = rate;
      if (Math.abs(companionAudioEl.currentTime - t) > 0.25) {
        companionAudioEl.currentTime = t;
      }
      if (isPlaying && companionAudioEl.paused) {
        companionAudioEl.play().catch(() => {});
      }
    } else {
      const t = companionAudioEl.currentTime;
      mediaEl.playbackRate = rate;
      mediaEl.currentTime = t;
      if (isPlaying) {
        mediaEl.play().catch(() => {});
      }
    }
  }

  if (hasRealMedia) {
    mediaEl = document.createElement(episode.mediaKind === 'audio' ? 'audio' : 'video');
    mediaEl.src = episode.mediaUrl;
    mediaEl.playsInline = true;
    mediaEl.preload = 'auto';
    mediaEl.playbackRate = store.state.playbackRate;

    if (episode.audioUrl) {
      companionAudioEl = document.createElement('audio');
      companionAudioEl.src = episode.audioUrl;
      companionAudioEl.preload = 'auto';
      companionAudioEl.volume = 1.0;
      companionAudioEl.playbackRate = store.state.playbackRate;
      mediaEl.muted = true; // 声音由独立音轨负责，防止浏览器静音策略拦截

      // 视频真正持续卡顿超过 240ms 才暂停伴音，避免句首解码短暂 waiting 导致“复读杂音”
      mediaEl.addEventListener('waiting', () => {
        if (isAudioClockMode() || !companionAudioEl || companionAudioEl.paused) return;
        clearStallTimer();
        stallPauseTimer = setTimeout(() => {
          if (!isAudioClockMode() && mediaEl && (mediaEl.readyState < 3 || mediaEl.paused) && companionAudioEl && !companionAudioEl.paused) {
            companionAudioEl.pause();
          }
        }, 240);
      });

      mediaEl.addEventListener('playing', () => {
        if (isAudioClockMode()) return;
        clearStallTimer();
        if (isPlaying && companionAudioEl) {
          companionAudioEl.playbackRate = store.state.playbackRate;
          if (Math.abs(companionAudioEl.currentTime - mediaEl.currentTime) > 0.35) {
            companionAudioEl.currentTime = mediaEl.currentTime;
          }
          if (companionAudioEl.paused) {
            companionAudioEl.play().catch(() => {});
          }
        }
      });

      // seek 保护期内或纯音频主钟模式下，视频的 pause 事件绝不掐断伴音！
      mediaEl.addEventListener('pause', () => {
        if (isAudioClockMode() || Date.now() < seekGuardUntil) return;
        clearStallTimer();
        if (!isPlaying && companionAudioEl && !companionAudioEl.paused) {
          companionAudioEl.pause();
        }
      });
    }

    let lastDriftFixAt = 0;
    const resolveSentenceIndexAtTime = (sents, t, current) => {
      if (!sents.length) return 0;
      if (t < sents[0].start) return 0;
      // 严格按 t >= s.start 匹配；若 t 处于两句之间的间隙 [cur.end, next.start)，继续停留在上一句，绝不提前切到下一句
      let matched = -1;
      for (let i = 0; i < sents.length; i++) {
        if (t >= sents[i].start) {
          matched = i;
        } else {
          break;
        }
      }
      return matched === -1 ? current : matched;
    };

    const checkMediaBoundary = () => {
      const clockEl = getClockEl();
      if (isDisposed || !isPlaying || !clockEl) return;
      if (clockEl.paused || clockEl.seeking || clockEl.readyState < 2) return;
      const now = Date.now();
      // 画面可见时严格以视频帧时间（mediaEl.currentTime）为准；纯音频模式以伴音为准
      const t = clockEl.currentTime;

      // 双轨视频模式下收紧伴音漂移阈值（>0.18s 即拉齐到视频帧），防止伴音/视频漂移带动字幕错位
      if (
        !isAudioClockMode() &&
        companionAudioEl &&
        !companionAudioEl.paused &&
        now > seekGuardUntil &&
        now - lastDriftFixAt > 1200 &&
        Math.abs(companionAudioEl.currentTime - t) > 0.18
      ) {
        companionAudioEl.currentTime = t;
        lastDriftFixAt = now;
      }

      const sents = episode.sentences;
      if (!sents.length) return;
      const firstSent = sents[0];
      const lastSent = sents[sents.length - 1];

      // 1) 跳过片头纯音乐（0 -> 第一句 > 0.5s，如 EP 10 / EP 20 约 13 秒片头）
      if (now > seekGuardUntil && firstSent.start > 0.5 && t < firstSent.start - 0.18) {
        setActiveIndex(0, true);
        seekMediaTo(firstSent.start, true);
        return;
      }

      // 2) 检查当前句内部是否包含纯音乐/空白 skipRange（如 EP 39 #1/#62/#153）：跳过后继续留在同一句！
      const curSent = sents[currentIdx];
      if (curSent && now > seekGuardUntil && skipRanges.length > 0) {
        for (let r = 0; r < skipRanges.length; r++) {
          const [rStart, rEnd] = skipRanges[r];
          const isInsideCur = rStart >= curSent.start + 0.05 && rEnd <= curSent.end - 0.05;
          if (isInsideCur && rEnd - rStart >= 1.2 && t >= rStart + 0.06 && t < rEnd - 0.08) {
            seekMediaTo(rEnd, true);
            return;
          }
        }
      }

      // 3) 检查当前句结束边界（严格到达 curSent.end 后才处理，绝不提前 40ms 抢切）
      if (curSent && now > seekGuardUntil && t >= curSent.end) {
        if (currentLoopRemaining > 1) {
          currentLoopRemaining -= 1;
          seekMediaTo(curSent.start, true);
          return;
        }
        if (abRange && currentIdx >= abRange.endIdx) {
          playSentenceAt(abRange.startIdx, true);
          return;
        }
        // 句末停住时保持停留在当前句，绝不提前切到下一句
        if (!store.state.autoContinue || mode === 'shadow' || mode === 'dictation') {
          stopPlayback();
          syncPlayStateUI();
          return;
        }
        // 最后一句播完立即暂停，绝不继续播放片尾纯音乐（如 EP 09 约 58 秒片尾）
        if (currentIdx >= sents.length - 1) {
          stopPlayback();
          syncPlayStateUI();
          return;
        }
        const nextSent = sents[currentIdx + 1];
        const gap = nextSent.start - curSent.end;
        // 句间空隙 >= 2.0s 时自动跳过纯音乐/长空白；< 2.0s 的自然口播停顿保持平滑连播，且等到 t >= nextSent.start 才切换高亮
        if (gap >= 2.0) {
          const lc = store.state.loopCount;
          currentLoopRemaining = lc === 0 ? 9999 : lc;
          setActiveIndex(currentIdx + 1, false);
          seekMediaTo(nextSent.start, true);
          return;
        }
      }

      // 4) 兜底：若已播到最后一句之后，立即停止
      if (now > seekGuardUntil && t >= lastSent.end) {
        if (abRange) {
          playSentenceAt(abRange.startIdx, true);
        } else {
          stopPlayback();
          syncPlayStateUI();
        }
        return;
      }

      // 5) 若连播落入长纯音乐 / skipRanges 区间（>= 2.0s），直接跳到该区间后的下一句（若无下一句则停止）
      if (now > seekGuardUntil && store.state.autoContinue && skipRanges.length > 0) {
        for (let r = 0; r < skipRanges.length; r++) {
          const [rStart, rEnd] = skipRanges[r];
          if (rEnd - rStart >= 2.0 && t >= rStart + 0.08 && t < rEnd - 0.08) {
            const nextAfterSkip = sents.findIndex((s) => s.start >= rEnd - 0.15);
            if (nextAfterSkip === -1) {
              stopPlayback();
              syncPlayStateUI();
            } else {
              const lc = store.state.loopCount;
              currentLoopRemaining = lc === 0 ? 9999 : lc;
              setActiveIndex(nextAfterSkip, false);
              seekMediaTo(sents[nextAfterSkip].start, true);
            }
            return;
          }
        }
      }

      // 6) 自然连播跨句：只有时钟真正进入下一句的 start（t >= nextSent.start）才切换高亮、当前句与视频遮罩字幕
      const foundIdx = resolveSentenceIndexAtTime(sents, t, currentIdx);
      if (foundIdx !== currentIdx) {
        const lc = store.state.loopCount;
        currentLoopRemaining = lc === 0 ? 9999 : lc;
        setActiveIndex(foundIdx, false);
      }
    };

    mediaEl.addEventListener('timeupdate', () => {
      if (!isAudioClockMode()) checkMediaBoundary();
    });
    if (companionAudioEl) {
      companionAudioEl.addEventListener('timeupdate', () => {
        if (isAudioClockMode()) checkMediaBoundary();
      });
      companionAudioEl.addEventListener('ended', () => {
        if (!isAudioClockMode()) return;
        if (abRange) {
          playSentenceAt(abRange.startIdx, true);
        } else {
          isPlaying = false;
          syncPlayStateUI();
        }
      });
    }
    precisionTimer = setInterval(checkMediaBoundary, 40);

    mediaEl.addEventListener('ended', () => {
      if (isAudioClockMode()) return;
      clearStallTimer();
      if (companionAudioEl) companionAudioEl.pause();
      if (abRange) {
        playSentenceAt(abRange.startIdx, true);
      } else {
        isPlaying = false;
        syncPlayStateUI();
      }
    });
  }

  // Collect all episode key words
  const allEpisodeKeywords = [];
  const seenKeys = new Set();
  episode.sentences.forEach((s) => {
    (s.highlights || []).forEach((h) => {
      if (!seenKeys.has(h.key)) {
        seenKeys.add(h.key);
        allEpisodeKeywords.push({ ...h, sentenceId: s.id, dict: lookupWord(h.key) });
      }
    });
  });

  function stopPlayback() {
    isPlaying = false;
    clearStallTimer();
    if (mediaEl) {
      mediaEl.pause();
    }
    if (companionAudioEl) {
      companionAudioEl.pause();
    }
    speechEngine.stopSpeak();
  }

  function setActiveIndex(nextIdx, forceScroll = false) {
    const prevIdx = currentIdx;
    currentIdx = Math.max(0, Math.min(episode.sentences.length - 1, nextIdx));
    store.updateEpisodeProgress(episode.id, ((currentIdx + 1) / episode.sentences.length) * 100);

    // 轻量原地切换高亮 class（绝不重建 .subtitle-list）
    const prevCard = root.querySelector(`.sentence-card[data-idx="${prevIdx}"]`);
    if (prevCard && prevIdx !== currentIdx) prevCard.classList.remove('active');
    const nextCard = root.querySelector(`.sentence-card[data-idx="${currentIdx}"]`);
    if (nextCard) nextCard.classList.add('active');

    renderCurrentSentenceAreas();
    scrollActiveCardIntoView(forceScroll);
  }

  function playSentenceAt(idx, resetLoop = true, forceScroll = false) {
    if (idx < 0 || idx >= episode.sentences.length) {
      stopPlayback();
      syncPlayStateUI();
      return;
    }
    isPlaying = true;
    const sent = episode.sentences[idx];
    if (resetLoop) {
      const lc = store.state.loopCount;
      currentLoopRemaining = lc === 0 ? 9999 : lc;
    }

    setActiveIndex(idx, forceScroll);
    syncPlayStateUI();

    if (mediaEl) {
      seekMediaTo(sent.start, true);
      return;
    }

    speechEngine.speak(sent.en, {
      rate: store.state.playbackRate,
      onEnd: () => {
        if (!isPlaying) return;
        currentLoopRemaining -= 1;
        if (currentLoopRemaining > 0) {
          playSentenceAt(currentIdx, false);
          return;
        }
        if (abRange) {
          const nextAb = currentIdx >= abRange.endIdx ? abRange.startIdx : currentIdx + 1;
          playSentenceAt(nextAb, true);
          return;
        }
        if (store.state.autoContinue && mode !== 'shadow' && mode !== 'dictation') {
          if (currentIdx + 1 < episode.sentences.length) {
            playSentenceAt(currentIdx + 1, true);
          } else {
            isPlaying = false;
            syncPlayStateUI();
          }
        } else {
          isPlaying = false;
          syncPlayStateUI();
        }
      }
    });
  }

  function togglePlay() {
    if (isPlaying) {
      stopPlayback();
      syncPlayStateUI();
    } else {
      playSentenceAt(currentIdx, true, false);
    }
  }

  function scrollActiveCardIntoView(force = false) {
    if (!force && Date.now() < userManualScrollUntil) return;
    requestAnimationFrame(() => {
      const list = root.querySelector('.subtitle-list');
      const activeEl = root.querySelector(`.sentence-card[data-idx="${currentIdx}"]`);
      if (!list || !activeEl) return;
      const listRect = list.getBoundingClientRect();
      const cardRect = activeEl.getBoundingClientRect();
      const margin = 48;
      // 只有当当前句真正滚出可视区域时才轻柔定位；用户手动翻页期间绝不抢回
      if (cardRect.top < listRect.top + margin || cardRect.bottom > listRect.bottom - margin) {
        const targetTop = activeEl.offsetTop - list.offsetTop - list.clientHeight * 0.25;
        isProgrammaticScroll = true;
        list.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
        setTimeout(() => { isProgrammaticScroll = false; }, 500);
      }
    });
  }

  // Render interactive English sentence tokens according to mode
  function renderInteractiveSentence(sent, renderMode) {
    let text = sent.en;
    let highlights = sent.highlights || [];

    // 兜底：若某句尚未标注重点词，在「挖空 / 听写词」模式下自动挑 1-2 个实词作为考点，保证每句都能练习
    if ((renderMode === 'cloze' || renderMode === 'dictation') && highlights.length === 0) {
      const words = text.match(/\b[A-Za-z][a-z]{3,}\b/g) || [];
      const skip = new Set(['that', 'this', 'with', 'have', 'from', 'they', 'your', 'just', 'what', 'when', 'here', 'there', 'into', 'very', 'some', 'more', 'guys']);
      const picked = words.filter((w) => !skip.has(w.toLowerCase())).slice(0, 2);
      highlights = picked.map((w) => ({ text: w, key: w.toLowerCase(), chip: 'orange' }));
    }

    if (renderMode === 'cloze' || renderMode === 'dictation' || renderMode === 'dictation-preview') {
      if (highlights.length === 0) return escapeHtml(text);
      let html = escapeHtml(text);
      highlights.forEach((h, hIdx) => {
        const escapedTarget = escapeHtml(h.text);
        const clozeKey = `${sent.id}:${hIdx}`;
        const widthCh = Math.max(5, Math.min(18, h.text.length + 2));
        if (renderMode === 'cloze') {
          const isOpen = revealedCloze.has(clozeKey);
          const replacement = isOpen
            ? `<span class="chip-pill chip-${h.chip || 'orange'}" data-word="${escapeHtml(h.key)}">${escapedTarget}</span>`
            : `<button class="cloze-btn" data-cloze="${clozeKey}" style="width:${widthCh}ch;" title="点击揭示单词" aria-label="点击揭示单词">&nbsp;</button>`;
          html = html.replace(escapedTarget, replacement);
        } else if (renderMode === 'dictation-preview') {
          const replacement = `<span class="dictation-underline" style="width:${widthCh}ch;"></span>`;
          html = html.replace(escapedTarget, replacement);
        } else {
          const val = dictationAnswers[clozeKey] || '';
          const isRevealed = dictationReveal.has(sent.id);
          const isCorrect = val.trim().toLowerCase() === h.text.toLowerCase();
          const cls = val ? (isCorrect ? 'correct' : 'wrong') : '';
          const displayVal = isRevealed ? h.text : val;
          const replacement = `<input class="dictation-input ${isRevealed ? 'correct' : cls}" style="width:${widthCh}ch;" data-dict="${clozeKey}" data-ans="${escapeHtml(h.text)}" value="${escapeHtml(displayVal)}" autocomplete="off" spellcheck="false" />`;
          html = html.replace(escapedTarget, replacement);
        }
      });
      return html;
    }

    // Bilingual / Shadowing: replace highlight phrases first, then clickable words
    let segments = [{ type: 'plain', text }];
    highlights.forEach((h) => {
      const nextSegments = [];
      segments.forEach((seg) => {
        if (seg.type !== 'plain') {
          nextSegments.push(seg);
          return;
        }
        const pos = seg.text.indexOf(h.text);
        if (pos === -1) {
          nextSegments.push(seg);
          return;
        }
        if (pos > 0) nextSegments.push({ type: 'plain', text: seg.text.slice(0, pos) });
        nextSegments.push({ type: 'chip', text: h.text, key: h.key, chip: h.chip || 'orange' });
        if (pos + h.text.length < seg.text.length) {
          nextSegments.push({ type: 'plain', text: seg.text.slice(pos + h.text.length) });
        }
      });
      segments = nextSegments;
    });

    return segments
      .map((seg) => {
        if (seg.type === 'chip') {
          return `<span class="chip-pill chip-${seg.chip}" data-word="${escapeHtml(seg.key)}">${escapeHtml(seg.text)}</span>`;
        }
        return seg.text
          .split(/(\s+)/)
          .map((tok) => {
            if (/^\s+$/.test(tok)) return tok;
            const clean = tok.replace(/[^a-zA-Z'-]/g, '');
            if (clean.length <= 2) return escapeHtml(tok);
            return `<span class="word-token" data-word="${escapeHtml(clean)}">${escapeHtml(tok)}</span>`;
          })
          .join('');
      })
      .join('');
  }

  // ===== Granular DOM updaters (ZERO full-page root.innerHTML rebuilds after mountShell) =====

  function syncPlayStateUI() {
    const stage = document.getElementById('media-stage');
    if (stage) stage.classList.toggle('playing', isPlaying);

    const stagePlayBtn = document.getElementById('stage-play-btn');
    if (stagePlayBtn) {
      stagePlayBtn.textContent = isPlaying ? '⏸' : '▶';
      stagePlayBtn.title = isPlaying ? '暂停' : '播放';
    }

    const ctlPlay = document.getElementById('ctl-play');
    if (ctlPlay) {
      ctlPlay.innerHTML = `<span class="dock-circle">${isPlaying ? '⏸' : '▶'}</span><span>${isPlaying ? '暂停' : '播放'}</span>`;
    }

    const shPlay = document.getElementById('sh-play-video');
    if (shPlay) {
      shPlay.innerHTML = `<span class="shadow-circle-icon">${isPlaying ? '⏸' : '▶'}</span>`;
    }

    const ttMpPlay = document.getElementById('tt-mp-play');
    if (ttMpPlay) {
      ttMpPlay.textContent = isPlaying ? '⏸ 暂停' : '▶ 播放';
    }
  }

  function syncChromeUI() {
    const s = store.state;
    const isLearned = !!s.learnedEpisodes[episode.id];
    const isFav = !!s.favoriteEpisodes[episode.id];

    const topNavSlot = document.getElementById('top-nav-slot');
    if (topNavSlot) {
      topNavSlot.innerHTML = showTopNav
        ? `<div class="practice-mini-header">
             <div style="display:flex;align-items:center;gap:12px;">
               <a href="#/universe" class="brand-lockup" style="gap:8px;">
                 <img src="./assets/icon-192.png" style="width:26px;height:26px;border-radius:50%;" alt="JM" />
                 <strong style="font-family:var(--font-serif);">刚认识不久 Just met</strong>
               </a>
               <span style="color:var(--muted);">/</span>
               <a href="#/library" style="color:var(--accent);font-weight:600;">返回英语自习室</a>
             </div>
             <div style="display:flex;align-items:center;gap:10px;">
               <a href="https://justmet.pages.dev" target="_blank" rel="noopener" class="pill">💌 恋综模拟器 ↗</a>
               <button class="btn btn-outline" id="btn-hide-top" style="padding:4px 12px;font-size:12px;">收起顶栏</button>
             </div>
           </div>`
        : '';
      document.getElementById('btn-hide-top')?.addEventListener('click', () => {
        showTopNav = false;
        syncChromeUI();
      });
    }

    const toggleTopBtn = document.getElementById('toggle-top-nav');
    if (toggleTopBtn) toggleTopBtn.textContent = showTopNav ? '▲ 收起导航' : '▼ 导航 / 返回英语自习室';

    const railLearned = document.getElementById('rail-learned');
    if (railLearned) {
      railLearned.classList.toggle('active', isLearned);
      railLearned.innerHTML = `<span class="rail-icon">${isLearned ? '✓' : '+'}</span><span>${isLearned ? '已学完' : '标记已学'}</span>`;
    }
    const railVocabBadge = document.getElementById('rail-vocab-badge');
    if (railVocabBadge) railVocabBadge.textContent = String(s.vocabBook.length);

    const ttMpSpeed = document.getElementById('tt-mp-speed');
    if (ttMpSpeed) ttMpSpeed.textContent = `${s.playbackRate}x`;
    document.getElementById('tt-mp-shadow')?.classList.toggle('primary', mode === 'shadow');
    document.getElementById('tt-mp-cloze')?.classList.toggle('primary', mode === 'cloze');
    document.getElementById('tt-mp-dict')?.classList.toggle('primary', mode === 'dictation');

    const epLearned = document.getElementById('ep-mark-learned');
    if (epLearned) {
      epLearned.classList.toggle('active', isLearned);
      epLearned.textContent = isLearned ? '✓' : '+';
    }
    const epFav = document.getElementById('ep-fav-btn');
    if (epFav) {
      epFav.classList.toggle('active', isFav);
      epFav.textContent = isFav ? '★' : '☆';
    }

    const stage = document.getElementById('media-stage');
    if (stage) {
      stage.classList.toggle('playing', isPlaying);
      stage.classList.toggle('pip-mode', pipMode);
      stage.classList.toggle('has-video', hasRealMedia && episode.mediaKind !== 'audio' && !s.audioOnly);
      stage.classList.toggle('audio-only', !!s.audioOnly);
      stage.style.background = s.audioOnly ? 'linear-gradient(135deg,#2B1F1B,#4E372F)' : episode.coverGradient;
    }

    const stageScenePill = document.getElementById('stage-scene-pill');
    if (stageScenePill) {
      stageScenePill.textContent = s.audioOnly ? '🎧 纯音频精听模式' : episode.sceneBadge;
    }

    // Mode tabs
    root.querySelectorAll('.mode-tab').forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.mode === mode);
      if (tab.dataset.mode === 'bilingual') {
        tab.textContent = `⇄ ${langDisplay === 'both' ? '双语' : langDisplay === 'en' ? 'EN' : 'ZH'}`;
      }
    });

    // Subtitle panel blind overlay
    const panelBlind = document.getElementById('panel-blind-overlay');
    if (panelBlind) panelBlind.style.display = s.blindListening ? '' : 'none';

    // Dock buttons
    document.getElementById('ctl-pip')?.classList.toggle('active', pipMode);
    document.getElementById('ctl-subpos')?.classList.toggle('active', !!s.inVideoSubtitle);
    document.getElementById('ctl-ab')?.classList.toggle('active', !!abRange);
    document.getElementById('ctl-blind')?.classList.toggle('active', !!s.blindListening);
    document.getElementById('ctl-ipa')?.classList.toggle('active', !!s.showIpa);
    document.getElementById('ctl-screenvocab')?.classList.toggle('active', !!s.screenVocab);

    const ctlSpeed = document.getElementById('ctl-speed');
    if (ctlSpeed) ctlSpeed.innerHTML = `<span class="dock-circle">${s.playbackRate}x</span><span>倍速</span>`;
    const speedLabel = document.getElementById('scrubber-speed');
    if (speedLabel) speedLabel.textContent = `${s.playbackRate.toFixed(1)}x`;

    const ctlLoop = document.getElementById('ctl-loop');
    if (ctlLoop) {
      ctlLoop.classList.toggle('active', s.loopCount !== 1 || !!s.audioOnly);
      ctlLoop.innerHTML = `<span class="dock-circle">${s.loopCount === 0 ? '∞' : s.loopCount + 'x'}</span><span>循环</span>`;
    }

    const ctlAuto = document.getElementById('ctl-autocont');
    if (ctlAuto) {
      ctlAuto.classList.toggle('active', !!s.autoContinue);
      ctlAuto.innerHTML = `<span class="dock-circle">${s.autoContinue ? '▶' : '⏸'}</span><span>${s.autoContinue ? '连播' : '句停'}</span>`;
    }

    syncAudioRate();
    syncPlayStateUI();
  }

  function renderCurrentSentenceAreas() {
    const s = store.state;
    const curSent = episode.sentences[currentIdx];
    if (!curSent) return;

    const metaPill = document.getElementById('stage-meta-pill');
    if (metaPill) metaPill.textContent = `${curSent.speaker} · #${curSent.id}/${episode.sentences.length}`;

    const vocabSlot = document.getElementById('stage-vocab-slot');
    if (vocabSlot) {
      vocabSlot.innerHTML =
        s.screenVocab && (curSent.highlights || []).length > 0
          ? `<div class="stage-vocab-float">
               ${curSent.highlights.map((h) => `<span class="stage-vocab-tag" data-word="${escapeHtml(h.key)}">✨ ${escapeHtml(h.text)}</span>`).join('')}
             </div>`
          : '';
    }

    const overlaySlot = document.getElementById('stage-overlay-sub-slot');
    if (overlaySlot) {
      overlaySlot.innerHTML =
        s.inVideoSubtitle && !s.blindListening
          ? `<div class="video-overlay-sub">
               ${langDisplay !== 'zh' ? `<div class="en">${escapeHtml(curSent.en)}</div>` : ''}
               ${langDisplay !== 'en' ? `<div class="zh">${escapeHtml(curSent.zh)}</div>` : ''}
             </div>`
          : '';
    }

    const curCardSlot = document.getElementById('current-sentence-slot');
    if (curCardSlot) {
      curCardSlot.innerHTML =
        !s.inVideoSubtitle && mode !== 'shadow'
          ? `<div class="current-sentence-card">
               ${s.blindListening ? `<div class="blind-overlay"><span class="blind-pill">🙈 盲听中 · 点击底部盲听按钮揭示</span></div>` : ''}
               <div>
                 ${s.showIpa && mode === 'bilingual' && langDisplay !== 'zh' ? `<div class="sentence-ipa">${escapeHtml(curSent.ipa)}</div>` : ''}
                 ${
                   !(mode === 'bilingual' && langDisplay === 'zh')
                     ? `<div class="sentence-en" style="font-size:${s.fontSize + 2}px;">
                          ${renderInteractiveSentence(curSent, mode === 'cloze' ? 'cloze' : mode === 'dictation' ? 'dictation-preview' : 'bilingual')}
                        </div>`
                     : ''
                 }
                 ${
                   mode === 'bilingual' && langDisplay !== 'en'
                     ? `<div class="sentence-zh" style="font-size:${langDisplay === 'zh' ? s.fontSize + 1 : Math.max(13, s.fontSize - 2)}px;color:${langDisplay === 'zh' ? 'var(--text)' : 'var(--muted)'};font-weight:${langDisplay === 'zh' ? '600' : '400'};margin-top:${langDisplay === 'zh' ? '0' : '10px'};">${escapeHtml(curSent.zh || '（本句暂无中文翻译）')}</div>`
                     : ''
                 }
               </div>
               <div class="current-sentence-footer">
                 <span class="pill">当前句</span>
                 <span>#${curSent.id}</span>
                 <span>${formatTime(curSent.start)} - ${formatTime(curSent.end)}</span>
                 ${abRange ? `<span class="pill">AB 复读: #${abRange.startIdx + 1}–#${abRange.endIdx + 1}</span>` : ''}
               </div>
             </div>`
          : '';
    }

    const scrubber = document.getElementById('dock-scrubber');
    if (scrubber) scrubber.value = String(currentIdx);
    const scrubberTime = document.getElementById('scrubber-time');
    if (scrubberTime) scrubberTime.textContent = `${formatTime(curSent.start)} / ${episode.durationLabel}`;

    if (mode === 'shadow') {
      renderShadowFocus();
    }
  }

  function renderShadowFocus() {
    const body = document.getElementById('subtitle-panel-body');
    if (!body) return;
    const s = store.state;
    const curSent = episode.sentences[currentIdx];
    const curRecKey = `${episode.id}:${curSent.id}`;
    const hasCurRec = !!speechEngine.recordings[curRecKey];
    const curEval = s.evalScores[curRecKey];

    body.innerHTML = `
      <div class="shadow-focus-box">
        <div class="shadow-card">
          <div style="width:100%;">
            ${s.showIpa ? `<div class="sentence-ipa">${escapeHtml(curSent.ipa)}</div>` : ''}
            <div class="sentence-en" style="font-size:${s.fontSize + 4}px;line-height:1.55;">
              ${renderInteractiveSentence(curSent, 'bilingual')}
            </div>
            <div class="sentence-zh" style="margin-top:10px;font-size:${Math.max(14, s.fontSize - 2)}px;">${escapeHtml(curSent.zh)}</div>
          </div>

          <div class="shadow-controls">
            <button class="shadow-circle-btn" id="sh-prev" title="上一句"><span class="shadow-circle-icon">‹</span></button>
            <button class="shadow-circle-btn soft-fill" id="sh-play-video" title="播放视频片段"><span class="shadow-circle-icon">${isPlaying ? '⏸' : '▶'}</span></button>
            <button class="shadow-circle-btn highlight" id="sh-play-orig" title="播放原音"><span class="shadow-circle-icon">♪</span></button>
            <button class="shadow-circle-btn ${recordingSentenceId === curSent.id ? 'recording' : ''}" id="sh-record" title="${recordingSentenceId === curSent.id ? '停止录音' : '开始录音'}">
              <span class="shadow-circle-icon">${recordingSentenceId === curSent.id ? '⏹' : '🎤'}</span>
            </button>
            <button class="shadow-circle-btn" id="sh-play-rec" title="播放我的录音" ${hasCurRec ? '' : 'style="opacity:0.42;"'}><span class="shadow-circle-icon">🎧</span></button>
            <button class="shadow-circle-btn" id="sh-next" title="下一句"><span class="shadow-circle-icon">›</span></button>
          </div>

          <button class="sent-act-btn" id="sh-eval" title="AI 发音评测" style="width:42px;height:42px;font-size:20px;border:1px solid var(--border);background:var(--card);">
            🤖<span class="score-mini-badge">${curEval ? curEval.overall : 0}</span>
          </button>

          <span class="pill" style="background:var(--card);border:1px solid var(--border);color:var(--muted);font-weight:500;">
            #${curSent.id} · ${formatTime(curSent.start)} - ${formatTime(curSent.end)} · ${(curSent.end - curSent.start).toFixed(1)}s
          </span>
        </div>
      </div>
    `;

    document.getElementById('sh-prev')?.addEventListener('click', () => setActiveIndex(Math.max(0, currentIdx - 1), true));
    document.getElementById('sh-next')?.addEventListener('click', () => setActiveIndex(Math.min(episode.sentences.length - 1, currentIdx + 1), true));
    document.getElementById('sh-play-video')?.addEventListener('click', () => togglePlay());
    document.getElementById('sh-play-orig')?.addEventListener('click', () => playSentenceAt(currentIdx, true, false));
    document.getElementById('sh-record')?.addEventListener('click', () => handleRecordToggle(currentIdx));
    document.getElementById('sh-play-rec')?.addEventListener('click', () => {
      const ok = speechEngine.playRecording(`${episode.id}:${episode.sentences[currentIdx].id}`);
      if (!ok) showToast('请先点击「开始录音」录制你的跟读音频');
    });
    document.getElementById('sh-eval')?.addEventListener('click', () => openEvalDrawer(episode, episode.sentences[currentIdx], handleRecordToggle));
  }

  function renderSubtitleList(forceRebuild = false) {
    const body = document.getElementById('subtitle-panel-body');
    if (!body) return;
    if (mode === 'shadow') {
      lastListSignature = 'shadow';
      renderShadowFocus();
      return;
    }

    const s = store.state;
    const sig = `${mode}|${langDisplay}|${s.fontSize}|${s.showIpa}|${recordingSentenceId}|${revealedCloze.size}|${dictationReveal.size}`;
    if (!forceRebuild && sig === lastListSignature && body.querySelector('.subtitle-list')) {
      return;
    }
    lastListSignature = sig;

    const prevScrollTop = body.querySelector('.subtitle-list')?.scrollTop || 0;

    body.innerHTML = `
      <div class="subtitle-list" id="subtitle-list">
        ${episode.sentences
          .map((sent, idx) => {
            const recKey = `${episode.id}:${sent.id}`;
            const isStarred = !!s.starredSentences[recKey];
            const hasRec = !!speechEngine.recordings[recKey];
            const evalRes = s.evalScores[recKey];
            const isRecThis = recordingSentenceId === sent.id;
            return `
              <article class="sentence-card ${idx === currentIdx ? 'active' : ''}" data-idx="${idx}">
                ${s.showIpa && !(mode === 'bilingual' && langDisplay === 'zh') ? `<div class="sentence-ipa">${escapeHtml(sent.ipa)}</div>` : ''}
                ${
                  !(mode === 'bilingual' && langDisplay === 'zh')
                    ? `<div class="sentence-en" style="font-size:${s.fontSize}px;">
                         ${renderInteractiveSentence(sent, mode)}
                       </div>`
                    : ''
                }
                ${
                  mode === 'bilingual' && langDisplay !== 'en'
                    ? `<div class="sentence-zh" style="${langDisplay === 'zh' ? `font-size:${s.fontSize}px;color:var(--text);font-weight:600;` : ''}">${escapeHtml(sent.zh || (langDisplay === 'zh' ? '（本句暂无中文翻译）' : ''))}</div>`
                    : ''
                }
                <div class="sentence-card-footer">
                  <span>#${sent.id} &nbsp; ${formatTime(sent.start)} - ${formatTime(sent.end)}</span>
                  <div class="sentence-actions">
                    ${
                      mode === 'dictation'
                        ? `<button class="sent-act-btn reveal-dict-btn ${dictationReveal.has(sent.id) ? 'active' : ''}" data-sent-id="${sent.id}" title="${dictationReveal.has(sent.id) ? '隐藏答案' : '查看答案'}">👁</button>`
                        : ''
                    }
                    <button class="sent-act-btn ${isStarred ? 'active' : ''}" data-act="star" data-idx="${idx}" title="收藏字幕">${isStarred ? '★' : '☆'}</button>
                    <button class="sent-act-btn" data-act="copy" data-idx="${idx}" title="复制字幕">📋</button>
                    <button class="sent-act-btn" data-act="play" data-idx="${idx}" title="播放原音">♪</button>
                    <button class="sent-act-btn ${isRecThis ? 'recording' : ''}" data-act="record" data-idx="${idx}" title="${isRecThis ? '停止录音' : '开始录音'}">🎤</button>
                    <button class="sent-act-btn" data-act="playrec" data-idx="${idx}" title="播放我的录音" ${hasRec ? '' : 'style="opacity:0.35;"'}>🎧</button>
                    <button class="sent-act-btn" data-act="eval" data-idx="${idx}" title="发音评测">
                      🤖<span class="score-mini-badge">${evalRes ? evalRes.overall : 0}</span>
                    </button>
                  </div>
                </div>
              </article>
            `;
          })
          .join('')}
      </div>
    `;

    const listEl = document.getElementById('subtitle-list');
    if (listEl) {
      listEl.scrollTop = prevScrollTop;
      const pauseAutoFollow = () => {
        userManualScrollUntil = Date.now() + 6000;
      };
      listEl.addEventListener('wheel', pauseAutoFollow, { passive: true });
      listEl.addEventListener('touchstart', pauseAutoFollow, { passive: true });
      listEl.addEventListener('pointerdown', pauseAutoFollow, { passive: true });
      listEl.addEventListener('scroll', () => {
        if (!isProgrammaticScroll) {
          userManualScrollUntil = Date.now() + 6000;
        }
      }, { passive: true });

      // 听写词输入框事件
      listEl.querySelectorAll('.dictation-input').forEach((inp) => {
        inp.addEventListener('click', (e) => e.stopPropagation());
        inp.addEventListener('focus', () => {
          const shell = root.querySelector('.practice-shell');
          if (window.innerWidth <= 768 && shell) shell.classList.add('keyboard-open');
          setTimeout(() => inp.scrollIntoView({ behavior: 'smooth', block: 'center' }), 220);
        });
        inp.addEventListener('blur', () => {
          setTimeout(() => {
            const active = document.activeElement;
            if (!active || !active.classList.contains('dictation-input')) {
              root.querySelector('.practice-shell')?.classList.remove('keyboard-open');
            }
          }, 120);
        });
        inp.addEventListener('input', (e) => {
          dictationAnswers[inp.dataset.dict] = e.target.value;
          const match = e.target.value.trim().toLowerCase() === inp.dataset.ans.toLowerCase();
          inp.classList.toggle('correct', match);
          inp.classList.toggle('wrong', e.target.value.length > 0 && !match);

          if (match) {
            const allInputs = Array.from(listEl.querySelectorAll('.dictation-input'));
            const pos = allInputs.indexOf(inp);
            const nextInp = pos >= 0 ? allInputs[pos + 1] : null;
            if (nextInp) {
              const curCard = inp.closest('.sentence-card');
              const nextCard = nextInp.closest('.sentence-card');
              if (nextCard && curCard && nextCard !== curCard) {
                const nextIdx = Number(nextCard.dataset.idx);
                if (!Number.isNaN(nextIdx)) {
                  playSentenceAt(nextIdx, true, false);
                }
              }
              nextInp.focus();
              nextInp.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }
        });
      });
    }
  }

  function refreshUI(rebuildList = false) {
    syncChromeUI();
    renderCurrentSentenceAreas();
    if (rebuildList || mode === 'shadow') {
      renderSubtitleList(true);
    }
  }

  function handleRecordToggle(idx) {
    const sent = episode.sentences[idx];
    const recKey = `${episode.id}:${sent.id}`;
    if (recordingSentenceId === sent.id) {
      speechEngine.stopRecording();
      recordingSentenceId = null;
      refreshUI(true);
      return;
    }
    stopPlayback();
    recordingSentenceId = sent.id;
    refreshUI(true);
    showToast('开始录音，请跟读当前英文句子...');
    speechEngine.startRecording(
      recKey,
      sent.en,
      (rec) => {
        recordingSentenceId = null;
        store.saveEvalScore(episode.id, sent.id, rec.evalResult);
        showToast(`录音完成！AI 发音综合得分：${rec.evalResult.overall} 分`);
        refreshUI(true);
      },
      () => {
        recordingSentenceId = null;
        const fallbackEval = speechEngine.evaluatePronunciation(sent.en, '');
        store.saveEvalScore(episode.id, sent.id, fallbackEval);
        showToast('未检测到麦克风权限，已生成示例发音评测供预览');
        refreshUI(true);
      }
    );
  }

  function mountShell() {
    const s = store.state;
    const curSent = episode.sentences[currentIdx];

    root.innerHTML = `
      <div class="practice-shell">
        <div id="top-nav-slot"></div>

        <!-- 移动端顶部精简栏（对照 04_screen_practice.png） -->
        <div class="tt-mobile-practice-head">
          <button class="tt-mp-back" id="tt-mp-back" title="返回课程列表">‹</button>
          <div class="tt-mp-title">${escapeHtml(episode.speaker)}</div>
          <div class="tt-mp-right">
            <span class="tt-mp-dur">${episode.durationLabel}</span>
            <button class="tt-mp-more-icon" id="tt-mp-more-top" title="全部学习工具">⋯</button>
          </div>
        </div>

        <div class="practice-top-collapse">
          <button class="collapse-nav-btn" id="toggle-top-nav" title="展开/收起顶部导航">
            ▼ 导航 / 返回英语自习室
          </button>
        </div>

        <div class="practice-body">
          <!-- 左侧学习工具栏 -->
          <aside class="tool-rail">
            <button class="rail-btn" id="rail-keywords">
              <span class="rail-badge">${allEpisodeKeywords.length}</span>
              <span class="rail-icon">🔖</span>
              <span>重点词</span>
            </button>
            <button class="rail-btn" id="rail-learned">
              <span class="rail-icon">+</span>
              <span>标记已学</span>
            </button>
            <button class="rail-btn" id="rail-vocab">
              <span class="rail-badge" id="rail-vocab-badge">${s.vocabBook.length}</span>
              <span class="rail-icon">📒</span>
              <span>生词本</span>
            </button>
            <button class="rail-btn" id="rail-catalog">
              <span class="rail-icon">☰</span>
              <span>目录</span>
            </button>
          </aside>

          <!-- 中左媒体区 + 当前句卡片 -->
          <section class="media-column">
            <div class="ep-title-bar">
              <span class="ep-pill-tag">${episode.number}</span>
              <h1 class="ep-title-text" title="${escapeHtml(episode.title)}">${escapeHtml(episode.title)}</h1>
              <button class="icon-circle-sm" id="ep-mark-learned" title="标记已学">+</button>
              <button class="icon-circle-sm" id="ep-fav-btn" title="收藏剧集">☆</button>
            </div>

            <div class="media-stage" id="media-stage" style="background:${episode.coverGradient};">
              ${hasRealMedia ? `<div class="media-mount-slot" id="media-mount"></div>` : ''}
              <div class="media-stage-header">
                <span class="stage-pill" id="stage-scene-pill">${episode.sceneBadge}</span>
                <span class="stage-pill" id="stage-meta-pill">${curSent.speaker} · #${curSent.id}/${episode.sentences.length}</span>
              </div>

              <div class="stage-center">
                <button class="stage-play-btn" id="stage-play-btn" title="播放">▶</button>
                <div class="waveform-bars">
                  <span></span><span></span><span></span><span></span><span></span><span></span>
                </div>
              </div>

              <div id="stage-vocab-slot"></div>
              <div id="stage-overlay-sub-slot"></div>
            </div>

            <div id="current-sentence-slot"></div>
          </section>

          <!-- 右侧动态字幕面板 -->
          <section class="subtitle-panel">
            <div class="subtitle-panel-header">
              <span class="panel-heading">动态字幕</span>
              <div class="mode-tabs">
                <button class="mode-tab active" data-mode="bilingual" title="再次点击切换：双语 / EN / ZH">⇄ 双语</button>
                <button class="mode-tab" data-mode="shadow">跟读</button>
                <button class="mode-tab" data-mode="cloze">挖空</button>
                <button class="mode-tab" data-mode="dictation">听写词</button>
              </div>
            </div>

            <div class="blind-overlay" id="panel-blind-overlay" style="display:none;"><span class="blind-pill">🙈 盲听中</span></div>
            <div id="subtitle-panel-body" style="display:flex;flex-direction:column;flex:1;min-height:0;"></div>
          </section>
        </div>

        <!-- 底部全宽 17 项播放控制栏 -->
        <footer class="player-dock">
          <div class="scrubber-row">
            <span id="scrubber-time">${formatTime(curSent.start)} / ${episode.durationLabel}</span>
            <input class="scrubber-range" id="dock-scrubber" type="range" min="0" max="${episode.sentences.length - 1}" value="${currentIdx}" />
            <span id="scrubber-speed">${s.playbackRate.toFixed(1)}x</span>
          </div>

          <div class="dock-controls">
            <div class="dock-group">
              <button class="dock-btn" id="ctl-pip"><span class="dock-circle">❐</span><span>小窗</span></button>
              <button class="dock-btn" id="ctl-full"><span class="dock-circle">⛶</span><span>全屏</span></button>
              <button class="dock-btn" id="ctl-subpos"><span class="dock-circle">▤</span><span>字幕</span></button>
              <button class="dock-btn" id="ctl-ab"><span class="dock-circle">AB</span><span>复读</span></button>
              <button class="dock-btn" id="ctl-speed"><span class="dock-circle">${s.playbackRate}x</span><span>倍速</span></button>
              <button class="dock-btn" id="ctl-blind"><span class="dock-circle">👁</span><span>盲听</span></button>
              <button class="dock-btn" id="ctl-loop"><span class="dock-circle">1x</span><span>循环</span></button>
            </div>

            <div class="dock-group">
              <button class="dock-btn" id="ctl-prev"><span class="dock-circle">←</span><span>上句</span></button>
              <button class="dock-btn play-main" id="ctl-play"><span class="dock-circle">▶</span><span>播放</span></button>
              <button class="dock-btn" id="ctl-next"><span class="dock-circle">→</span><span>下句</span></button>
            </div>

            <div class="dock-group">
              <button class="dock-btn" id="ctl-ipa"><span class="dock-circle">音</span><span>音标</span></button>
              <button class="dock-btn" id="ctl-autocont"><span class="dock-circle">▶</span><span>连播</span></button>
              <button class="dock-btn" id="ctl-screenvocab"><span class="dock-circle">词</span><span>屏词</span></button>
              <button class="dock-btn" id="ctl-font"><span class="dock-circle">T+</span><span>字号</span></button>
              <button class="dock-btn" id="ctl-cache"><span class="dock-circle">↓</span><span>缓存</span></button>
              <button class="dock-btn" id="ctl-theme"><span class="dock-circle">🎨</span><span>主题</span></button>
              <button class="dock-btn" id="ctl-pdf"><span class="dock-circle">🖨</span><span>PDF</span></button>
            </div>
          </div>
        </footer>

        <!-- 移动端底部精简主控条（对照 04_screen_practice.png：播放 / 倍速 / 跟读 / 挖空 / 听写 + 更多全功能面板） -->
        <div class="tt-mobile-practice-bar" id="tt-mobile-practice-bar">
          <button class="tt-mp-pill primary" id="tt-mp-play">▶ 播放</button>
          <button class="tt-mp-pill" id="tt-mp-speed">${s.playbackRate}x</button>
          <button class="tt-mp-pill" id="tt-mp-shadow">跟读</button>
          <button class="tt-mp-pill" id="tt-mp-cloze">挖空</button>
          <button class="tt-mp-pill" id="tt-mp-dict">听写</button>
          <button class="tt-mp-pill more" id="tt-mp-more">更多</button>
        </div>
      </div>
    `;

    // Mount persistent video/audio nodes ONCE — they stay attached for the entire episode lifetime
    if (mediaEl) {
      const mount = document.getElementById('media-mount');
      if (mount) {
        mount.appendChild(mediaEl);
        if (companionAudioEl) mount.appendChild(companionAudioEl);
      }
    }

    bindShellEvents();
    refreshUI(true);
  }

  function bindShellEvents() {
    document.getElementById('toggle-top-nav')?.addEventListener('click', () => {
      showTopNav = !showTopNav;
      syncChromeUI();
    });

    // Left rail
    document.getElementById('rail-keywords')?.addEventListener('click', () => openKeywordsModal(allEpisodeKeywords, episode, episode.sentences[currentIdx]));
    const toggleLearned = () => {
      const done = store.toggleLearnedEpisode(episode.id);
      showToast(done ? '已标记本集为已学完 🎉' : '已取消已学标记');
      syncChromeUI();
    };
    document.getElementById('rail-learned')?.addEventListener('click', toggleLearned);
    document.getElementById('ep-mark-learned')?.addEventListener('click', toggleLearned);
    document.getElementById('ep-fav-btn')?.addEventListener('click', () => {
      const f = store.toggleFavoriteEpisode(episode.id);
      showToast(f ? '已收藏本集' : '已取消收藏');
      syncChromeUI();
    });
    document.getElementById('rail-vocab')?.addEventListener('click', () => openVocabModal(() => syncChromeUI()));
    document.getElementById('rail-catalog')?.addEventListener('click', () => openCatalogDrawer(library, episode.id, (nextEpId) => {
      stopPlayback();
      navigate(`#/episode/${nextEpId}`);
    }));

    // Play controls
    document.getElementById('stage-play-btn')?.addEventListener('click', togglePlay);
    document.getElementById('ctl-play')?.addEventListener('click', togglePlay);
    document.getElementById('tt-mp-back')?.addEventListener('click', () => {
      stopPlayback();
      navigate('#/library');
    });
    document.getElementById('tt-mp-play')?.addEventListener('click', togglePlay);
    document.getElementById('tt-mp-speed')?.addEventListener('click', () => document.getElementById('ctl-speed')?.click());
    document.getElementById('tt-mp-shadow')?.addEventListener('click', () => {
      root.querySelector('.mode-tab[data-mode="shadow"]')?.click();
    });
    document.getElementById('tt-mp-cloze')?.addEventListener('click', () => {
      root.querySelector('.mode-tab[data-mode="cloze"]')?.click();
    });
    document.getElementById('tt-mp-dict')?.addEventListener('click', () => {
      root.querySelector('.mode-tab[data-mode="dictation"]')?.click();
    });

    const openMobileMoreSheet = () => {
      const st = store.state;
      const modalRoot = document.getElementById('modal-root');
      if (!modalRoot) return;
      const langLabel = langDisplay === 'both' ? '双语' : langDisplay === 'en' ? '仅 EN' : '仅 ZH';
      modalRoot.innerHTML = `
        <div class="modal-backdrop" id="tt-more-bg">
          <div class="modal-card tt-more-sheet">
            <div class="modal-header">
              <h3>全部学习工具</h3>
              <button class="icon-circle-sm" id="tt-more-close">✕</button>
            </div>
            <div class="modal-body">
              <div class="tt-more-grid">
                <button class="tt-more-item" data-trig="bilingual"><span>⇄</span><strong>${langLabel}切换</strong></button>
                <button class="tt-more-item" data-trig="ctl-speed"><span>⚡</span><strong>倍速 (${st.playbackRate}x)</strong></button>
                <button class="tt-more-item" data-trig="ctl-loop"><span>🔁</span><strong>循环 (${st.loopCount === 0 ? '∞' : st.loopCount + 'x'})</strong></button>
                <button class="tt-more-item ${st.audioOnly ? 'active' : ''}" data-trig="audioOnly"><span>🎧</span><strong>纯音频</strong></button>
                <button class="tt-more-item ${st.blindListening ? 'active' : ''}" data-trig="ctl-blind"><span>👁</span><strong>盲听遮罩</strong></button>
                <button class="tt-more-item ${st.showIpa ? 'active' : ''}" data-trig="ctl-ipa"><span>🔤</span><strong>整句 IPA</strong></button>
                <button class="tt-more-item ${st.autoContinue ? 'active' : ''}" data-trig="ctl-autocont"><span>▶</span><strong>${st.autoContinue ? '连播开' : '句停开'}</strong></button>
                <button class="tt-more-item ${st.inVideoSubtitle ? 'active' : ''}" data-trig="ctl-subpos"><span>▤</span><strong>字幕位置</strong></button>
                <button class="tt-more-item" data-trig="ctl-ab"><span>AB</span><strong>AB 复读</strong></button>
                <button class="tt-more-item ${st.screenVocab ? 'active' : ''}" data-trig="ctl-screenvocab"><span>词</span><strong>屏词</strong></button>
                <button class="tt-more-item" data-trig="ctl-pip"><span>❐</span><strong>小窗</strong></button>
                <button class="tt-more-item" data-trig="ctl-full"><span>⛶</span><strong>全屏</strong></button>
                <button class="tt-more-item" data-trig="ctl-font"><span>T+</span><strong>字号</strong></button>
                <button class="tt-more-item" data-trig="ctl-theme"><span>🎨</span><strong>护眼主题</strong></button>
                <button class="tt-more-item" data-trig="ctl-pdf"><span>🖨</span><strong>PDF 讲义</strong></button>
                <button class="tt-more-item" data-trig="rail-keywords"><span>🔖</span><strong>重点词 (${allEpisodeKeywords.length})</strong></button>
                <button class="tt-more-item" data-trig="rail-vocab"><span>📒</span><strong>生词本 (${st.vocabBook.length})</strong></button>
                <button class="tt-more-item" data-trig="rail-catalog"><span>☰</span><strong>剧集目录</strong></button>
                <button class="tt-more-item" data-trig="rail-learned"><span>✓</span><strong>标记已学</strong></button>
              </div>
            </div>
          </div>
        </div>
      `;
      const closeMore = () => { modalRoot.innerHTML = ''; };
      document.getElementById('tt-more-close')?.addEventListener('click', closeMore);
      document.getElementById('tt-more-bg')?.addEventListener('click', (e) => { if (e.target.id === 'tt-more-bg') closeMore(); });
      modalRoot.querySelectorAll('[data-trig]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const trig = btn.dataset.trig;
          closeMore();
          if (trig === 'bilingual') {
            root.querySelector('.mode-tab[data-mode="bilingual"]')?.click();
          } else if (trig === 'audioOnly') {
            store.set({ audioOnly: !store.state.audioOnly });
            handleAudioOnlyModeChange();
            refreshUI(false);
            showToast(store.state.audioOnly ? '已开启纯音频模式 🎧' : '已切回视频画面');
          } else {
            document.getElementById(trig)?.click();
          }
        });
      });
    };

    document.getElementById('tt-mp-more')?.addEventListener('click', openMobileMoreSheet);
    document.getElementById('tt-mp-more-top')?.addEventListener('click', openMobileMoreSheet);
    document.getElementById('ctl-prev')?.addEventListener('click', () => playSentenceAt(Math.max(0, currentIdx - 1), true, true));
    document.getElementById('ctl-next')?.addEventListener('click', () => playSentenceAt(Math.min(episode.sentences.length - 1, currentIdx + 1), true, true));
    document.getElementById('dock-scrubber')?.addEventListener('input', (e) => {
      const idx = Number(e.target.value);
      if (isPlaying) playSentenceAt(idx, true, true);
      else setActiveIndex(idx, true);
    });

    // Mode tabs
    root.querySelectorAll('.mode-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        const nextMode = tab.dataset.mode;
        if (nextMode === 'bilingual' && mode === 'bilingual') {
          langDisplay = langDisplay === 'both' ? 'en' : langDisplay === 'en' ? 'zh' : 'both';
          refreshUI(true);
          return;
        }
        const isPauseMode = (m) => m === 'shadow' || m === 'dictation';
        if (isPauseMode(nextMode) && !isPauseMode(mode)) {
          savedAutoContinue = store.state.autoContinue;
          store.set({ autoContinue: false });
        } else if (!isPauseMode(nextMode) && isPauseMode(mode)) {
          store.set({ autoContinue: savedAutoContinue });
        }
        mode = nextMode;
        refreshUI(true);
      });
    });

    // Event delegation on .practice-shell (NOT persistent root) so leaving an episode automatically detaches it
    const shellEl = root.querySelector('.practice-shell');
    shellEl?.addEventListener('click', (e) => {
      if (isDisposed) return;
      const wordEl = e.target.closest('[data-word]');
      if (wordEl) {
        e.stopPropagation();
        const card = wordEl.closest('.sentence-card');
        const idx = card ? Number(card.dataset.idx) : currentIdx;
        const ctxSent = episode.sentences[Number.isNaN(idx) ? currentIdx : idx] || episode.sentences[currentIdx];
        openWordDictionaryModal(wordEl.dataset.word, episode, () => syncChromeUI(), ctxSent);
        return;
      }

      const clozeBtn = e.target.closest('.cloze-btn');
      if (clozeBtn) {
        e.stopPropagation();
        revealedCloze.add(clozeBtn.dataset.cloze);
        refreshUI(true);
        return;
      }

      const revealBtn = e.target.closest('.reveal-dict-btn');
      if (revealBtn) {
        e.stopPropagation();
        const sid = Number(revealBtn.dataset.sentId);
        if (dictationReveal.has(sid)) dictationReveal.delete(sid);
        else dictationReveal.add(sid);
        refreshUI(true);
        return;
      }

      const actBtn = e.target.closest('.sent-act-btn[data-act]');
      if (actBtn) {
        e.stopPropagation();
        const idx = Number(actBtn.dataset.idx);
        const sent = episode.sentences[idx];
        const act = actBtn.dataset.act;
        if (!sent) return;
        if (act === 'star') {
          const starred = store.toggleStarSentence(episode.id, sent.id);
          showToast(starred ? '已收藏该句字幕' : '已取消收藏');
          refreshUI(true);
        } else if (act === 'copy') {
          navigator.clipboard?.writeText(`${sent.en}\n${sent.zh}`).catch(() => {});
          showToast('已复制双语字幕');
        } else if (act === 'play') {
          playSentenceAt(idx, true, false);
        } else if (act === 'record') {
          handleRecordToggle(idx);
        } else if (act === 'playrec') {
          const ok = speechEngine.playRecording(`${episode.id}:${sent.id}`);
          if (!ok) showToast('请先录制该句的跟读音频');
        } else if (act === 'eval') {
          openEvalDrawer(episode, sent, () => handleRecordToggle(idx));
        }
        return;
      }

      const card = e.target.closest('.sentence-card');
      if (card && !e.target.closest('button, input, [data-word]')) {
        const idx = Number(card.dataset.idx);
        if (!Number.isNaN(idx)) playSentenceAt(idx, true, false);
      }
    });

    // Bottom 17 dock controls
    document.getElementById('ctl-pip')?.addEventListener('click', () => {
      pipMode = !pipMode;
      syncChromeUI();
    });
    document.getElementById('ctl-full')?.addEventListener('click', () => {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
      else document.exitFullscreen?.().catch(() => {});
    });
    document.getElementById('ctl-subpos')?.addEventListener('click', () => {
      store.set({ inVideoSubtitle: !store.state.inVideoSubtitle });
      showToast(store.state.inVideoSubtitle ? '已切换为画面内字幕' : '已切换为画面下方字幕');
      refreshUI(false);
    });
    document.getElementById('ctl-ab')?.addEventListener('click', () => openABLoopModal(episode, abRange, (nextRange) => {
      abRange = nextRange;
      if (abRange) playSentenceAt(abRange.startIdx, true, true);
      else refreshUI(false);
    }));
    document.getElementById('ctl-speed')?.addEventListener('click', () => openSpeedModal(() => syncChromeUI()));
    document.getElementById('ctl-blind')?.addEventListener('click', () => {
      store.set({ blindListening: !store.state.blindListening });
      showToast(store.state.blindListening ? '已开启盲听模式' : '已关闭盲听模式');
      refreshUI(false);
    });
    document.getElementById('ctl-loop')?.addEventListener('click', () => openLoopModal(() => {
      handleAudioOnlyModeChange();
      syncChromeUI();
    }));
    document.getElementById('ctl-ipa')?.addEventListener('click', () => {
      store.set({ showIpa: !store.state.showIpa });
      refreshUI(true);
    });
    document.getElementById('ctl-autocont')?.addEventListener('click', () => {
      store.set({ autoContinue: !store.state.autoContinue });
      showToast(store.state.autoContinue ? '已切换为自动连播' : '已切换为逐句暂停（句停）');
      syncChromeUI();
    });
    document.getElementById('ctl-screenvocab')?.addEventListener('click', () => {
      store.set({ screenVocab: !store.state.screenVocab });
      refreshUI(false);
    });
    document.getElementById('ctl-font')?.addEventListener('click', () => openFontModal(() => refreshUI(true)));
    document.getElementById('ctl-cache')?.addEventListener('click', () => showToast('当前学习进度与生词笔记已保存在本地浏览器（音视频按需流式播放）'));
    document.getElementById('ctl-theme')?.addEventListener('click', () => openThemeModal(() => syncChromeUI()));
    document.getElementById('ctl-pdf')?.addEventListener('click', () => openPdfPreviewModal(episode));
  }

  const syncVisualViewport = () => {
    if (window.visualViewport) {
      document.documentElement.style.setProperty('--vvh', `${window.visualViewport.height}px`);
    }
  };
  syncVisualViewport();
  window.visualViewport?.addEventListener('resize', syncVisualViewport);

  mountShell();
  prefetchEpisodeKeywords(episode, () => isDisposed);

  return () => {
    isDisposed = true;
    stopPlayback();
    if (precisionTimer) clearInterval(precisionTimer);
    if (mediaEl) {
      mediaEl.pause();
      mediaEl.removeAttribute('src');
      mediaEl.load();
    }
    if (companionAudioEl) {
      companionAudioEl.pause();
      companionAudioEl.removeAttribute('src');
      companionAudioEl.load();
    }
    speechEngine.stopRecording();
    window.visualViewport?.removeEventListener('resize', syncVisualViewport);
    document.documentElement.style.removeProperty('--vvh');
  };
}

// ===== Modals & Drawers for Practice Workspace =====

function closeModal() {
  document.getElementById('modal-root').innerHTML = '';
}

const clientDictCache = {};
const inflightDictRequests = new Map();
let activeDictModalToken = 0;

async function fetchDefineWithTimeout(cleanWord, contextEn = '', timeoutMs = 8500) {
  const cacheKey = cleanWord.toLowerCase();
  const cached = lookupWord(cleanWord) || clientDictCache[cacheKey];
  if (cached && isCleanDictEntry(cached)) {
    return { ok: true, entry: cached, source: 'cache', error: '' };
  }
  if (inflightDictRequests.has(cacheKey)) {
    return inflightDictRequests.get(cacheKey);
  }

  const p = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const qs = new URLSearchParams({ word: cleanWord, context: contextEn || '' });
      const resp = await fetch(`/api/define?${qs.toString()}`, { signal: controller.signal });
      clearTimeout(timer);
      if (!resp.ok) {
        return { ok: false, entry: null, source: 'none', error: `词典接口返回 HTTP ${resp.status}` };
      }
      const data = await resp.json();
      if (data?.ok && data.entry && isCleanDictEntry(data.entry)) {
        const cleanEntry = { ...data.entry, headword: cleanWord };
        clientDictCache[cacheKey] = cleanEntry;
        saveCachedWord(cleanWord, cleanEntry);
        return { ok: true, entry: cleanEntry, source: data.source || 'api', error: '' };
      }
      return {
        ok: false,
        entry: null,
        source: 'none',
        error: data?.error ? `在线词典未返回有效释义（${data.error}）` : '在线词典暂未收录该词条',
      };
    } catch (err) {
      clearTimeout(timer);
      const errReason =
        err?.name === 'AbortError'
          ? '在线词典请求超过 8.5 秒超时'
          : '无法连接本地词典接口（请确认 dev_server.py 正在运行）';
      return { ok: false, entry: null, source: 'none', error: errReason };
    } finally {
      inflightDictRequests.delete(cacheKey);
    }
  })();

  inflightDictRequests.set(cacheKey, p);
  return p;
}

function prefetchEpisodeKeywords(episode, isDisposedFn) {
  if (!episode || !Array.isArray(episode.sentences)) return;
  const seen = new Set();
  const queue = [];
  for (const sent of episode.sentences) {
    for (const h of sent.highlights || []) {
      const raw = (h.text || h.key || '').trim();
      const clean = raw.replace(/^[^a-zA-Z'-]+|[^a-zA-Z'-]+$/g, '');
      const key = clean.toLowerCase();
      if (!clean || seen.has(key)) continue;
      seen.add(key);
      if (lookupWord(clean) || clientDictCache[key]) continue;
      queue.push({ word: clean, context: sent.en || '' });
      if (queue.length >= 36) break;
    }
    if (queue.length >= 36) break;
  }
  if (queue.length === 0) return;

  // 后台低并发静默预取（每批 2 个），不阻塞首屏与播放，离开页面立即停止
  const CONCURRENCY = 2;
  let cursor = 0;
  const runWorker = async () => {
    while (cursor < queue.length && !isDisposedFn()) {
      const item = queue[cursor++];
      if (lookupWord(item.word) || clientDictCache[item.word.toLowerCase()]) continue;
      await fetchDefineWithTimeout(item.word, item.context, 7000);
    }
  };
  setTimeout(() => {
    if (isDisposedFn()) return;
    for (let i = 0; i < Math.min(CONCURRENCY, queue.length); i++) {
      runWorker();
    }
  }, 450);
}

async function openWordDictionaryModal(rawWord, episode, onUpdate, ctxSent = null) {
  const cleanWord = String(rawWord || '').trim().replace(/^[^a-zA-Z'-]+|[^a-zA-Z'-]+$/g, '');
  if (!cleanWord) return;
  const cacheKey = cleanWord.toLowerCase();
  const displayHeadword = cleanWord;
  const modalToken = ++activeDictModalToken;

  const fallbackSent =
    ctxSent ||
    episode.sentences.find((s) => s.en.toLowerCase().includes(cacheKey)) ||
    null;
  const occurrences = episode.sentences.filter((s) =>
    s.en.toLowerCase().includes(cacheKey)
  ).length;
  const inVocab = store.hasVocab(cacheKey);
  const modalRoot = document.getElementById('modal-root');

  const buildFallbackEntry = () => ({
    headword: displayHeadword,
    pos: cleanWord.includes(' ') ? 'phrase' : 'word',
    level: '语境兜底',
    us: '',
    uk: '',
    meanings: [
      {
        zh: fallbackSent?.zh
          ? `本句语境参考：${fallbackSent.zh}`
          : '已展示本词基础信息，可点击发音或加入生词本',
        en: '',
      },
    ],
    exampleEn: '',
    exampleZh: '',
  });

  const renderBadgesHtml = (entry) => `
    ${entry?.pos ? `<span class="pill">${escapeHtml(entry.pos)}</span>` : ''}
    ${entry?.level ? `<span class="tag-chip">${escapeHtml(entry.level)}</span>` : ''}
  `;

  const renderMeaningsHtml = (entry) =>
    (entry?.meanings || [])
      .map(
        (m, i) => `
        <div style="background:var(--bg);padding:12px 14px;border-radius:12px;border:1px solid var(--border);">
          <div style="font-size:12px;color:var(--accent);font-weight:700;margin-bottom:4px;">Meaning ${i + 1}</div>
          ${m.zh ? `<div style="font-size:14px;font-weight:600;margin-bottom:4px;">${escapeHtml(m.zh)}</div>` : ''}
          ${m.en && m.en !== m.zh ? `<div style="font-size:13px;color:var(--muted);">${escapeHtml(m.en)}</div>` : ''}
        </div>
      `
      )
      .join('');

  const renderExampleHtml = (entry) =>
    entry?.exampleEn
      ? `<div style="background:var(--bg);padding:12px 14px;border-radius:12px;border:1px solid var(--border);">
           <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">双语例句 Example</div>
           <div style="font-size:14px;font-weight:600;">${escapeHtml(entry.exampleEn)}</div>
           ${entry.exampleZh ? `<div style="font-size:13px;color:var(--muted);margin-top:4px;">${escapeHtml(entry.exampleZh)}</div>` : ''}
         </div>`
      : '';

  const renderStatusHtml = (statusMode, note = '') => {
    if (statusMode === 'syncing') {
      return `<div style="background:var(--bg);padding:8px 12px;border-radius:10px;border:1px solid var(--border);font-size:12px;color:var(--muted);display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <span>✨ 已先展示语境兜底，正在后台补充音标与详细释义…</span>
              </div>`;
    }
    if (statusMode === 'error') {
      return `<div style="background:var(--accent-soft);padding:10px 12px;border-radius:10px;border:1px dashed var(--accent);font-size:12px;color:var(--text);display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
                <span>⚠️ ${escapeHtml(note)}</span>
                <button class="btn btn-outline" id="retry-define-btn" style="padding:4px 10px;font-size:12px;">🔄 重新查询</button>
              </div>`;
    }
    return '';
  };

  let currentEntry = lookupWord(cleanWord) || clientDictCache[cacheKey];
  const isCacheHit = Boolean(currentEntry && isCleanDictEntry(currentEntry));
  if (!isCacheHit) {
    currentEntry = buildFallbackEntry();
  }

  // 立即渲染完整可用卡片（绝不全屏 loading，标题永远是所点单词本身）
  modalRoot.innerHTML = `
    <div class="modal-backdrop" id="m-bg" data-dict-token="${modalToken}">
      <div class="modal-card">
        <div class="modal-header">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
            <h3>${escapeHtml(displayHeadword)}</h3>
            <span id="dict-badges-slot" style="display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;">${renderBadgesHtml(currentEntry)}</span>
          </div>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
            <button class="btn btn-soft" id="speak-us" style="padding:6px 12px;font-size:12px;">🔊 US <span id="dict-us-ipa">${escapeHtml(currentEntry.us || '')}</span></button>
            <button class="btn btn-soft" id="speak-uk" style="padding:6px 12px;font-size:12px;">🔊 UK <span id="dict-uk-ipa">${escapeHtml(currentEntry.uk || currentEntry.us || '')}</span></button>
            <span style="font-size:12px;color:var(--muted);">本集出现 ${Math.max(1, occurrences)} 次</span>
          </div>
          <div id="dict-status-slot">${isCacheHit ? '' : renderStatusHtml('syncing')}</div>
          <div id="dict-meanings-slot" style="display:flex;flex-direction:column;gap:10px;">${renderMeaningsHtml(currentEntry)}</div>
          <div id="dict-example-slot">${renderExampleHtml(currentEntry)}</div>
          ${
            fallbackSent
              ? `<div style="background:var(--accent-soft);padding:11px 14px;border-radius:12px;border:1px solid var(--border);">
                   <div style="font-size:11px;color:var(--accent);font-weight:700;margin-bottom:3px;">本集原句语境 #${fallbackSent.id}</div>
                   <div style="font-size:13px;font-weight:600;">${escapeHtml(fallbackSent.en)}</div>
                   ${fallbackSent.zh ? `<div style="font-size:12px;color:var(--muted);margin-top:2px;">${escapeHtml(fallbackSent.zh)}</div>` : ''}
                 </div>`
              : ''
          }
          <div style="display:flex;justify-content:flex-end;gap:10px;">
            <button class="btn btn-outline" id="copy-word">复制词条</button>
            <button class="btn ${inVocab ? 'btn-soft' : 'btn-primary'}" id="toggle-vocab-btn">
              ${inVocab ? '★ 已在生词本（点击移除）' : '☆ 加入生词本'}
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  const isStillOpen = () => {
    const bg = document.getElementById('m-bg');
    return Boolean(bg && Number(bg.dataset.dictToken) === modalToken && activeDictModalToken === modalToken);
  };

  const patchInPlace = (entry, statusMode = 'done', note = '') => {
    if (!isStillOpen()) return;
    currentEntry = entry;
    const badgesEl = document.getElementById('dict-badges-slot');
    const usEl = document.getElementById('dict-us-ipa');
    const ukEl = document.getElementById('dict-uk-ipa');
    const statusEl = document.getElementById('dict-status-slot');
    const meaningsEl = document.getElementById('dict-meanings-slot');
    const exampleEl = document.getElementById('dict-example-slot');
    if (badgesEl) badgesEl.innerHTML = renderBadgesHtml(entry);
    if (usEl) usEl.textContent = entry.us || '';
    if (ukEl) ukEl.textContent = entry.uk || entry.us || '';
    if (statusEl) statusEl.innerHTML = renderStatusHtml(statusMode, note);
    if (meaningsEl) meaningsEl.innerHTML = renderMeaningsHtml(entry);
    if (exampleEl) exampleEl.innerHTML = renderExampleHtml(entry);
    document.getElementById('retry-define-btn')?.addEventListener('click', () => runBackgroundLookup());
  };

  const runBackgroundLookup = async () => {
    if (isStillOpen()) {
      const statusEl = document.getElementById('dict-status-slot');
      if (statusEl) statusEl.innerHTML = renderStatusHtml('syncing');
    }
    const res = await fetchDefineWithTimeout(cleanWord, fallbackSent?.en || '', 8500);
    if (res.ok && res.entry) {
      patchInPlace(res.entry, 'done', '');
      return;
    }
    patchInPlace(currentEntry, 'error', `${res.error}；当前保留语境兜底，可点击重试`);
  };

  document.getElementById('m-close')?.addEventListener('click', closeModal);
  document.getElementById('m-bg')?.addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
  document.getElementById('speak-us')?.addEventListener('click', () => speechEngine.speak(displayHeadword, { accent: 'US' }));
  document.getElementById('speak-uk')?.addEventListener('click', () => speechEngine.speak(displayHeadword, { accent: 'UK' }));
  document.getElementById('copy-word')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(`${displayHeadword} ${currentEntry?.us || ''} - ${currentEntry?.meanings?.[0]?.zh || ''}`).catch(() => {});
    showToast('已复制词条');
  });
  document.getElementById('toggle-vocab-btn')?.addEventListener('click', () => {
    const added = store.toggleVocab(displayHeadword);
    showToast(added ? `已将 "${displayHeadword}" 加入生词本` : `已从生词本移除 "${displayHeadword}"`);
    closeModal();
    onUpdate();
  });

  // 命中内置词典或本地缓存直接结束，不发任何请求；未命中则在后台静默补充并就地刷新
  if (!isCacheHit) {
    runBackgroundLookup();
  }
}

function openKeywordsModal(keywords, episode, curSent) {
  let scope = 'all';
  let typeFilter = 'all';
  let showMeaning = true;
  let query = '';

  const renderModal = () => {
    let list = keywords;
    if (scope === 'current') list = list.filter((k) => k.sentenceId === curSent.id);
    if (typeFilter !== 'all') list = list.filter((k) => k.dict?.type === typeFilter);
    if (query.trim()) list = list.filter((k) => k.text.toLowerCase().includes(query.trim().toLowerCase()));

    document.getElementById('modal-root').innerHTML = `
      <div class="modal-backdrop" id="m-bg">
        <div class="modal-card">
          <div class="modal-header">
            <h3>本集重点词汇 (${list.length})</h3>
            <button class="icon-circle-sm" id="m-close">✕</button>
          </div>
          <div class="modal-body">
            <input class="filter-input" id="kw-q" placeholder="搜索重点词汇..." value="${escapeHtml(query)}" />
            <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:space-between;">
              <div style="display:flex;gap:6px;">
                <button class="mode-tab ${scope === 'all' ? 'active' : ''}" id="kw-all">全部</button>
                <button class="mode-tab ${scope === 'current' ? 'active' : ''}" id="kw-cur">当前句</button>
              </div>
              <div style="display:flex;gap:6px;">
                <button class="mode-tab ${typeFilter === 'all' ? 'active' : ''}" data-tf="all">全部</button>
                <button class="mode-tab ${typeFilter === 'vocab' ? 'active' : ''}" data-tf="vocab">词汇</button>
                <button class="mode-tab ${typeFilter === 'expression' ? 'active' : ''}" data-tf="expression">表达</button>
                <button class="mode-tab ${showMeaning ? 'active' : ''}" id="kw-meaning">释义</button>
              </div>
            </div>
            <div style="display:flex;flex-direction:column;gap:10px;">
              ${
                list.length === 0
                  ? `<div style="text-align:center;color:var(--muted);padding:20px;">当前筛选下暂无重点词</div>`
                  : list
                      .map(
                        (k) => {
                          const d = lookupWord(k.key);
                          return `
                        <div class="kw-row-item" data-kw-word="${escapeHtml(k.text)}" style="background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px;cursor:pointer;">
                          <div>
                            <div style="font-weight:700;color:var(--accent);">${escapeHtml(k.text)} <span style="font-size:12px;color:var(--muted);font-weight:400;">${escapeHtml(d?.us || '')}</span></div>
                            ${showMeaning ? `<div style="font-size:13px;color:var(--muted);margin-top:3px;">${escapeHtml(d?.meanings?.[0]?.zh || '点击查看详细释义与双语例句 →')}</div>` : ''}
                          </div>
                          <button class="icon-circle-sm kw-play" data-speak="${escapeHtml(k.text)}">🔊</button>
                        </div>
                      `;
                        }
                      )
                      .join('')
              }
            </div>
          </div>
        </div>
      </div>
    `;

    document.getElementById('m-close').addEventListener('click', closeModal);
    document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
    document.getElementById('kw-q').addEventListener('input', (e) => { query = e.target.value; renderModal(); });
    document.getElementById('kw-all').addEventListener('click', () => { scope = 'all'; renderModal(); });
    document.getElementById('kw-cur').addEventListener('click', () => { scope = 'current'; renderModal(); });
    document.getElementById('kw-meaning').addEventListener('click', () => { showMeaning = !showMeaning; renderModal(); });
    document.querySelectorAll('[data-tf]').forEach((b) => b.addEventListener('click', () => { typeFilter = b.dataset.tf; renderModal(); }));
    document.querySelectorAll('.kw-play').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); speechEngine.speak(b.dataset.speak); }));
    document.querySelectorAll('.kw-row-item').forEach((row) => row.addEventListener('click', () => openWordDictionaryModal(row.dataset.kwWord, episode, () => {}, curSent)));
  };
  renderModal();
}

function openVocabModal(onUpdate) {
  const renderModal = () => {
    const list = store.state.vocabBook;
    document.getElementById('modal-root').innerHTML = `
      <div class="modal-backdrop" id="m-bg">
        <div class="modal-card">
          <div class="modal-header">
            <h3>生词本 (${list.length})</h3>
            <button class="icon-circle-sm" id="m-close">✕</button>
          </div>
          <div class="modal-body">
            ${
              list.length === 0
                ? `<p style="text-align:center;color:var(--muted);padding:24px;">暂无收藏生词，点击字幕中的任意单词即可收藏</p>`
                : list
                    .map((item) => {
                      const d = lookupWord(item.key) || { headword: item.key, us: '', meanings: [{ zh: '点击原句中该词可补全释义' }] };
                      return `
                        <div style="background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px;">
                          <div>
                            <div style="font-weight:700;color:var(--accent);">${escapeHtml(d.headword)} <span style="font-size:12px;color:var(--muted);font-weight:400;">${escapeHtml(d.us)}</span></div>
                            <div style="font-size:13px;color:var(--muted);margin-top:3px;">${escapeHtml(d.meanings[0]?.zh || '')}</div>
                          </div>
                          <div style="display:flex;gap:6px;">
                            <button class="icon-circle-sm vb-play" data-speak="${escapeHtml(d.headword)}">🔊</button>
                            <button class="icon-circle-sm vb-del" data-key="${escapeHtml(item.key)}">✕</button>
                          </div>
                        </div>
                      `;
                    })
                    .join('')
            }
          </div>
        </div>
      </div>
    `;
    document.getElementById('m-close').addEventListener('click', closeModal);
    document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
    document.querySelectorAll('.vb-play').forEach((b) => b.addEventListener('click', () => speechEngine.speak(b.dataset.speak)));
    document.querySelectorAll('.vb-del').forEach((b) => b.addEventListener('click', () => {
      store.toggleVocab(b.dataset.key);
      renderModal();
      onUpdate();
    }));
  };
  renderModal();
}

function openCatalogDrawer(library, currentEpId, onSelect) {
  const curIdx = library.episodes.findIndex((e) => e.id === currentEpId);
  const nextEp = library.episodes[curIdx + 1];

  document.getElementById('modal-root').innerHTML = `
    <div class="drawer-backdrop" id="d-bg">
      <div class="drawer-panel">
        <div class="modal-header">
          <h3>当前资料库目录</h3>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          ${
            nextEp
              ? `<button class="btn btn-soft" id="jump-next-ep" style="justify-content:space-between;border-radius:14px;padding:12px 16px;">
                   <span>下一期快捷入口：${escapeHtml(nextEp.number)}</span>
                   <span>立即跳转 →</span>
                 </button>`
              : ''
          }
          ${library.episodes
            .map((ep) => {
              const prog = store.state.episodeProgress[ep.id] || 0;
              return `
                <button class="sentence-card ${ep.id === currentEpId ? 'active' : ''}" data-jump="${ep.id}" style="text-align:left;width:100%;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <span class="pill">${ep.number}</span>
                    <span style="font-size:12px;color:var(--muted);">进度 ${prog}%</span>
                  </div>
                  <div style="font-size:14px;font-weight:600;">${escapeHtml(ep.title)}</div>
                </button>
              `;
            })
            .join('')}
        </div>
      </div>
    </div>
  `;
  document.getElementById('m-close').addEventListener('click', closeModal);
  document.getElementById('d-bg').addEventListener('click', (e) => { if (e.target.id === 'd-bg') closeModal(); });
  document.getElementById('eval-topup-btn')?.addEventListener('click', () => {
    closeModal();
    openUpsellModal(() => openEvalDrawer(episode, sent, onRecordAgain));
  });
  document.getElementById('jump-next-ep')?.addEventListener('click', () => { closeModal(); onSelect(nextEp.id); });
  document.querySelectorAll('[data-jump]').forEach((b) => b.addEventListener('click', () => { closeModal(); onSelect(b.dataset.jump); }));
}

function openABLoopModal(episode, currentRange, onApply) {
  let startIdx = currentRange ? currentRange.startIdx : 0;
  let endIdx = currentRange ? currentRange.endIdx : Math.min(2, episode.sentences.length - 1);

  document.getElementById('modal-root').innerHTML = `
    <div class="modal-backdrop" id="m-bg">
      <div class="modal-card">
        <div class="modal-header">
          <h3>片段复读 (A–B Loop)</h3>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
              <label class="form-label">起始句 (A)</label>
              <select class="form-input" id="ab-start">
                ${episode.sentences.map((s, i) => `<option value="${i}" ${i === startIdx ? 'selected' : ''}>#${s.id} (${formatTime(s.start)}) ${escapeHtml(s.en.slice(0, 26))}...</option>`).join('')}
              </select>
            </div>
            <div>
              <label class="form-label">结束句 (B)</label>
              <select class="form-input" id="ab-end">
                ${episode.sentences.map((s, i) => `<option value="${i}" ${i === endIdx ? 'selected' : ''}>#${s.id} (${formatTime(s.end)}) ${escapeHtml(s.en.slice(0, 26))}...</option>`).join('')}
              </select>
            </div>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:8px;">
            <button class="btn btn-outline" id="ab-clear">关闭复读</button>
            <button class="btn btn-primary" id="ab-go">开始片段复读</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.getElementById('m-close').addEventListener('click', closeModal);
  document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
  document.getElementById('ab-clear').addEventListener('click', () => {
    closeModal();
    showToast('已关闭片段复读');
    onApply(null);
  });
  document.getElementById('ab-go').addEventListener('click', () => {
    const a = Number(document.getElementById('ab-start').value);
    const b = Number(document.getElementById('ab-end').value);
    const sIdx = Math.min(a, b);
    const eIdx = Math.max(a, b);
    closeModal();
    showToast(`已开启 #${sIdx + 1} 到 #${eIdx + 1} 片段复读`);
    onApply({ startIdx: sIdx, endIdx: eIdx });
  });
}

function openSpeedModal(onUpdate) {
  const presets = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0];
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-backdrop" id="m-bg">
      <div class="modal-card" style="max-width:400px;">
        <div class="modal-header">
          <h3>倍速设置</h3>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          <div style="text-align:center;font-size:28px;font-family:var(--font-serif);font-weight:700;color:var(--accent);" id="speed-val">${store.state.playbackRate.toFixed(1)}x</div>
          <input type="range" min="0.5" max="2.0" step="0.1" value="${store.state.playbackRate}" id="speed-slider" style="width:100%;accent-color:var(--accent);" />
          <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;">
            ${presets.map((p) => `<button class="mode-tab ${store.state.playbackRate === p ? 'active' : ''}" data-spd="${p}">${p}x</button>`).join('')}
          </div>
        </div>
      </div>
    </div>
  `;
  document.getElementById('m-close').addEventListener('click', closeModal);
  document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
  document.getElementById('speed-slider').addEventListener('input', (e) => {
    const v = Number(e.target.value);
    store.set({ playbackRate: v });
    document.getElementById('speed-val').textContent = `${v.toFixed(1)}x`;
    onUpdate();
  });
  document.querySelectorAll('[data-spd]').forEach((b) => b.addEventListener('click', () => {
    store.set({ playbackRate: Number(b.dataset.spd) });
    closeModal();
    onUpdate();
  }));
}

function openLoopModal(onUpdate) {
  const counts = [
    { val: 1, label: '单次' },
    { val: 2, label: '2 次' },
    { val: 3, label: '3 次' },
    { val: 5, label: '5 次' },
    { val: 10, label: '10 次' },
    { val: 0, label: '∞ 无限' }
  ];
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-backdrop" id="m-bg">
      <div class="modal-card" style="max-width:420px;">
        <div class="modal-header">
          <h3>循环与播放模式</h3>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          <div style="font-size:13px;color:var(--muted);">单句循环次数</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            ${counts.map((c) => `<button class="mode-tab ${store.state.loopCount === c.val ? 'active' : ''}" data-lc="${c.val}">${c.label}</button>`).join('')}
          </div>
          <label style="display:flex;align-items:center;justify-content:space-between;padding:12px;border-radius:12px;background:var(--bg);border:1px solid var(--border);margin-top:8px;cursor:pointer;">
            <span>仅播放音频（纯听力专注画面）</span>
            <input type="checkbox" id="audio-only-chk" ${store.state.audioOnly ? 'checked' : ''} />
          </label>
        </div>
      </div>
    </div>
  `;
  document.getElementById('m-close').addEventListener('click', closeModal);
  document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
  document.querySelectorAll('[data-lc]').forEach((b) => b.addEventListener('click', () => {
    store.set({ loopCount: Number(b.dataset.lc) });
    closeModal();
    onUpdate();
  }));
  document.getElementById('audio-only-chk').addEventListener('change', (e) => {
    store.set({ audioOnly: e.target.checked });
    onUpdate();
  });
}

function openFontModal(onUpdate) {
  const presets = [
    { label: '小 14px', val: 14 },
    { label: '中 18px', val: 18 },
    { label: '大 22px', val: 22 },
    { label: '超大 26px', val: 26 }
  ];
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-backdrop" id="m-bg">
      <div class="modal-card" style="max-width:440px;">
        <div class="modal-header">
          <h3>字幕字体大小</h3>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          <div id="font-preview" style="padding:16px;border-radius:12px;background:var(--bg);border:1px solid var(--border);font-weight:600;font-size:${store.state.fontSize}px;">
            Let's make sure we're all on the same page.
          </div>
          <input type="range" min="12" max="32" value="${store.state.fontSize}" id="font-slider" style="width:100%;accent-color:var(--accent);" />
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            ${presets.map((p) => `<button class="mode-tab ${store.state.fontSize === p.val ? 'active' : ''}" data-fs="${p.val}">${p.label}</button>`).join('')}
          </div>
          <div style="text-align:right;">
            <button class="btn btn-primary" id="font-done">完成</button>
          </div>
        </div>
      </div>
    </div>
  `;
  document.getElementById('m-close').addEventListener('click', closeModal);
  document.getElementById('font-done').addEventListener('click', closeModal);
  document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
  document.getElementById('font-slider').addEventListener('input', (e) => {
    const v = Number(e.target.value);
    store.set({ fontSize: v });
    document.getElementById('font-preview').style.fontSize = `${v}px`;
    onUpdate();
  });
  document.querySelectorAll('[data-fs]').forEach((b) => b.addEventListener('click', () => {
    const v = Number(b.dataset.fs);
    store.set({ fontSize: v });
    document.getElementById('font-slider').value = v;
    document.getElementById('font-preview').style.fontSize = `${v}px`;
    onUpdate();
  }));
}

function openThemeModal(onUpdate) {
  document.getElementById('modal-root').innerHTML = `
    <div class="modal-backdrop" id="m-bg">
      <div class="modal-card" style="max-width:560px;">
        <div class="modal-header">
          <h3>切换学习页主题（12 套护眼配色）</h3>
          <button class="icon-circle-sm" id="m-close">✕</button>
        </div>
        <div class="modal-body">
          <div class="theme-grid">
            ${THEMES.map(
              (t) => `
              <button class="theme-swatch ${store.state.themeId === t.id ? 'active' : ''}" data-theme="${t.id}" style="background:${t.bg};color:${t.text};border-color:${store.state.themeId === t.id ? t.accent : t.border};">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                  <span style="width:14px;height:14px;border-radius:50%;background:${t.accent};display:inline-block;"></span>
                  <span style="width:14px;height:14px;border-radius:50%;background:${t.card};border:1px solid ${t.border};display:inline-block;"></span>
                </div>
                <div style="font-size:12px;font-weight:700;">${escapeHtml(t.name)}</div>
              </button>
            `
            ).join('')}
          </div>
        </div>
      </div>
    </div>
  `;
  document.getElementById('m-close').addEventListener('click', closeModal);
  document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
  document.querySelectorAll('[data-theme]').forEach((b) => b.addEventListener('click', () => {
    const theme = THEMES.find((t) => t.id === b.dataset.theme);
    if (!theme) return;
    store.set({ themeId: theme.id });
    applyThemeVars(theme);
    showToast(`已切换主题：${theme.name}`);
    closeModal();
    onUpdate();
  }));
}

function openPdfPreviewModal(episode) {
  let langMode = 'bilingual';
  const renderModal = () => {
    document.getElementById('modal-root').innerHTML = `
      <div class="modal-backdrop" id="m-bg">
        <div class="modal-card" style="max-width:640px;">
          <div class="modal-header">
            <h3>字幕讲义打印预览 / 导出 PDF</h3>
            <button class="icon-circle-sm" id="m-close">✕</button>
          </div>
          <div class="modal-body">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
              <div style="display:flex;gap:6px;">
                <button class="mode-tab ${langMode === 'bilingual' ? 'active' : ''}" data-lm="bilingual">双语</button>
                <button class="mode-tab ${langMode === 'en' ? 'active' : ''}" data-lm="en">仅 EN</button>
                <button class="mode-tab ${langMode === 'zh' ? 'active' : ''}" data-lm="zh">仅 ZH</button>
              </div>
              <button class="btn btn-primary" id="btn-print-pdf">另存为 PDF / 打印</button>
            </div>
            <div id="print-preview-sheet" style="background:#fff;color:#1f1f1f;border:1px solid var(--border);border-radius:12px;padding:22px;">
              <div style="font-size:12px;color:#888;margin-bottom:4px;">刚认识不久 Just met · 刚认识小屋 英语自习室</div>
              <h2 style="font-family:var(--font-serif);font-size:20px;margin-bottom:14px;">${escapeHtml(episode.number)} · ${escapeHtml(episode.title)}</h2>
              ${episode.sentences
                .map(
                  (s) => `
                  <div style="margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #eee;">
                    <div style="font-size:11px;color:#999;">#${s.id} · ${formatTime(s.start)} - ${formatTime(s.end)} · ${escapeHtml(s.speaker)}</div>
                    ${langMode !== 'zh' ? `<div style="font-size:14px;font-weight:600;margin-top:3px;">${escapeHtml(s.en)}</div>` : ''}
                    ${langMode !== 'en' ? `<div style="font-size:13px;color:#555;margin-top:2px;">${escapeHtml(s.zh)}</div>` : ''}
                  </div>
                `
                )
                .join('')}
            </div>
          </div>
        </div>
      </div>
    `;
    document.getElementById('m-close').addEventListener('click', closeModal);
    document.getElementById('m-bg').addEventListener('click', (e) => { if (e.target.id === 'm-bg') closeModal(); });
    document.querySelectorAll('[data-lm]').forEach((b) => b.addEventListener('click', () => { langMode = b.dataset.lm; renderModal(); }));
    document.getElementById('btn-print-pdf').addEventListener('click', () => window.print());
  };
  renderModal();
}

function openEvalDrawer(episode, sent, onRecordAgain) {
  const recKey = `${episode.id}:${sent.id}`;
  let evalRes = store.state.evalScores[recKey];
  let selectedWordIdx = 0;

  const renderDrawer = () => {
    const activeWord = evalRes?.wordScores?.[selectedWordIdx] || evalRes?.wordScores?.[0] || null;
    document.getElementById('modal-root').innerHTML = `
      <div class="drawer-backdrop" id="d-bg">
        <div class="drawer-panel" style="max-width:460px;">
          <div class="modal-header">
            <h3>AI 逐词音素级深度评测 · #${sent.id}</h3>
            <button class="icon-circle-sm" id="m-close">✕</button>
          </div>
          <div class="modal-body">
            <div style="background:var(--accent-soft);border:1px solid var(--border);border-radius:12px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px;">
              <div style="font-size:12px;">
                <strong>💎 AI 深度评测积分：${store.state.credits} 点</strong><br />
                <span style="color:var(--muted);">每次音素级深度诊断消耗 1 积分</span>
              </div>
              <button class="btn btn-primary" id="eval-topup-btn" style="padding:6px 12px;font-size:12px;">充值 / 兑换</button>
            </div>

            <div style="background:var(--bg);border:1px solid var(--border);border-radius:14px;padding:14px;">
              <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">目标例句</div>
              <div style="font-size:15px;font-weight:600;">${escapeHtml(sent.en)}</div>
              <div style="font-size:13px;color:var(--muted);margin-top:4px;">${escapeHtml(sent.zh)}</div>
            </div>

            <div style="display:flex;gap:8px;">
              <button class="btn btn-soft" id="eval-play-orig" style="flex:1;padding:8px 10px;font-size:13px;">🔊 听原声</button>
              <button class="btn btn-outline" id="eval-play-mine" style="flex:1;padding:8px 10px;font-size:13px;">🎧 听我的发音</button>
              <button class="btn btn-outline" id="eval-re-record" style="padding:8px 12px;font-size:13px;">🎤 重录</button>
            </div>

            ${
              evalRes
                ? `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center;">
                     <div class="kpi-card" style="padding:10px 6px;"><div class="kpi-label">综合分</div><div class="kpi-value" style="font-size:21px;color:var(--accent);">${evalRes.overall}</div></div>
                     <div class="kpi-card" style="padding:10px 6px;"><div class="kpi-label">准确度</div><div class="kpi-value" style="font-size:21px;">${evalRes.accuracy}</div></div>
                     <div class="kpi-card" style="padding:10px 6px;"><div class="kpi-label">流利度</div><div class="kpi-value" style="font-size:21px;">${evalRes.fluency}</div></div>
                     <div class="kpi-card" style="padding:10px 6px;"><div class="kpi-label">语调重音</div><div class="kpi-value" style="font-size:21px;">${evalRes.prosody || evalRes.completeness}</div></div>
                   </div>

                   <div>
                     <div style="font-size:12px;font-weight:600;margin-bottom:6px;">点击任意单词查看「音素级」口腔纠音细节（绿≥82 · 黄65-81 · 红&lt;65）：</div>
                     <div>
                       ${evalRes.wordScores
                         .map(
                           (w, idx) => `<button class="eval-word-chip ${w.status}" data-widx="${idx}" style="border:${idx === selectedWordIdx ? '2px solid var(--text)' : '2px solid transparent'};">${escapeHtml(w.word)} ${w.score}</button>`
                         )
                         .join('')}
                     </div>
                   </div>

                   ${
                     activeWord
                       ? `<div style="background:var(--bg);border:1.5px solid var(--accent);border-radius:14px;padding:14px;">
                            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                              <div>
                                <span style="font-size:16px;font-weight:700;">${escapeHtml(activeWord.word)}</span>
                                <span class="pill" style="margin-left:6px;">单词得分 ${activeWord.score}</span>
                              </div>
                              <button class="btn btn-soft" id="eval-slow-word" style="padding:4px 10px;font-size:12px;">🐢 0.7x 慢速示范</button>
                            </div>
                            <div style="display:flex;flex-direction:column;gap:8px;">
                              ${(activeWord.phonemes || [])
                                .map(
                                  (ph) => `
                                  <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:8px 10px;">
                                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">
                                      <strong style="font-family:ui-monospace,monospace;font-size:14px;">${escapeHtml(ph.symbol)}</strong>
                                      <span class="eval-word-chip ${ph.status}" style="margin:0;padding:1px 8px;font-size:11px;">${ph.score} 分</span>
                                    </div>
                                    <div style="font-size:12px;color:var(--muted);">${escapeHtml(ph.tip)}</div>
                                  </div>
                                `
                                )
                                .join('')}
                            </div>
                          </div>`
                       : ''
                   }

                   <div style="font-size:12px;color:var(--muted);background:var(--bg);padding:10px 12px;border-radius:10px;border:1px solid var(--border);">
                     <strong>✨ 连读与语调建议：</strong>${escapeHtml(evalRes.linkingTip || '保持自然语速，重点词适当加重。')}
                   </div>`
                : `<div style="text-align:center;padding:24px 14px;background:var(--bg);border-radius:14px;border:1px dashed var(--border);display:flex;flex-direction:column;gap:10px;align-items:center;">
                     <p style="font-size:14px;">还没有本句的音素级评测报告</p>
                     <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;">
                       <button class="btn btn-primary" id="eval-start-rec">🎤 立即跟读并评测</button>
                       <button class="btn btn-soft" id="eval-demo-btn">✨ 一键查看音素级评测演示</button>
                     </div>
                   </div>`
            }
          </div>
        </div>
      </div>
    `;

    document.getElementById('m-close').addEventListener('click', closeModal);
    document.getElementById('d-bg').addEventListener('click', (e) => { if (e.target.id === 'd-bg') closeModal(); });
    document.getElementById('eval-topup-btn')?.addEventListener('click', () => {
      closeModal();
      openUpsellModal(() => openEvalDrawer(episode, sent, onRecordAgain));
    });
    document.getElementById('eval-play-orig').addEventListener('click', () => speechEngine.speak(sent.en, { rate: store.state.playbackRate }));
    document.getElementById('eval-play-mine').addEventListener('click', () => {
      const ok = speechEngine.playRecording(recKey);
      if (!ok) showToast('还没有录制你的声音，先点击跟读录音吧');
    });
    document.getElementById('eval-re-record')?.addEventListener('click', () => {
      closeModal();
      onRecordAgain();
    });
    document.getElementById('eval-start-rec')?.addEventListener('click', () => {
      closeModal();
      onRecordAgain();
    });
    document.getElementById('eval-demo-btn')?.addEventListener('click', () => {
      evalRes = speechEngine.evaluatePronunciation(sent.en, '');
      // Auto-select the lowest-scoring word so user immediately sees phoneme coaching
      let minIdx = 0;
      evalRes.wordScores.forEach((w, i) => {
        if (w.score < evalRes.wordScores[minIdx].score) minIdx = i;
      });
      selectedWordIdx = minIdx;
      store.saveEvalScore(episode.id, sent.id, evalRes);
      renderDrawer();
    });
    document.querySelectorAll('[data-widx]').forEach((btn) => {
      btn.addEventListener('click', () => {
        selectedWordIdx = Number(btn.dataset.widx);
        renderDrawer();
      });
    });
    document.getElementById('eval-slow-word')?.addEventListener('click', () => {
      if (activeWord) speechEngine.speak(activeWord.word, { rate: 0.7 });
    });
  };

  if (evalRes?.wordScores?.length) {
    let minIdx = 0;
    evalRes.wordScores.forEach((w, i) => {
      if (w.score < evalRes.wordScores[minIdx].score) minIdx = i;
    });
    selectedWordIdx = minIdx;
  }
  renderDrawer();
}
