// ============================================================
// Language selection that actually works
// ============================================================
//
// GTranslate's float.js renders the language dropdown, but on this site its
// own option-click handlers never fire — verified live by dispatching click,
// mousedown, pointerdown and touchstart at a language anchor and watching
// nothing happen, then proving the underlying pipeline is healthy: setting
// the `googtrans` cookie by hand and reloading translated the whole page.
//
// So the click is ours now. One delegated listener on the document (it
// survives React re-renders and widget re-paints, unlike per-anchor
// bindings) catches selections in the dropdown, writes the cookie the way
// GTranslate itself expects, and reloads. Choosing English clears the
// cookie — that is GTranslate's own convention for "show original".

const HANDLER_FLAG = "__asamGtClickHandler";

function setLangCookie(lang: string) {
    const host = location.hostname;
    // Both host and parent-domain scope, so www and bare domain agree.
    const parent = host.replace(/^www\./, "");
    if (lang === "en") {
        for (const domain of ["", `; domain=.${parent}`]) {
            document.cookie = `googtrans=; path=/${domain}; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
        }
    } else {
        for (const domain of ["", `; domain=.${parent}`]) {
            document.cookie = `googtrans=/en/${lang}; path=/${domain}`;
        }
    }
}

export function installGtClickHandler(): () => void {
    const w = window as any;
    if (w[HANDLER_FLAG]) return () => {};

    const onClick = (e: MouseEvent) => {
        const anchor = (e.target as Element | null)?.closest?.(
            ".gt_options a.nturl"
        ) as HTMLElement | null;
        if (!anchor) return;
        const lang = anchor.dataset.gtLang;
        if (!lang) return;
        e.preventDefault();
        setLangCookie(lang);
        location.reload();
    };

    document.addEventListener("click", onClick, true);
    w[HANDLER_FLAG] = true;
    return () => {
        document.removeEventListener("click", onClick, true);
        delete w[HANDLER_FLAG];
    };
}
