/* Playgama Bridge v2 compatibility layer for Yandex-integrated browser ports. */
(() => {
  'use strict';
  if (window.__playgamaYandexCompatInstalled) return;
  window.__playgamaYandexCompatInstalled = true;

  const pauseListeners = new Set();
  const resumeListeners = new Set();
  const pauseReasons = new Set();
  const trackedAudioContexts = new Set();
  const pausedMedia = new Set();
  let pseudoSdk = null;
  let pseudoPlayer = null;
  let gameReadySent = false;
  let gameplayStarted = false;
  let platformAudioEnabled = true;

  const safeCall = (callback, ...args) => {
    try { callback?.(...args); } catch (error) { console.warn('[Playgama] callback failed:', error); }
  };

  const normalizeLanguage = (value) => {
    const code = String(value || navigator.language || 'en').trim().toLowerCase().split(/[-_]/)[0];
    return code || 'en';
  };

  const wrapAudioContext = () => {
    const NativeAudioContext = window.AudioContext || window.webkitAudioContext;
    if (!NativeAudioContext || NativeAudioContext.__playgamaCompatWrapped) return;
    const WrappedAudioContext = new Proxy(NativeAudioContext, {
      construct(target, args, newTarget) {
        const context = Reflect.construct(target, args, newTarget === WrappedAudioContext ? target : newTarget);
        trackedAudioContexts.add(context);
        return context;
      }
    });
    WrappedAudioContext.__playgamaCompatWrapped = true;
    window.AudioContext = WrappedAudioContext;
    if (window.webkitAudioContext === NativeAudioContext) window.webkitAudioContext = WrappedAudioContext;
  };

  const pauseTrackedAudio = () => {
    trackedAudioContexts.forEach((context) => {
      if (context?.state === 'running') context.suspend?.().catch?.(() => {});
    });
    document.querySelectorAll('audio,video').forEach((media) => {
      if (!media.paused) {
        pausedMedia.add(media);
        try { media.pause(); } catch (_) {}
      }
    });
  };

  const resumeTrackedAudio = () => {
    if (pauseReasons.size || !platformAudioEnabled || document.hidden) return;
    trackedAudioContexts.forEach((context) => {
      if (context?.state === 'suspended') context.resume?.().catch?.(() => {});
    });
    Array.from(pausedMedia).forEach((media) => {
      pausedMedia.delete(media);
      try { media.play?.().catch?.(() => {}); } catch (_) {}
    });
  };

  const emitPauseState = () => {
    const paused = pauseReasons.size > 0;
    const listeners = paused ? pauseListeners : resumeListeners;
    listeners.forEach((listener) => safeCall(listener));
    if (paused) pauseTrackedAudio(); else resumeTrackedAudio();
  };

  const setPauseReason = (reason, active) => {
    const wasPaused = pauseReasons.size > 0;
    if (active) pauseReasons.add(reason); else pauseReasons.delete(reason);
    const isPaused = pauseReasons.size > 0;
    if (wasPaused !== isPaused) emitPauseState();
  };

  wrapAudioContext();

  const initializeBridge = async () => {
    if (!window.bridge || typeof window.bridge.initialize !== 'function') {
      throw new Error('Playgama Bridge script is unavailable');
    }

    // v2 reports this engine value to the Playgama QA tool.
    window.bridge.engine = 'javascript';
    await window.bridge.initialize({ configFilePath: './playgama-bridge-config.json' });
    const bridge = window.bridge;

    if (!String(bridge.version || '').startsWith('2.')) {
      throw new Error(`Playgama Bridge v2 required, loaded ${bridge.version || 'unknown'}`);
    }

    try { bridge.advertisement?.setMinimumDelayBetweenInterstitial?.(120); } catch (_) {}

    platformAudioEnabled = bridge.platform?.isAudioEnabled !== false;
    if (!platformAudioEnabled) pauseTrackedAudio();

    try {
      bridge.platform?.on?.(bridge.EVENT_NAME.PAUSE_STATE_CHANGED, (paused) => {
        setPauseReason('platform', Boolean(paused));
      });
    } catch (error) {
      console.warn('[Playgama] pause event subscription failed:', error);
    }

    try {
      bridge.platform?.on?.(bridge.EVENT_NAME.AUDIO_STATE_CHANGED, (enabled) => {
        platformAudioEnabled = enabled !== false;
        if (platformAudioEnabled) resumeTrackedAudio(); else pauseTrackedAudio();
      });
    } catch (error) {
      console.warn('[Playgama] audio event subscription failed:', error);
    }

    // v2 storage automatically uses platform cloud storage when available and
    // falls back to local storage otherwise. No v1 storage-type argument is used.
    try {
      const markerKey = '__playgama_bridge_port_v2';
      await bridge.storage.get(markerKey).catch(() => undefined);
      await bridge.storage.set(markerKey, { version: 2, updatedAt: Date.now() });
    } catch (error) {
      console.info('[Playgama] storage unavailable; native/local persistence remains available.', error);
    }

    document.documentElement.dataset.playgamaBridge = 'ready';
    document.documentElement.dataset.playgamaBridgeVersion = String(bridge.version || '2');
    return bridge;
  };

  window.playgamaBridgeReady = initializeBridge().catch((error) => {
    document.documentElement.dataset.playgamaBridge = 'failed';
    console.warn('[Playgama] Bridge initialization failed:', error);
    return null;
  });

  const storageGet = async (bridge, key) => {
    try { return await bridge.storage.get(key); }
    catch (_) { return undefined; }
  };

  const storageSet = async (bridge, key, value) => {
    try {
      await bridge.storage.set(key, value);
      return true;
    } catch (_) {
      return false;
    }
  };

  const createPlayer = (bridge) => {
    if (pseudoPlayer) return pseudoPlayer;
    pseudoPlayer = {
      async getData(keys) {
        const requested = Array.isArray(keys) ? keys : (keys == null ? [] : [keys]);
        const result = {};
        for (const key of requested) {
          const value = await storageGet(bridge, String(key));
          if (value !== undefined && value !== null) result[key] = value;
        }
        return result;
      },
      async setData(data) {
        for (const [key, value] of Object.entries(data || {})) {
          const ok = await storageSet(bridge, String(key), value);
          if (!ok) throw new Error(`Could not persist Playgama storage key: ${key}`);
        }
      },
      getMode() { return 'full'; },
      getUniqueID() { return ''; },
      getName() { return ''; }
    };
    return pseudoPlayer;
  };

  const bindAdPause = (bridge, eventName, openedState, closedStates, reason) => {
    bridge.advertisement?.on?.(eventName, (state) => {
      if (state === openedState) setPauseReason(reason, true);
      else if (closedStates.includes(state)) setPauseReason(reason, false);
    });
  };

  const createFullscreenAd = (bridge) => (options = {}) => {
    const callbacks = options.callbacks || {};
    const advertisement = bridge.advertisement;
    if (!advertisement?.isInterstitialSupported) {
      safeCall(callbacks.onError, new Error('Interstitial advertising is not supported'));
      return;
    }

    const eventName = bridge.EVENT_NAME.INTERSTITIAL_STATE_CHANGED;
    const openedState = bridge.INTERSTITIAL_STATE.OPENED;
    const closedState = bridge.INTERSTITIAL_STATE.CLOSED;
    const failedState = bridge.INTERSTITIAL_STATE.FAILED;
    let opened = false;
    let finished = false;

    const cleanup = () => advertisement.off?.(eventName, listener);
    const listener = (state) => {
      if (finished) return;
      if (state === openedState) {
        opened = true;
        setPauseReason('interstitial', true);
        safeCall(callbacks.onOpen);
      } else if (state === closedState) {
        finished = true;
        setPauseReason('interstitial', false);
        cleanup();
        safeCall(callbacks.onClose, opened);
      } else if (state === failedState) {
        finished = true;
        setPauseReason('interstitial', false);
        cleanup();
        safeCall(callbacks.onError, new Error('Playgama interstitial failed'));
      }
    };

    advertisement.on?.(eventName, listener);
    try { advertisement.showInterstitial(options.placement || null); }
    catch (error) {
      finished = true;
      cleanup();
      setPauseReason('interstitial', false);
      safeCall(callbacks.onError, error);
    }
  };

  const createRewardedAd = (bridge) => (options = {}) => {
    const callbacks = options.callbacks || {};
    const advertisement = bridge.advertisement;
    if (!advertisement?.isRewardedSupported) {
      safeCall(callbacks.onError, new Error('Rewarded advertising is not supported'));
      return;
    }

    const eventName = bridge.EVENT_NAME.REWARDED_STATE_CHANGED;
    const openedState = bridge.REWARDED_STATE.OPENED;
    const rewardedState = bridge.REWARDED_STATE.REWARDED;
    const closedState = bridge.REWARDED_STATE.CLOSED;
    const failedState = bridge.REWARDED_STATE.FAILED;
    let rewarded = false;
    let finished = false;

    const cleanup = () => advertisement.off?.(eventName, listener);
    const listener = (state) => {
      if (finished) return;
      if (state === openedState) {
        setPauseReason('rewarded', true);
        safeCall(callbacks.onOpen);
      } else if (state === rewardedState) {
        rewarded = true;
        safeCall(callbacks.onRewarded);
      } else if (state === closedState) {
        finished = true;
        setPauseReason('rewarded', false);
        cleanup();
        safeCall(callbacks.onClose, rewarded);
      } else if (state === failedState) {
        finished = true;
        setPauseReason('rewarded', false);
        cleanup();
        safeCall(callbacks.onError, new Error('Playgama rewarded advertisement failed'));
      }
    };

    advertisement.on?.(eventName, listener);
    try { advertisement.showRewarded(options.placement || null); }
    catch (error) {
      finished = true;
      cleanup();
      setPauseReason('rewarded', false);
      safeCall(callbacks.onError, error);
    }
  };

  const sendPlatformMessage = async (bridge, message) => {
    try { await bridge.platform?.sendMessage?.(message); }
    catch (error) { console.info(`[Playgama] platform message ${message} was not accepted.`, error); }
  };

  const createSdk = (bridge) => {
    if (pseudoSdk) return pseudoSdk;
    const player = createPlayer(bridge);

    pseudoSdk = {
      environment: {
        i18n: { lang: normalizeLanguage(bridge.platform?.language) },
        app: { id: bridge.platform?.id || 'playgama' }
      },
      features: {
        LoadingAPI: {
          ready() {
            if (gameReadySent) return Promise.resolve(false);
            gameReadySent = true;
            return sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAME_READY || 'game_ready').then(() => true);
          }
        },
        GameplayAPI: {
          start() {
            if (gameplayStarted) return Promise.resolve(false);
            gameplayStarted = true;
            return sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAMEPLAY_STARTED || 'gameplay_started').then(() => true);
          },
          stop() {
            if (!gameplayStarted) return Promise.resolve(false);
            gameplayStarted = false;
            return sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAMEPLAY_STOPPED || 'gameplay_stopped').then(() => true);
          }
        }
      },
      adv: {
        showFullscreenAdv: createFullscreenAd(bridge),
        showRewardedVideo: createRewardedAd(bridge)
      },
      async getPlayer() { return player; },
      on(eventName, listener) {
        if (eventName === 'game_api_pause') pauseListeners.add(listener);
        else if (eventName === 'game_api_resume') resumeListeners.add(listener);
      },
      off(eventName, listener) {
        if (eventName === 'game_api_pause') pauseListeners.delete(listener);
        else if (eventName === 'game_api_resume') resumeListeners.delete(listener);
      },
      isAvailableMethod(methodName) {
        return Promise.resolve(new Set([
          'getPlayer',
          'adv.showFullscreenAdv',
          'adv.showRewardedVideo',
          'features.LoadingAPI.ready',
          'features.GameplayAPI.start',
          'features.GameplayAPI.stop'
        ]).has(String(methodName || '')));
      }
    };

    window.ysdk = pseudoSdk;
    window.playgamaYandexCompatSdk = pseudoSdk;
    return pseudoSdk;
  };

  window.YaGames = {
    init() {
      return window.playgamaBridgeReady.then((bridge) => {
        if (!bridge) throw new Error('Playgama Bridge initialization failed');
        return createSdk(bridge);
      });
    }
  };

  document.addEventListener('visibilitychange', () => {
    setPauseReason('document-hidden', document.hidden);
  });

  window.playgamaBridgeReady.then((bridge) => {
    if (!bridge) return;
    try {
      bindAdPause(
        bridge,
        bridge.EVENT_NAME.INTERSTITIAL_STATE_CHANGED,
        bridge.INTERSTITIAL_STATE.OPENED,
        [bridge.INTERSTITIAL_STATE.CLOSED, bridge.INTERSTITIAL_STATE.FAILED],
        'interstitial'
      );
      bindAdPause(
        bridge,
        bridge.EVENT_NAME.REWARDED_STATE_CHANGED,
        bridge.REWARDED_STATE.OPENED,
        [bridge.REWARDED_STATE.CLOSED, bridge.REWARDED_STATE.FAILED],
        'rewarded'
      );
    } catch (error) {
      console.warn('[Playgama] ad lifecycle subscription failed:', error);
    }
  });
})();
