(() => {
  'use strict';
  const frame = document.getElementById('lead-frame');
  const ticket = JSON.parse(document.getElementById('ticket').textContent);
  const status = document.getElementById('submission-status');
  let pending = false;
  let complete = false;
  window.addEventListener('message', async (event) => {
    if (event.source !== frame.contentWindow || event.origin !== 'null') return;
    const message = event.data;
    if (!message || message.type !== 'crm-submit' || !message.data ||
        typeof message.data !== 'object' || Array.isArray(message.data)) return;
    if (pending || complete) return;
    pending = true;
    status.textContent = 'Submitting your application…';
    try {
      const response = await fetch('/api/public/submit/', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ticket, data: message.data})
      });
      const result = await response.json();
      if (!response.ok) {
        status.textContent = 'Unable to submit your application: ' + JSON.stringify(result.errors || result.detail || result);
        return;
      }
      complete = true;
      frame.hidden = true;
      document.getElementById('success').hidden = false;
      status.textContent = '';
    } catch (_) {
      status.textContent = 'Connection error. Please try submitting again.';
    } finally {
      pending = false;
    }
  });
})();
