/* ═══════════════════════════════════════════════════════════
   poll.js — polling loop for /status/<job_id> page
   Expects JOB_ID to be set as a global by the template.
   ═══════════════════════════════════════════════════════════ */

(function initPoller() {
    if (typeof JOB_ID === 'undefined') return;

    const INTERVAL_MS = 2500;
    const MAX_POLLS   = 120;       // give up after ~5 min
    let   pollCount   = 0;
    let   progress    = 20;        // synthetic progress % (20 → 90)

    const statusText  = document.getElementById('poll-status-text');
    const progressBar = document.getElementById('poll-progress-bar');
    const errorBox    = document.getElementById('poll-error');
    const errorMsg    = document.getElementById('poll-error-msg');

    const steps = [
        document.getElementById('poll-step-upload'),
        document.getElementById('poll-step-ocr'),
        document.getElementById('poll-step-extract'),
        document.getElementById('poll-step-validate'),
    ];

    function setStep(idx) {
        steps.forEach((s, i) => {
            if (!s) return;
            s.classList.remove('active', 'done');
            if (i < idx)  s.classList.add('done');
            if (i === idx) s.classList.add('active');
        });
    }

    function advanceProgress() {
        progress = Math.min(progress + 8, 90);
        if (progressBar) progressBar.style.width = progress + '%';
    }

    function showError(msg) {
        if (errorBox) errorBox.classList.remove('hidden');
        if (errorMsg) errorMsg.textContent = msg || 'Processing failed. Please try again.';
        if (statusText) statusText.textContent = 'Error encountered.';
    }

    async function poll() {
        pollCount++;
        if (pollCount > MAX_POLLS) {
            showError('Processing timed out. Please try again.');
            return;
        }

        try {
            const res  = await fetch(`/api/result/${JOB_ID}`);
            const json = await res.json();

            if (json.status === 'pending') {
                setStep(1);
                if (statusText) statusText.textContent = 'Job queued — waiting for worker…';
                advanceProgress();
                setTimeout(poll, INTERVAL_MS);

            } else if (json.status === 'processing') {
                // Cycle through steps visually
                const stepIdx = Math.min(1 + Math.floor(pollCount / 4), 3);
                setStep(stepIdx);
                const msgs = [
                    'Running OCR pipeline…',
                    'Extracting document fields…',
                    'Computing validation score & fraud check…',
                ];
                if (statusText) statusText.textContent = msgs[stepIdx - 1] || 'Processing…';
                advanceProgress();
                setTimeout(poll, INTERVAL_MS);

            } else if (json.status === 'done') {
                // Finish all steps
                steps.forEach(s => { if (s) { s.classList.remove('active'); s.classList.add('done'); } });
                if (progressBar) progressBar.style.width = '100%';
                if (statusText) statusText.textContent = 'Complete! Redirecting…';
                // Navigate to rendered result page
                setTimeout(() => { window.location.href = `/result/${JOB_ID}`; }, 600);

            } else if (json.status === 'error') {
                showError(json.error || 'An unknown error occurred during processing.');

            } else {
                showError('Unexpected response from server.');
            }

        } catch (err) {
            console.error('Poll error:', err);
            // Retry silently up to 5 times on network error
            if (pollCount < 5) setTimeout(poll, INTERVAL_MS * 2);
            else showError('Network error — unable to reach server.');
        }
    }

    // Start first poll after short delay
    setTimeout(poll, 1500);
})();
