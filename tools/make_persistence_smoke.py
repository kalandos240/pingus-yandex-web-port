from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit('usage: make_persistence_smoke.py INPUT_HTML OUTPUT_HTML')

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
html = src.read_text(encoding='utf-8')
marker = '  <script src="pingus.js"></script>'
if html.count(marker) != 1:
    raise SystemExit('pingus.js script marker missing or duplicated')

harness = r'''  <script>
    (() => {
      if (new URLSearchParams(location.search).get('pingus-persistence-smoke') !== '1') return;

      const statsPath = '/home/web_user/.pingus/savegames/variables.scm';
      const phaseKey = 'pingus-persistence-smoke-phase';
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const signal = (kind, detail = '') => {
        const suffix = detail ? `?detail=${encodeURIComponent(String(detail).slice(0, 400))}` : '';
        fetch(`/__pingus_persist_${kind}__${suffix}`, { cache: 'no-store' }).catch(() => {});
      };
      const readStats = () => {
        try { return FS.readFile(statsPath, { encoding: 'utf8' }); }
        catch (_) { return ''; }
      };
      const syncToIDB = () => new Promise((resolve, reject) => {
        FS.syncfs(false, (error) => error ? reject(error) : resolve());
      });
      const clickLogical = (logicalX, logicalY) => {
        const rect = canvas.getBoundingClientRect();
        const x = rect.left + logicalX * rect.width / Math.max(1, canvas.width);
        const y = rect.top + logicalY * rect.height / Math.max(1, canvas.height);
        const base = { bubbles: true, cancelable: true, clientX: x, clientY: y, view: window };
        canvas.dispatchEvent(new MouseEvent('mousemove', { ...base, button: 0, buttons: 0 }));
        canvas.dispatchEvent(new MouseEvent('mousedown', { ...base, button: 0, buttons: 1 }));
        canvas.dispatchEvent(new MouseEvent('mouseup', { ...base, button: 0, buttons: 0 }));
      };

      const originalReady = window.pingusMarkReady;
      if (typeof originalReady !== 'function') {
        signal('error', 'pingusMarkReady missing');
        return;
      }

      window.pingusMarkReady = async (...args) => {
        await originalReady(...args);
        await sleep(250);

        try {
          const phase = sessionStorage.getItem(phaseKey) || 'first';
          const initialStats = readStats();

          if (phase === 'restore') {
            if (!initialStats.includes('tutorial-startstory-seen')) {
              signal('error', `restore missing stat: ${initialStats}`);
              return;
            }
            sessionStorage.removeItem(phaseKey);
            signal('success', initialStats);
            return;
          }

          if (initialStats.includes('tutorial-startstory-seen')) {
            signal('error', `fresh profile already contained stat: ${initialStats}`);
            return;
          }

          // Story is centered at logical (400, 280) in the original 800x600 menu.
          // Clicking it makes Pingus' own StatManager write tutorial-startstory-seen.
          clickLogical(400, 280);

          let generatedStats = '';
          for (let i = 0; i < 60; ++i) {
            generatedStats = readStats();
            if (generatedStats.includes('tutorial-startstory-seen')) break;
            await sleep(100);
          }
          if (!generatedStats.includes('tutorial-startstory-seen')) {
            signal('error', `Pingus did not generate tutorial stat: ${generatedStats}`);
            return;
          }

          sessionStorage.setItem(phaseKey, 'restore');
          await syncToIDB();
          location.reload();
        } catch (error) {
          signal('error', error?.stack || error);
        }
      };
    })();
  </script>
'''

html = html.replace(marker, harness + marker, 1)
dst.write_text(html, encoding='utf-8')
