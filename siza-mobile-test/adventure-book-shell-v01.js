(function (global) {
  'use strict';

  const MODES = Object.freeze({
    EXPLORATION: 'EXPLORATION',
    DIALOGUE: 'DIALOGUE',
    COMBAT: 'COMBAT'
  });

  function cleanText(value, fallback = '') {
    if (value === null || value === undefined) return fallback;
    return String(value);
  }

  function cleanNumber(value, fallback = 0) {
    return Number.isFinite(value) ? value : fallback;
  }

  function cleanOptionalNumber(value) {
    return Number.isFinite(value) ? value : null;
  }

  function normalizeMode(mode) {
    const value = String(mode || '').toUpperCase();
    return MODES[value] || MODES.EXPLORATION;
  }

  function normalizeCharacter(character) {
    if (!character) return null;
    return {
      id: cleanText(character.id),
      name: cleanText(character.name),
      title: cleanText(character.title),
      portrait: cleanText(character.portrait),
      life: cleanOptionalNumber(character.life),
      mf: cleanOptionalNumber(character.mf),
      prow: cleanOptionalNumber(character.prow),
      eva: cleanOptionalNumber(character.eva),
      status: Array.isArray(character.status) ? character.status.map(String) : []
    };
  }

  function normalizeAction(action, index) {
    if (!action) return null;
    return {
      id: cleanText(action.id, `action-${index}`),
      label: cleanText(action.label),
      hint: cleanText(action.hint),
      kind: cleanText(action.kind, 'context'),
      enabled: action.enabled !== false,
      payload: action.payload === undefined ? null : action.payload
    };
  }

  function createModel(input) {
    const source = input || {};
    const header = source.header || {};
    const scene = source.scene || {};
    const narrative = source.narrative || {};
    const resources = source.resources || {};

    return {
      version: '0.1',
      mode: normalizeMode(source.mode),
      header: {
        chapter: cleanText(header.chapter),
        location: cleanText(header.location),
        region: cleanText(header.region),
        time: cleanText(header.time),
        condition: cleanText(header.condition)
      },
      player: normalizeCharacter(source.player),
      counterpart: normalizeCharacter(source.counterpart),
      scene: {
        title: cleanText(scene.title),
        subtitle: cleanText(scene.subtitle),
        image: cleanText(scene.image),
        state: cleanText(scene.state)
      },
      narrative: {
        speaker: cleanText(narrative.speaker),
        lead: cleanText(narrative.lead),
        text: cleanText(narrative.text),
        prompt: cleanText(narrative.prompt, '¿Qué haces?'),
        log: Array.isArray(narrative.log) ? narrative.log.slice() : []
      },
      actions: (Array.isArray(source.actions) ? source.actions : [])
        .map(normalizeAction)
        .filter(Boolean),
      resources: {
        crystals: resources.crystals || null,
        hand: Array.isArray(resources.hand) ? resources.hand.slice() : [],
        advance: cleanNumber(resources.advance),
        advanceMax: cleanNumber(resources.advanceMax),
        turn: cleanNumber(resources.turn),
        phase: cleanText(resources.phase)
      },
      payload: source.payload === undefined ? null : source.payload
    };
  }

  function modeFromFrontendState(state) {
    if (state && state.route === 'match') return MODES.COMBAT;
    return MODES.EXPLORATION;
  }

  global.SizaBookShellV1 = Object.freeze({
    MODES,
    normalizeMode,
    normalizeCharacter,
    createModel,
    modeFromFrontendState
  });
})(window);
