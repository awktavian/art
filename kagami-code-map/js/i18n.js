/**
 * Internationalization System
 * Supports dynamic language switching and pluralization
 */

// Language definitions
const TRANSLATIONS = {
  en: {
    // App
    appTitle: 'Code Map',
    appSubtitle: 'Semantic Explorer',
    
    // Search
    searchPlaceholder: 'Search files, classes, functions...',
    searchResults: '{count} results',
    searchNoResults: 'No matches found',
    
    // Stats
    files: 'files',
    file: 'file',
    lines: 'lines',
    line: 'line',
    clusters: 'clusters',
    cluster: 'cluster',
    
    // Categories
    categories: 'Categories',
    category: 'Category',
    
    // Treemap
    treemapView: 'Treemap',
    expandFolder: 'Click to expand',
    collapseFolder: 'Click to collapse',
    
    // 3D Explorer
    semanticExplorer: '3D Explorer',
    semanticSpace: 'Semantic Space',
    explore3d: 'Explore in 3D',
    orbit: 'Orbit',
    top: 'Top',
    front: 'Front',
    reset: 'Reset',
    autoRotate: 'Auto Rotate',
    
    // Layers
    layers: 'Layers',
    imports: 'Imports',
    exports: 'Exports',
    shared: 'Shared Dependencies',
    labels: 'Labels',
    grid: 'Grid',
    
    // View modes
    viewModes: 'View Modes',
    normal: 'Normal',
    explode: 'Exploded',
    isolate: 'Isolate',
    xray: 'X-Ray',
    section: 'Section',
    trace: 'Trace',
    
    // File details
    fileDetails: 'File Details',
    path: 'Path',
    size: 'Size',
    importance: 'Importance',
    summary: 'Summary',
    concepts: 'Concepts',
    
    // Relationships
    relationships: 'Relationships',
    relatedFiles: 'Related Files',
    similarFiles: 'Similar Files',
    importedBy: 'Imported By',
    importsList: 'Imports',
    sharedDeps: 'Shared Dependencies',
    
    // Actions
    close: 'Close',
    zoomIn: 'Zoom In',
    zoomOut: 'Zoom Out',
    fullscreen: 'Fullscreen',
    
    // Tooltips
    holdToExpand: 'Hold to see details',
    clickToSelect: 'Click to select',
    dragToRotate: 'Drag to rotate',
    scrollToZoom: 'Scroll to zoom',
    
    // Accessibility
    skipToMain: 'Skip to main content',
    loading: 'Loading...',
    error: 'Error loading data',
    
    // Relevance
    matchExact: 'exact match',
    matchPrefix: 'starts with',
    matchContains: 'contains',
    matchPath: 'path match',
    matchDoc: 'in docs',
    matchSemantic: 'similar code',
    matchCluster: 'same cluster',
  },
  
  ja: {
    appTitle: 'コードマップ',
    appSubtitle: '意味的エクスプローラー',
    searchPlaceholder: 'ファイル、クラス、関数を検索...',
    searchResults: '{count}件の結果',
    searchNoResults: '一致するものが見つかりません',
    files: 'ファイル',
    file: 'ファイル',
    lines: '行',
    line: '行',
    clusters: 'クラスタ',
    cluster: 'クラスタ',
    categories: 'カテゴリ',
    category: 'カテゴリ',
    treemapView: 'ツリーマップ',
    semanticExplorer: '3Dエクスプローラー',
    semanticSpace: '意味空間',
    explore3d: '3Dで探索',
    orbit: '軌道',
    top: '上面',
    front: '正面',
    reset: 'リセット',
    autoRotate: '自動回転',
    layers: 'レイヤー',
    imports: 'インポート',
    exports: 'エクスポート',
    shared: '共有依存関係',
    labels: 'ラベル',
    grid: 'グリッド',
    fileDetails: 'ファイル詳細',
    path: 'パス',
    size: 'サイズ',
    importance: '重要度',
    summary: '概要',
    concepts: 'コンセプト',
    relationships: '関係',
    relatedFiles: '関連ファイル',
    similarFiles: '類似ファイル',
    close: '閉じる',
    zoomIn: '拡大',
    zoomOut: '縮小',
    holdToExpand: '長押しで詳細表示',
    clickToSelect: 'クリックで選択',
    dragToRotate: 'ドラッグで回転',
    scrollToZoom: 'スクロールで拡大',
    skipToMain: 'メインコンテンツへ',
    loading: '読み込み中...',
    error: 'データの読み込みエラー',
    matchExact: '完全一致',
    matchPrefix: '前方一致',
    matchContains: '部分一致',
    matchSemantic: '類似コード',
    matchCluster: '同クラスタ',
  },
  
  zh: {
    appTitle: '代码地图',
    appSubtitle: '语义探索器',
    searchPlaceholder: '搜索文件、类、函数...',
    files: '文件',
    lines: '行',
    clusters: '集群',
    categories: '分类',
    semanticExplorer: '3D探索器',
    close: '关闭',
    loading: '加载中...',
  },
  
  ko: {
    appTitle: '코드맵',
    appSubtitle: '시맨틱 탐색기',
    searchPlaceholder: '파일, 클래스, 함수 검색...',
    files: '파일',
    lines: '줄',
    clusters: '클러스터',
    categories: '카테고리',
    semanticExplorer: '3D 탐색기',
    close: '닫기',
    loading: '로딩 중...',
  },
  
  es: {
    appTitle: 'Mapa de Código',
    appSubtitle: 'Explorador Semántico',
    searchPlaceholder: 'Buscar archivos, clases, funciones...',
    files: 'archivos',
    lines: 'líneas',
    clusters: 'grupos',
    categories: 'Categorías',
    semanticExplorer: 'Explorador 3D',
    close: 'Cerrar',
    loading: 'Cargando...',
  },
};

