from pathlib import Path

p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

# Cloud progress synchronization for Yandex Games. Pingus keeps its native
# savegames in IDBFS; this layer mirrors only progression files to Player data.
# Local saves remain the offline fallback. On startup, local and cloud level
# progress are merged monotonically so finishing a level on one device cannot
# erase progress made on another device.
cloud_anchor = '''      const fitCanvas = () => {'''
cloud_code = r'''      const PINGUS_CLOUD_KEY = 'pingusCloudSaveV1';
      const PINGUS_CLOUD_VERSION = 1;
      const PINGUS_SAVE_PATH = '/home/web_user/.pingus/savegames/savegames.scm';
      const PINGUS_STATS_PATH = '/home/web_user/.pingus/savegames/variables.scm';
      const PINGUS_CLOUD_MAX_CHARS = 180000;
      let pingusPlayerPromise = null;
      let pingusCloudRestoreFinished = false;
      let pingusCloudSaveInProgress = false;
      let pingusCloudSaveRequestedAgain = false;
      let pingusLastCloudFingerprint = '';

      const cloudTimeout = (promise, timeoutMs) => Promise.race([
        promise,
        new Promise((_, reject) => window.setTimeout(
          () => reject(new Error('Yandex cloud operation timed out')),
          timeoutMs
        ))
      ]);

      const ensureFsDir = (path) => {
        try { FS.mkdir(path); } catch (_) {}
      };

      const readTextFile = (path) => {
        try { return FS.readFile(path, { encoding: 'utf8' }); } catch (_) { return ''; }
      };

      const fileModifiedAt = (path) => {
        try {
          const value = FS.stat(path)?.mtime;
          if (value instanceof Date) return value.getTime();
          const number = Number(value || 0);
          return Number.isFinite(number) ? number : 0;
        } catch (_) {
          return 0;
        }
      };

      const hashText = (value) => {
        // FNV-1a is sufficient here: this is only a change detector, not security.
        let hash = 0x811c9dc5;
        const textValue = String(value || '');
        for (let i = 0; i < textValue.length; ++i) {
          hash ^= textValue.charCodeAt(i);
          hash = Math.imul(hash, 0x01000193);
        }
        return (hash >>> 0).toString(16).padStart(8, '0');
      };

      const snapshotFingerprint = (snapshot) =>
        `${hashText(snapshot?.savegames)}:${hashText(snapshot?.stats)}`;

      const validSavegames = (value) =>
        typeof value === 'string' && value.length <= PINGUS_CLOUD_MAX_CHARS &&
        value.includes('(pingus-savegame');

      const validStats = (value) =>
        typeof value === 'string' && value.length <= PINGUS_CLOUD_MAX_CHARS &&
        value.includes('(pingus-stats');

      const readLocalProgress = () => {
        const savegames = readTextFile(PINGUS_SAVE_PATH);
        const stats = readTextFile(PINGUS_STATS_PATH);
        return {
          version: PINGUS_CLOUD_VERSION,
          updatedAt: Math.max(fileModifiedAt(PINGUS_SAVE_PATH), fileModifiedAt(PINGUS_STATS_PATH)),
          savegames: validSavegames(savegames) ? savegames : '',
          stats: validStats(stats) ? stats : ''
        };
      };

      const normalizeCloudProgress = (value) => {
        if (!value || typeof value !== 'object' || value.version !== PINGUS_CLOUD_VERSION)
          return null;
        const savegames = validSavegames(value.savegames) ? value.savegames : '';
        const stats = validStats(value.stats) ? value.stats : '';
        if (!savegames && !stats) return null;
        const updatedAt = Number(value.updatedAt || 0);
        return {
          version: PINGUS_CLOUD_VERSION,
          updatedAt: Number.isFinite(updatedAt) ? updatedAt : 0,
          savegames,
          stats
        };
      };

      const extractLevelBlocks = (source) => {
        const blocks = [];
        let cursor = 0;
        while (cursor < source.length) {
          const start = source.indexOf('(level', cursor);
          if (start < 0) break;
          const boundary = source[start + 6];
          if (boundary && !/\s|\)/.test(boundary)) {
            cursor = start + 6;
            continue;
          }

          let depth = 0;
          let inString = false;
          let escaped = false;
          let end = -1;
          for (let i = start; i < source.length; ++i) {
            const ch = source[i];
            if (inString) {
              if (escaped) escaped = false;
              else if (ch === '\\') escaped = true;
              else if (ch === '"') inString = false;
              continue;
            }
            if (ch === '"') inString = true;
            else if (ch === '(') ++depth;
            else if (ch === ')') {
              --depth;
              if (depth === 0) {
                end = i + 1;
                break;
              }
            }
          }
          if (end < 0) return null;
          blocks.push(source.slice(start, end));
          cursor = end;
        }
        return blocks;
      };

      const parseLevelBlock = (block, sourceName, sourceUpdatedAt) => {
        const filename = /\(filename\s+"((?:\\.|[^"\\])*)"\)/.exec(block)?.[1];
        const status = /\(status\s+([^\s\)]+)\)/.exec(block)?.[1]?.toLowerCase();
        if (!filename || !status) return null;
        const time = Number(/\(time\s+(-?\d+)\)/.exec(block)?.[1] || 0);
        const saved = Number(/\(saved-pingus\s+(-?\d+)\)/.exec(block)?.[1] || 0);
        return { block, filename, status, time, saved, sourceName, sourceUpdatedAt };
      };

      const levelRank = (level) => {
        if (level.status === 'finished') return 2;
        if (level.status === 'accessible') return 1;
        return 0;
      };

      const chooseLevelProgress = (left, right) => {
        const leftRank = levelRank(left);
        const rightRank = levelRank(right);
        if (leftRank !== rightRank) return leftRank > rightRank ? left : right;
        if (leftRank === 2) {
          if (left.saved !== right.saved) return left.saved > right.saved ? left : right;
          const leftTime = left.time > 0 ? left.time : Number.MAX_SAFE_INTEGER;
          const rightTime = right.time > 0 ? right.time : Number.MAX_SAFE_INTEGER;
          if (leftTime !== rightTime) return leftTime < rightTime ? left : right;
        }
        return left.sourceUpdatedAt >= right.sourceUpdatedAt ? left : right;
      };

      const mergeSavegames = (localText, cloudText, localUpdatedAt, cloudUpdatedAt) => {
        if (!validSavegames(localText)) return validSavegames(cloudText) ? cloudText : '';
        if (!validSavegames(cloudText)) return localText;

        const localBlocks = extractLevelBlocks(localText);
        const cloudBlocks = extractLevelBlocks(cloudText);
        if (!localBlocks || !cloudBlocks)
          return cloudUpdatedAt > localUpdatedAt ? cloudText : localText;

        const merged = new Map();
        const addBlocks = (blocks, sourceName, updatedAt) => {
          for (const block of blocks) {
            const parsed = parseLevelBlock(block, sourceName, updatedAt);
            if (!parsed) return false;
            const existing = merged.get(parsed.filename);
            merged.set(parsed.filename, existing ? chooseLevelProgress(existing, parsed) : parsed);
          }
          return true;
        };
        if (!addBlocks(localBlocks, 'local', localUpdatedAt) ||
            !addBlocks(cloudBlocks, 'cloud', cloudUpdatedAt))
          return cloudUpdatedAt > localUpdatedAt ? cloudText : localText;

        if (!merged.size)
          return cloudUpdatedAt > localUpdatedAt ? cloudText : localText;

        return '(pingus-savegame \n' +
          Array.from(merged.values(), (entry) => '  ' + entry.block).join('\n') +
          '\n)';
      };

      const mergeProgress = (local, cloud) => {
        if (!cloud) return local;
        const savegames = mergeSavegames(
          local.savegames,
          cloud.savegames,
          local.updatedAt,
          cloud.updatedAt
        );
        let stats = local.stats;
        if (!stats || (cloud.stats && cloud.updatedAt > local.updatedAt)) stats = cloud.stats;
        return {
          version: PINGUS_CLOUD_VERSION,
          updatedAt: Math.max(local.updatedAt || 0, cloud.updatedAt || 0),
          savegames,
          stats
        };
      };

      const writeLocalProgress = (snapshot) => {
        ensureFsDir('/home/web_user/.pingus');
        ensureFsDir('/home/web_user/.pingus/savegames');
        if (validSavegames(snapshot?.savegames) && readTextFile(PINGUS_SAVE_PATH) !== snapshot.savegames)
          FS.writeFile(PINGUS_SAVE_PATH, snapshot.savegames, { encoding: 'utf8' });
        if (validStats(snapshot?.stats) && readTextFile(PINGUS_STATS_PATH) !== snapshot.stats)
          FS.writeFile(PINGUS_STATS_PATH, snapshot.stats, { encoding: 'utf8' });
      };

      const getYandexPlayer = () => {
        if (pingusPlayerPromise) return pingusPlayerPromise;
        pingusPlayerPromise = (async () => {
          const ysdk = await window.yandexSDKPromise;
          if (typeof ysdk?.getPlayer !== 'function') return null;
          try {
            return await ysdk.getPlayer();
          } catch (error) {
            console.warn('Yandex Player initialization failed:', error);
            return null;
          }
        })();
        return pingusPlayerPromise;
      };

      const setCloudProgress = async (player, snapshot) => {
        if (!player || typeof player.setData !== 'function') return false;
        const payload = {
          version: PINGUS_CLOUD_VERSION,
          updatedAt: Date.now(),
          savegames: validSavegames(snapshot.savegames) ? snapshot.savegames : '',
          stats: validStats(snapshot.stats) ? snapshot.stats : ''
        };
        if (!payload.savegames && !payload.stats) return false;
        if (JSON.stringify(payload).length > PINGUS_CLOUD_MAX_CHARS) {
          console.warn('Pingus cloud save skipped: payload is too large');
          return false;
        }
        await player.setData({ [PINGUS_CLOUD_KEY]: payload }, true);
        pingusLastCloudFingerprint = snapshotFingerprint(payload);
        return true;
      };

      window.pingusRestoreCloudSave = async () => {
        if (pingusCloudRestoreFinished) return;
        try {
          const player = await cloudTimeout(getYandexPlayer(), 6000);
          if (!player || typeof player.getData !== 'function') return;

          const data = await cloudTimeout(player.getData([PINGUS_CLOUD_KEY]), 6000);
          const cloud = normalizeCloudProgress(data?.[PINGUS_CLOUD_KEY]);
          const local = readLocalProgress();
          const merged = mergeProgress(local, cloud);
          writeLocalProgress(merged);

          const mergedFingerprint = snapshotFingerprint(merged);
          pingusLastCloudFingerprint = cloud ? snapshotFingerprint(cloud) : '';
          if (mergedFingerprint !== pingusLastCloudFingerprint)
            await cloudTimeout(setCloudProgress(player, merged), 6000);

          document.documentElement.dataset.pingusCloud = 'ready';
        } catch (error) {
          // Cloud is an enhancement; local IDBFS remains authoritative offline.
          console.warn('Yandex cloud save restore failed; using local progress:', error);
          document.documentElement.dataset.pingusCloud = 'local';
        } finally {
          pingusCloudRestoreFinished = true;
        }
      };

      window.pingusCloudSave = async () => {
        if (!pingusCloudRestoreFinished) return;
        if (pingusCloudSaveInProgress) {
          pingusCloudSaveRequestedAgain = true;
          return;
        }

        const snapshot = readLocalProgress();
        const fingerprint = snapshotFingerprint(snapshot);
        if ((!snapshot.savegames && !snapshot.stats) || fingerprint === pingusLastCloudFingerprint)
          return;

        pingusCloudSaveInProgress = true;
        try {
          const player = await cloudTimeout(getYandexPlayer(), 6000);
          if (player) await cloudTimeout(setCloudProgress(player, snapshot), 6000);
        } catch (error) {
          console.warn('Yandex cloud save failed; local progress is safe:', error);
        } finally {
          pingusCloudSaveInProgress = false;
          if (pingusCloudSaveRequestedAgain) {
            pingusCloudSaveRequestedAgain = false;
            window.pingusCloudSave();
          }
        }
      };

'''
if s.count(cloud_anchor) != 1:
    raise SystemExit('cloud save insertion anchor missing or duplicated')
