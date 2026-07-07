/* ═══════════════════════════════════════════════════════════
   script.js — shared UI utilities (all pages)
   ═══════════════════════════════════════════════════════════ */

// ── Particle background ──────────────────────────────────────
(function initParticles() {
    const bg = document.getElementById('particles-bg');
    if (!bg) return;
    const canvas = document.createElement('canvas');
    const ctx    = canvas.getContext('2d');
    bg.appendChild(canvas);

    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const COLORS = ['#3a86ff', '#8338ec', '#06d6a0', '#f59e0b'];
    const count  = Math.min(Math.floor(window.innerWidth / 18), 80);
    const pts    = Array.from({length: count}, () => ({
        x:     Math.random() * canvas.width,
        y:     Math.random() * canvas.height,
        r:     Math.random() * 2 + 1,
        dx:    (Math.random() - 0.5) * 0.55,
        dy:    (Math.random() - 0.5) * 0.55,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        alpha: Math.random() * 0.5 + 0.2,
    }));

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        pts.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = p.color + Math.round(p.alpha * 255).toString(16).padStart(2,'0');
            ctx.shadowColor = p.color;
            ctx.shadowBlur  = 6;
            ctx.fill();
            p.x += p.dx;
            p.y += p.dy;
            if (p.x < 0 || p.x > canvas.width)  p.dx *= -1;
            if (p.y < 0 || p.y > canvas.height) p.dy *= -1;
        });
        requestAnimationFrame(draw);
    }
    draw();
})();

// ── Page fade-in ─────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.5s ease';
    requestAnimationFrame(() => { document.body.style.opacity = '1'; });
});

// ── 3-D tilt on cards ────────────────────────────────────────
function add3DTilt(selector) {
    document.querySelectorAll(selector).forEach(card => {
        card.addEventListener('mousemove', e => {
            const r = card.getBoundingClientRect();
            const dx = ((e.clientX - r.left) / r.width  - 0.5) * 10;
            const dy = ((e.clientY - r.top)  / r.height - 0.5) * 10;
            card.style.transform = `perspective(900px) rotateX(${-dy}deg) rotateY(${dx}deg) translateY(-4px)`;
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
}
add3DTilt('.glass-card');
add3DTilt('.upload-3d-card');
add3DTilt('.info-card');

// ── File input: drag-drop + label update ──────────────────────
function setupFileZone(cardId, inputId) {
    const card  = document.getElementById(cardId);
    const input = document.getElementById(inputId);
    if (!card || !input) return;

    const label = input.nextElementSibling;

    function updateLabel(file) {
        label.innerHTML = `<i class="fas fa-check-circle"></i><span>${file.name}</span>`;
        label.style.background = 'linear-gradient(135deg,#22c55e,#16a34a)';
        const bar = card.querySelector('.progress-bar');
        if (bar) bar.style.width = '100%';
    }

    input.addEventListener('change', function() {
        if (this.files[0]) updateLabel(this.files[0]);
    });

    card.addEventListener('dragover',  e => { e.preventDefault(); card.classList.add('dragover'); });
    card.addEventListener('dragleave', e => { e.preventDefault(); card.classList.remove('dragover'); });
    card.addEventListener('drop', e => {
        e.preventDefault();
        card.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            updateLabel(e.dataTransfer.files[0]);
        }
    });
}

setupFileZone('license-drop',   'license_file');
setupFileZone('insurance-drop', 'insurance_file');

// ── Form submission → show overlay + step animation ───────────
(function initForm() {
    const form    = document.getElementById('upload-form');
    const overlay = document.getElementById('processing-overlay');
    if (!form) return;

    form.addEventListener('submit', e => {
        const licInput = document.getElementById('license_file');
        const insInput = document.getElementById('insurance_file');
        let ok = true;

        [['license_file','license-drop'], ['insurance_file','insurance-drop']].forEach(([id, cardId]) => {
            const inp = document.getElementById(id);
            if (inp && !inp.files.length) {
                ok = false;
                const card = document.getElementById(cardId);
                if (card) {
                    card.classList.add('input-error');
                    setTimeout(() => card.classList.remove('input-error'), 1200);
                }
            }
        });

        if (!ok) { e.preventDefault(); return; }

        if (overlay) {
            overlay.classList.remove('hidden');
            // animate processing steps
            const steps = ['step-upload','step-ocr','step-extract','step-validate'];
            let idx = 0;
            const interval = setInterval(() => {
                if (idx < steps.length) {
                    document.querySelectorAll('.proc-step').forEach(s => s.classList.remove('active'));
                    const el = document.getElementById(steps[idx]);
                    if (el) el.classList.add('active');
                    idx++;
                } else {
                    clearInterval(interval);
                }
            }, 600);
        }

        const btn = form.querySelector('.submit-btn-3d');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing…</span>';
            btn.disabled = true;
        }
    });
})();