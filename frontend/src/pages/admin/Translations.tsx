/**
 * Admin Translations page — review + override automated translations.
 *
 * Talks DIRECTLY to Supabase via the existing client (no FastAPI admin endpoint
 * needed). RLS policies on `page_translations` table gate access — users
 * without app_metadata.role='admin' get an empty result set automatically.
 *
 * Mount under your existing /admin route layout. Wrap with <AdminRoute /> for
 * frontend-side auth check.
 */
import { useEffect, useState, useMemo } from "react";
import { supabase } from "@/lib/supabase";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { SUPPORTED_LANGUAGES } from "@/i18n";

interface PageTranslationRow {
  id: string;
  domain: string;
  resource_type: string;
  resource_id: string;
  language_code: string;
  source_text: string;
  translated_title: string | null;
  translated_body: string;
  provider: string;
  quality_score: number | null;
  manual_override: boolean;
  is_approved: boolean;
  last_updated: string;
  char_count: number;
}

export default function AdminTranslations() {
  const [rows, setRows] = useState<PageTranslationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterLang, setFilterLang] = useState<string>("hi");
  const [filterStatus, setFilterStatus] = useState<"all" | "manual" | "auto" | "low_quality">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [editing, setEditing] = useState<PageTranslationRow | null>(null);
  const [editedBody, setEditedBody] = useState("");
  const [editedTitle, setEditedTitle] = useState("");
  const { toast } = useToast();

  async function loadRows() {
    setLoading(true);
    let query = supabase
      .from("page_translations")
      .select("*")
      .eq("language_code", filterLang)
      .order("last_updated", { ascending: false })
      .limit(100);

    if (filterStatus === "manual") query = query.eq("manual_override", true);
    if (filterStatus === "auto") query = query.eq("manual_override", false);
    if (filterStatus === "low_quality") query = query.lt("quality_score", 0.85);

    const { data, error } = await query;
    if (error) {
      toast({ title: "Error loading", description: error.message, variant: "destructive" });
      setLoading(false);
      return;
    }
    setRows(data as PageTranslationRow[]);
    setLoading(false);
  }

  useEffect(() => {
    loadRows();
  }, [filterLang, filterStatus]);

  const filteredRows = useMemo(() => {
    if (!searchQuery.trim()) return rows;
    const q = searchQuery.toLowerCase();
    return rows.filter(
      (r) =>
        r.resource_id.toLowerCase().includes(q) ||
        r.source_text.toLowerCase().includes(q) ||
        r.translated_body.toLowerCase().includes(q),
    );
  }, [rows, searchQuery]);

  function startEdit(row: PageTranslationRow) {
    setEditing(row);
    setEditedTitle(row.translated_title || "");
    setEditedBody(row.translated_body);
  }

  async function saveEdit() {
    if (!editing) return;
    const { error } = await supabase
      .from("page_translations")
      .update({
        translated_title: editedTitle || null,
        translated_body: editedBody,
        manual_override: true,
        provider: "manual",
        quality_score: 1.0,
        last_updated: new Date().toISOString(),
      })
      .eq("id", editing.id);

    if (error) {
      toast({ title: "Save failed", description: error.message, variant: "destructive" });
      return;
    }
    toast({ title: "Translation saved", description: "Marked as manual override." });
    setEditing(null);
    await loadRows();
  }

  async function retranslate(row: PageTranslationRow, provider: "sarvam" | "azure" | "google") {
    // Re-translate via the backend gateway (clears the cache row first).
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL;
      // Force a re-translation by calling the gateway with the source text
      const r = await fetch(`${apiBase}/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: row.source_text,
          target_lang: row.language_code,
          resource_type: row.resource_type,
          resource_id: row.resource_id,
        }),
      });
      const json = await r.json();
      if (!json.success) throw new Error(json.message);
      toast({ title: "Re-translated", description: `Provider: ${json.data.provider}` });
      await loadRows();
    } catch (e: any) {
      toast({ title: "Re-translate failed", description: String(e.message || e), variant: "destructive" });
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">Translation Manager</h1>
      <p className="text-sm text-gray-500 mb-6">
        Review and override automated translations. Manual edits are protected
        from being overwritten by future automated runs.
      </p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs mb-1">Language</label>
            <Select value={filterLang} onValueChange={setFilterLang}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                {SUPPORTED_LANGUAGES.filter((l) => l.code !== "en").map((l) => (
                  <SelectItem key={l.code} value={l.code}>
                    {l.native} ({l.english})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="block text-xs mb-1">Status</label>
            <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as any)}>
              <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="auto">Automated only</SelectItem>
                <SelectItem value="manual">Manual override</SelectItem>
                <SelectItem value="low_quality">Low quality (&lt;0.85)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-64">
            <label className="block text-xs mb-1">Search</label>
            <Input
              placeholder="Search slug or text…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button variant="outline" onClick={loadRows} disabled={loading}>
            {loading ? "Loading…" : "Reload"}
          </Button>
        </CardContent>
      </Card>

      {!editing && (
        <Card>
          <CardHeader>
            <CardTitle>{filteredRows.length} translations</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 border-b">
                <tr>
                  <th className="text-left pb-2">Resource</th>
                  <th className="text-left pb-2">Provider</th>
                  <th className="text-left pb-2">Quality</th>
                  <th className="text-left pb-2">Override</th>
                  <th className="text-left pb-2">Updated</th>
                  <th className="text-right pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-900">
                    <td className="py-2 font-mono text-xs">{row.resource_id}</td>
                    <td className="py-2"><Badge variant="outline">{row.provider}</Badge></td>
                    <td className="py-2">{row.quality_score?.toFixed(2) ?? "—"}</td>
                    <td className="py-2">
                      {row.manual_override ? (
                        <Badge>Manual</Badge>
                      ) : (
                        <Badge variant="secondary">Auto</Badge>
                      )}
                    </td>
                    <td className="py-2 text-xs">{new Date(row.last_updated).toLocaleString()}</td>
                    <td className="py-2 text-right">
                      <Button size="sm" variant="ghost" onClick={() => startEdit(row)}>Edit</Button>
                      <Button size="sm" variant="ghost" onClick={() => retranslate(row, "sarvam")}>Re-run</Button>
                    </td>
                  </tr>
                ))}
                {filteredRows.length === 0 && !loading && (
                  <tr><td colSpan={6} className="py-6 text-center text-gray-500">No translations match your filters.</td></tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {editing && (
        <Card>
          <CardHeader>
            <CardTitle>Edit translation: {editing.resource_id}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-semibold mb-2 text-gray-500">Source (English)</h3>
                <pre className="bg-gray-50 dark:bg-gray-900 p-3 rounded text-sm whitespace-pre-wrap">
                  {editing.source_text}
                </pre>
              </div>
              <div>
                <h3 className="text-sm font-semibold mb-2 text-gray-500">
                  {SUPPORTED_LANGUAGES.find((l) => l.code === editing.language_code)?.native} (editable)
                </h3>
                <Input
                  placeholder="Translated title (optional)"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="mb-2"
                />
                <Textarea
                  rows={10}
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  className={editing.language_code === "ar" ? "text-right" : ""}
                  dir={editing.language_code === "ar" ? "rtl" : "ltr"}
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
              <Button onClick={saveEdit}>Save & Approve</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
