/**
 * Admin → Translations: translate → review → approve → cache, page by page.
 * Only APPROVED translations are served on the public site.
 */
import { useEffect, useState } from "react";
import { apiClient } from "@/apis";

type LangRow = { code: string; name: string; status: "none" | "draft" | "approved" };
type PageRow = { slug: string; title: string };

export default function TranslationsManager() {
    const [pages, setPages] = useState<PageRow[]>([]);
    const [slug, setSlug] = useState<string>("");
    const [source, setSource] = useState<{ title: string; subtitle?: string; body: string } | null>(null);
    const [langs, setLangs] = useState<LangRow[]>([]);
    const [lang, setLang] = useState<string>("");
    const [draft, setDraft] = useState<{ title: string; subtitle: string; body: string; status: string }>(
        { title: "", subtitle: "", body: "", status: "none" });
    const [busy, setBusy] = useState<string>("");

    useEffect(() => {
        apiClient.get("/admin/pages").then(r => setPages(r.data || [])).catch(() => {});
    }, []);

    const loadPage = async (s: string) => {
        setSlug(s); setLang(""); setSource(null); setLangs([]);
        if (!s) return;
        const r = await apiClient.get(`/admin/translations?slug=${encodeURIComponent(s)}`);
        setSource(r.data.source); setLangs(r.data.languages || []);
    };

    const loadLang = async (l: string) => {
        setLang(l);
        const r = await apiClient.get(`/admin/translations/one?slug=${encodeURIComponent(slug)}&lang=${l}`);
        setDraft({ title: r.data.title || "", subtitle: r.data.subtitle || "", body: r.data.body || "", status: r.data.status });
    };

    const refreshStatus = async () => {
        const r = await apiClient.get(`/admin/translations?slug=${encodeURIComponent(slug)}`);
        setLangs(r.data.languages || []);
    };

    const autoTranslate = async () => {
        setBusy("Translating… (this can take a few seconds)");
        try {
            const r = await apiClient.post("/admin/translations/draft", { slug, lang });
            setDraft({ title: r.data.title || "", subtitle: r.data.subtitle || "", body: r.data.body || "", status: "draft" });
            await refreshStatus();
        } finally { setBusy(""); }
    };
    const save = async () => {
        setBusy("Saving…");
        try {
            await apiClient.put("/admin/translations", { slug, lang, title: draft.title, subtitle: draft.subtitle, body: draft.body });
            setDraft(d => ({ ...d, status: "draft" })); await refreshStatus();
        } finally { setBusy(""); }
    };
    const approve = async () => {
        setBusy("Approving…");
        try {
            await apiClient.put("/admin/translations", { slug, lang, title: draft.title, subtitle: draft.subtitle, body: draft.body });
            await apiClient.post("/admin/translations/approve", { slug, lang });
            setDraft(d => ({ ...d, status: "approved" })); await refreshStatus();
            alert("Approved — now live on the site for this language.");
        } finally { setBusy(""); }
    };
    const unapprove = async () => { await apiClient.post("/admin/translations/unapprove", { slug, lang }); setDraft(d => ({ ...d, status: "draft" })); await refreshStatus(); };

    const badge = (st: string) => st === "approved" ? "✅" : st === "draft" ? "✎ draft" : "—";

    return (
        <div style={{ padding: 24, fontFamily: "system-ui", maxWidth: 1200 }}>
            <h2 style={{ fontSize: "1.4rem", fontWeight: 700, color: "#9c3b12" }}>Translations</h2>
            <p style={{ color: "#666", fontSize: ".9rem" }}>Translate a page, review it for authenticity, then Approve. Only approved translations appear on the live site.</p>

            <label>Page:&nbsp;
                <select value={slug} onChange={e => loadPage(e.target.value)} style={{ minWidth: 360, padding: 6 }}>
                    <option value="">— choose a page —</option>
                    {pages.map(p => <option key={p.slug} value={p.slug}>{p.title} ({p.slug})</option>)}
                </select>
            </label>

            {langs.length > 0 && (
                <div style={{ margin: "14px 0", display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {langs.map(l => (
                        <button key={l.code} onClick={() => loadLang(l.code)}
                            style={{ padding: "6px 10px", borderRadius: 6, cursor: "pointer",
                                border: lang === l.code ? "2px solid #9c3b12" : "1px solid #ccc",
                                background: l.status === "approved" ? "#e8f5e9" : l.status === "draft" ? "#fff8e1" : "#fff" }}>
                            {l.name} <span style={{ fontSize: ".8rem", color: "#888" }}>{badge(l.status)}</span>
                        </button>
                    ))}
                </div>
            )}

            {lang && source && (
                <div>
                    <div style={{ margin: "10px 0", display: "flex", gap: 10, alignItems: "center" }}>
                        <button onClick={autoTranslate} disabled={!!busy}>✨ Auto-translate</button>
                        <button onClick={save} disabled={!!busy}>Save draft</button>
                        <button onClick={approve} disabled={!!busy} style={{ background: "#2e7d32", color: "#fff", padding: "6px 14px", border: "none", borderRadius: 6 }}>Approve &amp; publish</button>
                        {draft.status === "approved" && <button onClick={unapprove}>Unpublish</button>}
                        <span style={{ color: "#9c3b12" }}>{busy}</span>
                        <span style={{ marginLeft: "auto" }}>Status: <strong>{draft.status}</strong></span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                        <div>
                            <h4>English (source)</h4>
                            <input readOnly value={source.title} style={{ width: "100%", marginBottom: 6 }} />
                            <input readOnly value={source.subtitle || ""} style={{ width: "100%", marginBottom: 6 }} />
                            <textarea readOnly value={source.body} rows={22} style={{ width: "100%", fontFamily: "monospace", fontSize: ".8rem" }} />
                        </div>
                        <div>
                            <h4>{langs.find(l => l.code === lang)?.name} (edit for authenticity)</h4>
                            <input value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} placeholder="Title" style={{ width: "100%", marginBottom: 6 }} />
                            <input value={draft.subtitle} onChange={e => setDraft({ ...draft, subtitle: e.target.value })} placeholder="Subtitle" style={{ width: "100%", marginBottom: 6 }} />
                            <textarea value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })} rows={22} style={{ width: "100%", fontFamily: "monospace", fontSize: ".8rem" }} />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
