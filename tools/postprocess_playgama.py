from pathlib import Path
import json

D=Path('../dist'); I=D/'index.html'; B=D/'bootstrap.js'; C=Path('../web/playgama-bridge-config.json')

def between(s,a,b,r):
    i=s.index(a); j=s.index(b,i); return s[:i]+r+s[j:]

x=I.read_text('utf-8')
a='<script src="/sdk.js"></script>'
b='<script src="https://bridge.playgama.com/v1/stable/playgama-bridge.js"></script>'
if x.count(a)!=1: raise SystemExit('Playgama SDK tag anchor mismatch')
I.write_text(x.replace(a,b,1),'utf-8')

s=B.read_text('utf-8')
s=s.replace('const INTERSTITIAL_MIN_INTERVAL_MS = 90000;','const INTERSTITIAL_MIN_INTERVAL_MS = 60000;',1)
s=s.replace('      let lastInterstitialAt = performance.now();\n','',1)
s=s.replace('      let platformPaused = false;\n','      let platformPaused = false;\n      let platformAudioEnabled = true;\n',1)
s=s.replace("Yandex cloud operation timed out","Playgama storage operation timed out")

ads=r'''      window.pingusShowInterstitialAfterResultAction = () => {
        if (interstitialInProgress) return;
        interstitialInProgress = true;
        (async () => {
          const pg = await window.playgamaBridgePromise;
          const a = pg?.advertisement;
          if (!a?.isInterstitialSupported || typeof a.showInterstitial !== 'function') return;
          window.pingusSaveNow?.();
          await a.showInterstitial('level_complete');
        })().catch(e => console.warn('Playgama interstitial failed:', e))
          .finally(() => { interstitialInProgress = false; });
      };

'''
s=between(s,'      // Called only after the player explicitly clicks a result-screen action.','      let gameplayDesiredActive = false;',ads)

gameplay=r'''      let gameplayDesiredActive = false;
      let gameplayStateInitialized = false;
      let gameplaySyncVersion = 0;
      window.pingusSetGameplayActive = active => {
        const desired = Boolean(active);
        if (gameplayStateInitialized && gameplayDesiredActive === desired) return;
        gameplayStateInitialized = true;
        gameplayDesiredActive = desired;
        const version = ++gameplaySyncVersion;
        (async () => {
          const pg = await window.playgamaBridgePromise;
          if (!pg || version !== gameplaySyncVersion) return;
          await pg.platform?.sendMessage?.(gameplayDesiredActive ? 'gameplay_started' : 'gameplay_stopped');
        })().catch(e => console.warn('Playgama gameplay message failed:', e));
      };

'''
s=between(s,'      let gameplayDesiredActive = false;','      window.yandexSDKPromise = (async () => {',gameplay)

sdk=r'''      window.playgamaBridgePromise = (async () => {
        try {
          if (typeof bridge === 'undefined') throw new Error('Playgama Bridge unavailable');
          await bridge.initialize();
          const pg = bridge;
          window.playgamaBridge = pg;
          applyLanguage(pg.platform?.language || navigator.language);
          pg.advertisement?.setMinimumDelayBetweenInterstitial?.(INTERSTITIAL_MIN_INTERVAL_MS / 1000);
          platformAudioEnabled = pg.platform?.isAudioEnabled !== false;
          const syncAudio = () => setAudioPaused(window.pingusPagePaused() || !platformAudioEnabled);
          pg.platform?.on?.(pg.EVENT_NAME.AUDIO_STATE_CHANGED, v => { platformAudioEnabled=Boolean(v); syncAudio(); });
          pg.platform?.on?.(pg.EVENT_NAME.PAUSE_STATE_CHANGED, v => { window.pingusSetPlatformPaused(Boolean(v)); if(v) window.pingusSaveNow?.(); });
          const adState = st => {
            if (st === 'opened') { window.pingusSetPlatformPaused(true); window.pingusSaveNow?.(); }
            else if (st === 'closed' || st === 'failed') window.pingusSetPlatformPaused(false);
          };
          pg.advertisement?.on?.(pg.EVENT_NAME.INTERSTITIAL_STATE_CHANGED, adState);
          adState(pg.advertisement?.interstitialState);
          syncAudio();
          return pg;
        } catch (e) {
          console.warn('Playgama Bridge initialization failed:', e);
          applyLanguage(navigator.language);
          return null;
        }
      })();

'''
s=between(s,'      window.yandexSDKPromise = (async () => {','      const PINGUS_CLOUD_KEY =',sdk)

