(function (global) {
  'use strict';

  function requireShell() {
    if (!global.SizaBookShellV1) {
      throw new Error('SizaBookShellV1 must be loaded before its frontend adapter.');
    }
    return global.SizaBookShellV1;
  }

  function playerFromState(state, portrait) {
    const mag = state && state.player && state.player.mag ? state.player.mag : {};
    return {
      id: mag.id,
      name: mag.name,
      title: mag.title,
      portrait,
      life: mag.life,
      mf: mag.mf,
      prow: mag.prow,
      eva: mag.eva,
      status: []
    };
  }

  function adventure(input) {
    const Shell = requireShell();
    const source = input || {};
    const state = source.state || {};
    const event = source.event || {};
    const adv = state.adventure || {};
    const meta = source.meta || {};

    return Shell.createModel({
      mode: source.mode || Shell.MODES.EXPLORATION,
      header: {
        chapter: meta.chapter,
        location: meta.location,
        region: meta.region,
        time: meta.time,
        condition: meta.condition || adv.landState
      },
      player: playerFromState(state, source.playerPortrait),
      counterpart: source.counterpart || null,
      scene: {
        title: event.title || meta.sceneTitle,
        subtitle: meta.sceneSubtitle,
        image: meta.sceneImage,
        state: adv.landState
      },
      narrative: {
        speaker: source.speaker,
        lead: event.lead,
        text: event.text,
        prompt: source.prompt || '¿Qué haces?',
        log: Array.isArray(adv.journal) ? adv.journal : []
      },
      actions: (Array.isArray(event.choices) ? event.choices : []).map((choice, index) => ({
        id: `${event.id || 'event'}-${index}`,
        label: choice.label,
        hint: choice.hint,
        kind: source.mode === Shell.MODES.DIALOGUE ? 'dialogue' : 'context',
        enabled: true,
        payload: { choiceIndex: index }
      })),
      resources: {
        advance: adv.advance,
        advanceMax: source.advanceMax || 5
      },
      payload: adv
    });
  }

  function combat(input) {
    const Shell = requireShell();
    const source = input || {};
    const state = source.state || {};
    const match = state.match || {};
    const player = match.player || {};
    const enemy = match.enemy || {};
    const mag = state.player && state.player.mag ? state.player.mag : {};
    const meta = source.meta || {};

    return Shell.createModel({
      mode: Shell.MODES.COMBAT,
      header: {
        chapter: meta.chapter,
        location: meta.location,
        region: meta.region,
        time: meta.time,
        condition: meta.condition
      },
      player: {
        id: source.playerId || mag.id,
        name: source.playerName || mag.name,
        title: mag.title,
        portrait: source.playerPortrait,
        life: player.life,
        mf: player.mf,
        prow: player.prow,
        eva: player.eva,
        status: []
      },
      counterpart: {
        id: source.rivalId || 'rival',
        name: source.rivalName || 'Rival',
        title: source.rivalTitle || '',
        portrait: source.rivalPortrait || '',
        life: enemy.life,
        mf: enemy.mf,
        prow: enemy.prow,
        eva: enemy.eva,
        status: []
      },
      scene: {
        title: meta.sceneTitle || 'Enfrentamiento',
        subtitle: meta.sceneSubtitle,
        image: meta.sceneImage,
        state: match.phase
      },
      narrative: {
        lead: source.lead,
        text: source.text,
        prompt: source.prompt || 'Elige tu siguiente acción.',
        log: Array.isArray(match.log) ? match.log : []
      },
      actions: [],
      resources: {
        crystals: player.crystals || null,
        hand: Array.isArray(player.hand) ? player.hand : [],
        turn: match.turn,
        phase: match.phase
      },
      payload: match
    });
  }

  global.SizaBookShellAdapterV1 = Object.freeze({
    adventure,
    combat
  });
})(window);
