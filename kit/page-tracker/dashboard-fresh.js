// When the daily run (or any run) writes new data, offer a reload; checks every 5 minutes and when the tab comes back.
(() => {
  let first = null;
  const check = () => fetch('data.json?' + Date.now(), { method: 'GET' }).then(r => r.json()).then(d => {
    if (first === null) { first = d.built; return; }
    if (d.built !== first && !document.getElementById('fresh')) {
      const b = document.createElement('div'); b.id = 'fresh'; b.className = 'fresh'; b.setAttribute('role', 'status');
      b.innerHTML = 'New data is in. <button type="button">Reload</button>';
      b.querySelector('button').onclick = () => location.reload();
      document.body.appendChild(b);
    }
  }).catch(() => {});
  check(); setInterval(check, 300000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
})();
