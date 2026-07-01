/* landing.js — behaviour for landing.html only */

(function () {

    /* ── Theme toggle ───────────────────────────────────────── */
    const html = document.documentElement;
    const themeBtn = document.getElementById('ld-theme-toggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            html.setAttribute(
                'data-theme',
                html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'
            );
        });
    }

    /* ── Nav scroll shadow ──────────────────────────────────── */
    const nav = document.getElementById('ld-nav');
    if (nav) {
        const onScroll = () => {
            nav.classList.toggle('scrolled', window.scrollY > 32);
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }

    /* ── Footer year ────────────────────────────────────────── */
    const yearEl = document.getElementById('ld-year');
    if (yearEl) yearEl.textContent = new Date().getFullYear();

    /* ── Typewriter demo ─────────────────────────────────────
       Simulates the assistant typing a realistic reply inside
       the hero mockup.
       -------------------------------------------------------- */
    const typeTarget = document.getElementById('ld-type-target');
    const sourcesBar = document.getElementById('ld-mockup-sources');
    const agentPill  = document.getElementById('ld-agent-pill');

    const replies = [
        'Key change: Q2 added a net-payment-60 clause on all orders above $10 k — absent in Q1. Three vendors also dropped the liability cap from $50 k to $25 k.',
        'Auto Route selected RAG Document Analysis after detecting a document-comparison intent in your query.',
        'Both Q1 and Q2 contracts share the same force-majeure language, so no change there.',
    ];

    const agentLabels = ['Auto Route', 'RAG Analysis', 'Summary'];

    let replyIndex = 0;
    let charIndex  = 0;
    let timer      = null;

    function typeChar() {
        if (!typeTarget) return;
        const reply = replies[replyIndex];
        if (charIndex < reply.length) {
            typeTarget.textContent += reply[charIndex];
            charIndex++;
            timer = setTimeout(typeChar, 28 + Math.random() * 22);
        } else {
            // Show sources after typing finishes
            if (sourcesBar) sourcesBar.classList.add('visible');
            // Pause, clear, then start next reply
            setTimeout(() => {
                typeTarget.textContent = '';
                charIndex = 0;
                if (sourcesBar) sourcesBar.classList.remove('visible');
                replyIndex = (replyIndex + 1) % replies.length;
                if (agentPill) agentPill.textContent = agentLabels[replyIndex % agentLabels.length];
                timer = setTimeout(typeChar, 600);
            }, 3800);
        }
    }

    if (typeTarget) {
        setTimeout(typeChar, 1200);
    }

    /* ── Scroll-reveal ───────────────────────────────────────
       Any element with class .ld-reveal fades in when it
       enters the viewport.
       -------------------------------------------------------- */
    const revealEls = document.querySelectorAll(
        '.ld-feature-card, .ld-stat, .ld-agent-row, .ld-flow-step, ' +
        '.ld-section-head, .ld-cta-box'
    );

    revealEls.forEach(el => el.classList.add('ld-reveal'));

    if ('IntersectionObserver' in window) {
        const obs = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('in-view');
                        obs.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.12 }
        );
        revealEls.forEach(el => obs.observe(el));
    } else {
        // Fallback: just show everything
        revealEls.forEach(el => el.classList.add('in-view'));
    }

    /* ── Smooth-scroll for anchor links ─────────────────────── */
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener('click', (e) => {
            const target = document.querySelector(a.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

})();