s = s.replace(cloud_anchor, cloud_code + cloud_anchor, 1)

old_save = r'''      window.pingusSaveNow = () => {
        if (typeof FS === 'undefined' || typeof FS.syncfs !== 'function') return;
        if (saveInProgress) {
          saveRequestedAgain = true;
          return;
        }
        saveInProgress = true;
        FS.syncfs(false, (error) => {
          saveInProgress = false;
          if (error) console.warn('Pingus save synchronization failed:', error);
          if (saveRequestedAgain) {
            saveRequestedAgain = false;
            window.pingusSaveNow();
          }
        });
      };'''
new_save = r'''      window.pingusSaveNow = () => {
        if (typeof FS === 'undefined' || typeof FS.syncfs !== 'function') return;
        if (saveInProgress) {
          saveRequestedAgain = true;
          return;
        }
        saveInProgress = true;
        FS.syncfs(false, (error) => {
          saveInProgress = false;
          if (error) console.warn('Pingus save synchronization failed:', error);
          else window.pingusCloudSave?.();
          if (saveRequestedAgain) {
            saveRequestedAgain = false;
            window.pingusSaveNow();
          }
        });
      };'''
if s.count(old_save) != 1:
    raise SystemExit('cloud save local sync anchor missing or duplicated')
s = s.replace(old_save, new_save, 1)

