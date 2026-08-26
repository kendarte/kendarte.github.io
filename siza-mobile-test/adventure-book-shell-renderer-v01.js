(function (global) {
  'use strict';

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }[char];
    });
  }

  function modeClass(mode) {
    if (mode === 'COMBAT') return 'modeCombat';
    if (mode === 'DIALOGUE') return 'modeDialogue';
    return 'modeExploration';
  }

  function portrait(character, side) {
    if (!character) return '<div class="bookIdentityV01 ' + (side || '') + '"></div>';
    const image = character.portrait
      ? '<img src="' + esc(character.portrait) + '" alt="' + esc(character.name) + '">'
      : '';
    const stats = [
      Number.isFinite(character.life) ? 'VIDA ' + character.life : '',
      Number.isFinite(character.mf) ? 'MF ' + character.mf : ''
    ].filter(Boolean).join(' · ');

    const copy = '<div><b>' + esc(character.name) + '</b>' +
      (character.title ? '<span>' + esc(character.title) + '</span>' : '') +
      (stats ? '<div class="bookStatsV01">' + esc(stats) + '</div>' : '') +
      '</div>';

    return '<div class="bookIdentityV01 ' + (side || '') + '">' +
      (side === 'right' ? copy + image : image + copy) +
      '</div>';
  }

  function header(model) {
    const h = model.header || {};
    const title = h.location || model.scene.title || 'SIZA';
    const context = [h.condition, h.time].filter(Boolean).join(' · ');
    return '<header class="bookHeaderV01">' +
      portrait(model.player, '') +
      '<div class="bookChapterV01"><div>' +
        (h.chapter ? '<small>' + esc(h.chapter) + '</small>' : '<small>AVENTURA</small>') +
        '<b>' + esc(title) + '</b>' +
        (context ? '<span>' + esc(context) + '</span>' : '') +
      '</div></div>' +
      portrait(model.counterpart, 'right') +
    '</header>';
  }

  function narrative(model) {
    const n = model.narrative || {};
    const speaker = n.speaker ? '<b>' + esc(n.speaker) + ':</b> ' : '';
    const lead = n.lead ? '<div>' + esc(n.lead) + '</div>' : '';
    const text = n.text ? '<div>' + speaker + esc(n.text) + '</div>' : '';
    const prompt = n.prompt ? '<div class="bookPromptV01">&gt; ' + esc(n.prompt) + '</div>' : '';
    if (!lead && !text && !prompt) return '';
    return '<div class="bookNarrativeTextV01">' + lead + text + prompt + '</div>';
  }

  function render(model, slots) {
    const safeModel = model || { mode: 'EXPLORATION', header: {}, scene: {}, narrative: {} };
    const content = slots || {};
    const sceneHtml = content.sceneHtml || '';
    const narrativeHtml = content.narrativeHtml === undefined ? narrative(safeModel) : content.narrativeHtml;
    const actionsHtml = content.actionsHtml || '';
    const overlaysHtml = content.overlaysHtml || '';
    const menuHtml = content.menuHtml || '';

    return '<section class="bookShellV01 ' + modeClass(safeModel.mode) + '" data-book-mode="' + esc(safeModel.mode) + '">' +
      menuHtml +
      header(safeModel) +
      '<div class="bookBodyV01">' +
        '<div class="bookSceneV01">' + sceneHtml + '</div>' +
        '<section class="bookNarrativeV01">' + narrativeHtml + actionsHtml + '</section>' +
        overlaysHtml +
      '</div>' +
    '</section>';
  }

  global.SizaBookShellRendererV1 = Object.freeze({
    esc,
    modeClass,
    header,
    narrative,
    render
  });
})(window);
