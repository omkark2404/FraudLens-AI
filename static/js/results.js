/* ═══════════════════════════════════════════════════════════
   results.js — result page: score circle animations
   ═══════════════════════════════════════════════════════════ */

(function animateScores() {
    const CIRCUMFERENCE = 2 * Math.PI * 42;  // r=42 → ~263.9

    function animateCircle(fillId, numId, targetScore) {
        const fillEl = document.getElementById(fillId);
        const numEl  = document.getElementById(numId);
        if (!fillEl || !numEl) return;

        const target = Math.min(Math.max(parseInt(targetScore) || 0, 0), 100);
        const targetDash = (target / 100) * CIRCUMFERENCE;

        let current = 0;
        const duration = 1200;
        const start = performance.now();

        function step(now) {
            const elapsed = now - start;
            const t = Math.min(elapsed / duration, 1);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - t, 3);
            const val = Math.round(eased * target);
            current = eased * targetDash;

            fillEl.setAttribute('stroke-dasharray', `${current} ${CIRCUMFERENCE}`);
            numEl.textContent = val;

            if (t < 1) requestAnimationFrame(step);
        }

        requestAnimationFrame(step);
    }

    // Find all score circles on the page and animate them
    document.querySelectorAll('.score-circle').forEach(circle => {
        const score = circle.dataset.score || '0';
        const fillId = circle.querySelector('.score-fill')?.id;
        const numId  = circle.querySelector('.score-number')?.id;
        if (fillId && numId) animateCircle(fillId, numId, score);
    });

    // Card entrance animation (staggered)
    document.querySelectorAll('.info-card, .doc-section').forEach((el, i) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(24px)';
        el.style.transition = `opacity 0.5s ease ${i * 80}ms, transform 0.5s ease ${i * 80}ms`;
        requestAnimationFrame(() => {
            el.style.opacity = '1';
            el.style.transform = '';
        });
    });
})();
