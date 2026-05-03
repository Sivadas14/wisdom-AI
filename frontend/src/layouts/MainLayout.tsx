import { ReactNode, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import UserMenu from "@/components/UserMenu";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import i18n, { SUPPORTED_LNG_CODES, RTL_LANGS } from "@/i18n";
import { supabase } from "@/lib/supabase";

interface MainLayoutProps {
    children: ReactNode;
}

const MainLayout = ({ children }: MainLayoutProps) => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    useEffect(() => {
        console.log('🏗️ [MainLayout] Mounted');
        return () => console.log('🏗️ [MainLayout] Unmounted');
    }, []);

    // ── Post-login GTranslate widget ─────────────────────────────────────────
    // Almost no post-login component currently uses react-i18next. Hardcoded
    // English strings dominate (Sidebar, Chat, Library, etc.). To translate
    // the visible UI without rewriting every page, mount the same GTranslate
    // widget we use on Landing — it walks the DOM at runtime and translates
    // text in-place, regardless of whether components use t() calls.
    //
    // Cleanup runs on unmount (e.g. user signs out and SPA hits a route
    // without MainLayout). The googtrans cookie persists across logout.
    useEffect(() => {
        if (document.querySelector('script[data-scope="app-gtranslate"]')) return;

        (window as any).gtranslateSettings = {
            default_language: "en",
            languages: ["en","hi","ta","te","bn","ml","es","fr","de","nl","sv","da","no","fi","ar","zh-CN"],
            wrapper_selector: ".gtranslate_wrapper",
            switcher_horizontal_position: "right",
            switcher_vertical_position: "top",
            float_switcher_open_direction: "bottom",
            flag_size: 24,
            flag_style: "3d",
        };
        const script = document.createElement("script");
        script.src = "https://cdn.gtranslate.net/widgets/latest/float.js";
        script.defer = true;
        script.dataset.scope = "app-gtranslate";
        document.body.appendChild(script);

        return () => {
            script.remove();
            document.querySelectorAll(".gt_float_switcher, .gtranslate_wrapper, .gt-current-lang, .gt_widget_wrapper")
                .forEach(el => el.remove());
            try { delete (window as any).gtranslateSettings; } catch { /* ignore */ }
        };
    }, []);

    // ── Cross-route language sync ────────────────────────────────────────────
    // When the user picks a language via GTranslate (post-login), mirror that
    // choice to: (1) pref_lang cookie, (2) preferredLang localStorage,
    // (3) live i18n state, (4) Supabase language_preferences table — so the
    // auth'd chat handler's detect_user_lang() picks it up and the chat
    // actually responds in the user's language.
    useEffect(() => {
        let lastSyncedCode: string | null = null;

        const sync = async () => {
            const m = document.cookie.match(/googtrans=\/[^/]+\/([a-zA-Z-]+)/);
            if (!m || !m[1]) return;

            const raw = m[1].toLowerCase();
            const code: string =
                raw === "zh-cn" ? "zh-CN" :
                raw === "zh-tw" ? "zh-TW" :
                raw;

            if (!(SUPPORTED_LNG_CODES as readonly string[]).includes(code)) return;

            const cur = document.cookie.match(/pref_lang=([^;]+)/);
            if (cur && cur[1] === code && lastSyncedCode === code) return;

            // Cookie + localStorage + live i18n
            document.cookie = `pref_lang=${code}; max-age=${60 * 60 * 24 * 365}; path=/; SameSite=Lax; Secure`;
            try { localStorage.setItem("preferredLang", code); } catch { /* ignore */ }
            try {
                i18n.changeLanguage(code);
                document.documentElement.lang = code;
                document.documentElement.dir = (RTL_LANGS as Set<string>).has(code) ? "rtl" : "ltr";
            } catch { /* ignore */ }

            // Supabase language_preferences (so chat handler detect_user_lang sees it)
            if (lastSyncedCode !== code) {
                try {
                    const { data } = await supabase.auth.getUser();
                    if (data?.user) {
                        await supabase.from("language_preferences").upsert({
                            user_id: data.user.id,
                            preferred_language: code,
                            last_updated: new Date().toISOString(),
                        });
                    }
                } catch { /* silent — chat will fall back to pref_lang cookie or 'en' */ }
            }

            lastSyncedCode = code;
        };

        sync();
        const id = window.setInterval(sync, 1000);
        return () => window.clearInterval(id);
    }, []);

    return (
        <div className="flex h-full w-full overflow-hidden bg-[#F5F0EC]">
            {/* Desktop Sidebar */}
            <div className="flex-shrink-0 hidden md:flex">
                <Sidebar />
            </div>

            <div className="flex-1 flex flex-col h-full overflow-hidden relative bg-[#F5F0EC]">
                {/* Top Header — always visible. Mobile shows menu+title+UserMenu;
                    desktop shows only the LanguageSwitcher pinned to the right
                    (UserMenu stays in the sidebar on desktop so it isn't duplicated). */}
                <header className="flex items-center justify-between px-4 h-14 border-b border-[#ECE5DF] bg-[#F5F0EC]/80 backdrop-blur-sm sticky top-0 z-50">
                    {/* Left: mobile-only menu button + app title */}
                    <div className="flex items-center gap-2 md:invisible">
                        <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
                            <SheetTrigger asChild>
                                <Button variant="ghost" size="icon" className="text-[#472B20] md:hidden">
                                    <Menu className="h-5 w-5" />
                                </Button>
                            </SheetTrigger>
                            <SheetContent side="left" className="p-0 w-[260px] border-r border-[#ECE5DF]">
                                <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
                                <div className="h-full" onClick={() => setIsMobileMenuOpen(false)}>
                                    <Sidebar />
                                </div>
                            </SheetContent>
                        </Sheet>
                        <span className="font-heading text-[#472B20] font-bold md:hidden">Wisdom AI</span>
                    </div>
                    {/* Right: UserMenu mobile-only (sidebar already has it on desktop).
                        Language switching is now handled by the GTranslate floating widget
                        (mounted by useEffect above), which actually translates the DOM
                        for hardcoded English text — unlike the previous LanguageSwitcher
                        which only updated react-i18next state that no component reads. */}
                    <div className="flex items-center gap-2">
                        <div className="md:hidden"><UserMenu /></div>
                    </div>
                </header>
                {/* GTranslate floating-widget wrapper — populated by the script in useEffect */}
                <div className="gtranslate_wrapper" />
                {/* Main Content Area */}
                <main className="flex-1 h-full overflow-y-auto relative scroll-smooth">
                    {children}
                </main>
            </div>
        </div>
    );
};

export default MainLayout;