old_restore = r'''          addRunDependency('pingus-idbfs');
          try {
            FS.mount(IDBFS, {}, '/home/web_user');
            FS.syncfs(true, (error) => {
              if (error) console.warn('Pingus save restore failed:', error);
              removeRunDependency('pingus-idbfs');
            });
          } catch (error) {
            console.warn('IDBFS unavailable:', error);
            removeRunDependency('pingus-idbfs');
          }'''
new_restore = r'''          addRunDependency('pingus-idbfs');
          try {
            FS.mount(IDBFS, {}, '/home/web_user');
            FS.syncfs(true, (error) => {
              if (error) console.warn('Pingus save restore failed:', error);
              (async () => {
                await window.pingusRestoreCloudSave?.();
                await new Promise((resolve) => {
                  FS.syncfs(false, (syncError) => {
                    if (syncError) console.warn('Pingus cloud restore local flush failed:', syncError);
                    resolve();
                  });
                });
              })().catch((cloudError) => {
                console.warn('Pingus cloud startup synchronization failed:', cloudError);
              }).finally(() => removeRunDependency('pingus-idbfs'));
            });
          } catch (error) {
            console.warn('IDBFS unavailable:', error);
            // The game can still run without browser persistence. Cloud restore
            // is skipped because there is no safe local filesystem mount.
            pingusCloudRestoreFinished = true;
            removeRunDependency('pingus-idbfs');
          }'''
if s.count(old_restore) != 1:
    raise SystemExit('cloud save startup restore anchor missing or duplicated')
s = s.replace(old_restore, new_restore, 1)

p.write_text(s, encoding='utf-8')
print('Yandex cloud saves: Player.getData/setData + IDBFS merge/fallback enabled')