storage=r'''      const getPlaygamaBridge = () => window.playgamaBridgePromise;
      const decodeBridgeProgress = raw => {
        let v = raw;
        if (v && typeof v === 'object' && PINGUS_CLOUD_KEY in v) v = v[PINGUS_CLOUD_KEY];
        if (typeof v === 'string') { try { v=JSON.parse(v); } catch (_) { return null; } }
        return normalizeCloudProgress(v);
      };
      const setCloudProgress = async (pg, snap) => {
        if (!pg?.storage?.set) return false;
        const p={version:PINGUS_CLOUD_VERSION,updatedAt:Date.now(),savegames:validSavegames(snap.savegames)?snap.savegames:'',stats:validStats(snap.stats)?snap.stats:''};
        if (!p.savegames && !p.stats) return false;
        const v=JSON.stringify(p); if(v.length>PINGUS_CLOUD_MAX_CHARS) return false;
        await pg.storage.set(PINGUS_CLOUD_KEY,v); pingusLastCloudFingerprint=snapshotFingerprint(p); return true;
      };
      window.pingusRestoreCloudSave = async () => {
        if (pingusCloudRestoreFinished) return;
        try {
          const pg=await cloudTimeout(getPlaygamaBridge(),8000); if(!pg?.storage?.get) return;
          const cloud=decodeBridgeProgress(await cloudTimeout(pg.storage.get(PINGUS_CLOUD_KEY),8000));
          const local=readLocalProgress(), merged=mergeProgress(local,cloud); writeLocalProgress(merged);
          pingusLastCloudFingerprint=cloud?snapshotFingerprint(cloud):'';
          if(snapshotFingerprint(merged)!==pingusLastCloudFingerprint) await cloudTimeout(setCloudProgress(pg,merged),8000);
          document.documentElement.dataset.pingusCloud='ready';
        } catch(e) { console.warn('Playgama save restore failed:',e); document.documentElement.dataset.pingusCloud='local'; }
        finally { pingusCloudRestoreFinished=true; }
      };
      window.pingusCloudSave = async () => {
        if(!pingusCloudRestoreFinished) return;
        if(pingusCloudSaveInProgress){pingusCloudSaveRequestedAgain=true;return;}
        const snap=readLocalProgress(), fp=snapshotFingerprint(snap);
        if((!snap.savegames&&!snap.stats)||fp===pingusLastCloudFingerprint)return;
        pingusCloudSaveInProgress=true;
        try{const pg=await cloudTimeout(getPlaygamaBridge(),8000);if(pg)await cloudTimeout(setCloudProgress(pg,snap),8000);}
        catch(e){console.warn('Playgama save failed:',e);}
        finally{pingusCloudSaveInProgress=false;if(pingusCloudSaveRequestedAgain){pingusCloudSaveRequestedAgain=false;window.pingusCloudSave();}}
      };

'''
s=between(s,'      const getYandexPlayer = () => {','      const fitCanvas = () => {',storage)

ready=r'''      window.pingusMarkReady = async () => {
        if (gameReadySent) return;
        gameReadySent = true;
        document.documentElement.dataset.pingusReady = '1';
        pingusSmokeSignal('ready'); fitCanvas(); loading.hidden=true; canvas.focus({preventScroll:true});
        if (!autosaveTimer) autosaveTimer=window.setInterval(window.pingusSaveNow,15000);
        try { const pg=await window.playgamaBridgePromise; await pg?.platform?.sendMessage?.('game_ready'); }
        catch(e){console.warn('Playgama game_ready failed:',e);}
      };

'''
s=between(s,'      window.pingusMarkReady = async () => {','      const syncPagePause = () => {',ready)
s=s.replace('window.yandexSDKPromise','window.playgamaBridgePromise')
s=s.replace('language selected by Yandex (or navigator fallback)','language selected by Playgama Bridge (or navigator fallback)')
s=s.replace('setAudioPaused(window.pingusPagePaused());','setAudioPaused(window.pingusPagePaused() || !platformAudioEnabled);')
s=s.replace('        setAudioPaused(paused);','        setAudioPaused(paused || !platformAudioEnabled);')
for q in ('YaGames','showFullscreenAdv','window.yandexSDKPromise'):
    if q in s: raise SystemExit('Yandex runtime remains: '+q)
for q in ('bridge.initialize()',"sendMessage?.('game_ready')",'pg.storage.get(PINGUS_CLOUD_KEY)','pg.storage.set(PINGUS_CLOUD_KEY,v)',"showInterstitial('level_complete')",'pg.EVENT_NAME.AUDIO_STATE_CHANGED','pg.EVENT_NAME.PAUSE_STATE_CHANGED','pg.EVENT_NAME.INTERSTITIAL_STATE_CHANGED'):
    if q not in s: raise SystemExit('Playgama marker missing: '+q)
B.write_text(s,'utf-8')
conf=json.loads(C.read_text('utf-8'))
if conf.get('advertisement',{}).get('minimumDelayBetweenInterstitial')!=60000: raise SystemExit('Playgama config delay mismatch')
(D/'playgama-bridge-config.json').write_text(json.dumps(conf,indent=2)+'\n','utf-8')
print('Playgama Bridge integration installed')