// Current language state
let currentLang = 'en';
const listeners = new Set();

/**
 * Get translation for key with optional interpolation
 * @param {string} key - Translation key
 * @param {object} params - Interpolation parameters
 * @returns {string} Translated string
 */
export function t(key, params = {}) {
  const translations = TRANSLATIONS[currentLang] || TRANSLATIONS.en;
  let text = translations[key] || TRANSLATIONS.en[key] || key;
  
  // Interpolate {param} placeholders
  Object.entries(params).forEach(([k, v]) => {
    text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
  });
  
  return text;
}

/**
 * Get current language code
 */
export function getLang() {
  return currentLang;
}

/**
 * Set language and update all UI elements
 * @param {string} lang - Language code
 */
export function setLang(lang) {
  if (!TRANSLATIONS[lang]) {
    console.warn(`Language "${lang}" not supported, falling back to English`);
    lang = 'en';
  }
  
  currentLang = lang;
  document.documentElement.lang = lang;
  document.documentElement.dataset.lang = lang;
  localStorage.setItem('codemap-lang', lang);
  
  // Update all elements with data-i18n attributes
  updateI18nElements();
  
  // Notify listeners
  listeners.forEach(fn => fn(lang));
}

/**
 * Subscribe to language changes
 * @param {function} callback - Called with new language code
 * @returns {function} Unsubscribe function
 */
export function onLangChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

/**
 * Update all elements with i18n data attributes
 */
export function updateI18nElements() {
  // Text content
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  
  // Placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  
  // ARIA labels
  document.querySelectorAll('[data-i18n-aria]').forEach(el => {
    el.setAttribute('aria-label', t(el.dataset.i18nAria));
  });
  
  // Titles
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
}

/**
 * Detect user's preferred language
 */
export function detectLang() {
  // Check localStorage first
  const stored = localStorage.getItem('codemap-lang');
  if (stored && TRANSLATIONS[stored]) return stored;
  
  // Check browser language
  const browserLang = navigator.language?.split('-')[0];
  if (browserLang && TRANSLATIONS[browserLang]) return browserLang;
  
  return 'en';
}

/**
 * Get list of supported languages
 */
export function getSupportedLangs() {
  return Object.keys(TRANSLATIONS).map(code => ({
    code,
    name: {
      en: 'English',
      ja: '日本語',
      zh: '中文',
      ko: '한국어',
      es: 'Español',
    }[code] || code,
  }));
}

/**
 * Format number with locale
 */
export function formatNumber(num) {
  return new Intl.NumberFormat(currentLang).format(num);
}

/**
 * Format date with locale
 */
export function formatDate(date) {
  return new Intl.DateTimeFormat(currentLang, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date instanceof Date ? date : new Date(date));
}

// Initialize
export function initI18n() {
  const lang = detectLang();
  setLang(lang);
}
