// Just Met 宇宙路由与应用启动入口
import { store, applyThemeVars } from './store.js';
import { renderLoginPage, renderUniverseHub, renderLibraryPage, renderVocabPage, renderMembershipPage } from './views.js';
import { renderPracticeWorkspace } from './practice.js';
import { mountDarcyCompanion } from './darcy_companion.js';

const appRoot = document.getElementById('app');
let cleanupCurrentView = null;

function navigate(hash) {
  if (window.location.hash === hash) {
    renderRoute();
  } else {
    window.location.hash = hash;
  }
}

function renderRoute() {
  if (cleanupCurrentView) {
    cleanupCurrentView();
    cleanupCurrentView = null;
  }
  document.getElementById('modal-root').innerHTML = '';

  applyThemeVars(store.getTheme());

  const hash = window.location.hash || '#/login';

  if (hash === '#/login') {
    renderLoginPage(appRoot, navigate);
    return;
  }

  if (hash === '#/universe') {
    renderUniverseHub(appRoot, navigate);
    return;
  }

  if (hash === '#/library') {
    renderLibraryPage(appRoot, navigate);
    return;
  }

  if (hash === '#/vocab') {
    renderVocabPage(appRoot, navigate);
    return;
  }

  if (hash === '#/membership') {
    renderMembershipPage(appRoot, navigate);
    return;
  }

  if (hash.startsWith('#/episode/')) {
    const epId = hash.replace('#/episode/', '').split('?')[0];
    cleanupCurrentView = renderPracticeWorkspace(appRoot, epId, navigate);
    return;
  }

  renderLoginPage(appRoot, navigate);
}

window.addEventListener('hashchange', renderRoute);
renderRoute();
mountDarcyCompanion();
