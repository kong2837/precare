(() => {
    const nav = document.querySelector('.mobile-tabbar');
    if (!nav) return;
    const path = window.location.pathname;
    nav.querySelectorAll('a').forEach(link => {
        const target = new URL(link.href, window.location.origin).pathname;
        const active = target === '/' ? path === '/' : path.startsWith(target);
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });

    const mobile = window.matchMedia('(max-width: 767.98px)');
    const viewport = window.visualViewport;
    const updateKeyboard = () => {
        const editing = document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]), textarea, select');
        const keyboardOpen = mobile.matches && editing && viewport && window.innerHeight - viewport.height > 120;
        document.body.classList.toggle('mobile-keyboard-open', Boolean(keyboardOpen));
    };
    viewport?.addEventListener('resize', updateKeyboard);
    document.addEventListener('focusin', updateKeyboard);
    document.addEventListener('focusout', () => requestAnimationFrame(updateKeyboard));
    mobile.addEventListener('change', updateKeyboard);
})();
