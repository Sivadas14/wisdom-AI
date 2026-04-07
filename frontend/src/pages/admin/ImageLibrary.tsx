import { useState, useEffect, useRef } from "react";
import { Upload, Trash2, Eye, EyeOff, ImageIcon, AlertCircle, CheckCircle2 } from "lucide-react";
import { ramanaImagesAPI, RamanaImageItem } from "@/apis/api";

export default function ImageLibrary() {
    const [images, setImages] = useState<RamanaImageItem[]>([]);
    const [total, setTotal] = useState(0);
    const [activeCount, setActiveCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [description, setDescription] = useState("");
    const [toastMsg, setToastMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
    const [dragging, setDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const showToast = (type: "success" | "error", text: string) => {
        setToastMsg({ type, text });
        setTimeout(() => setToastMsg(null), 3500);
    };

    const loadImages = async () => {
        try {
            const data = await ramanaImagesAPI.list();
            setImages(data.images);
            setTotal(data.total);
            setActiveCount(data.active);
        } catch {
            showToast("error", "Failed to load images");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadImages(); }, []);

    const MAX_BATCH = 10;

    const handleFiles = async (files: File[]) => {
        if (!files.length) return;
        const allowed = files.filter(f => f.type.startsWith("image/"));
        if (!allowed.length) { showToast("error", "Only image files are supported (JPG, PNG, WebP)"); return; }
        if (allowed.length > MAX_BATCH) {
            showToast("error", `Max ${MAX_BATCH} images per upload. Please select fewer files.`);
            return;
        }
        setUploading(true);
        try {
            const result = await ramanaImagesAPI.upload(allowed, description);
            if (result.uploaded.length) showToast("success", `Uploaded ${result.uploaded.length} image(s) successfully`);
            if (result.errors.length) showToast("error", result.errors[0]);
            setDescription("");
            await loadImages();
        } catch (err: any) {
            // FastAPI 422 detail is an array of objects; always coerce to a string
            const raw = err?.response?.data?.detail;
            const msg = typeof raw === "string"
                ? raw
                : Array.isArray(raw)
                    ? (raw[0]?.msg || "Validation error — check file type/size")
                    : "Upload failed — please try again";
            showToast("error", msg);
        } finally {
            setUploading(false);
        }
    };

    const handleToggle = async (id: string) => {
        try {
            const result = await ramanaImagesAPI.toggle(id);
            setImages(prev => prev.map(img => img.id === id ? { ...img, active: result.active } : img));
            setActiveCount(prev => result.active ? prev + 1 : prev - 1);
        } catch {
            showToast("error", "Failed to update image");
        }
    };

    const handleDelete = async (id: string, filename: string) => {
        if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;
        try {
            await ramanaImagesAPI.delete(id);
            const wasActive = images.find(i => i.id === id)?.active;
            setImages(prev => prev.filter(i => i.id !== id));
            setTotal(prev => prev - 1);
            if (wasActive) setActiveCount(prev => prev - 1);
            showToast("success", "Image deleted");
        } catch {
            showToast("error", "Delete failed");
        }
    };

    return (
        <div className="space-y-6">
            {/* Toast */}
            {toastMsg && (
                <div className={`fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium
                    ${toastMsg.type === "success" ? "bg-green-50 text-green-800 border border-green-200" : "bg-red-50 text-red-800 border border-red-200"}`}>
                    {toastMsg.type === "success" ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                    {toastMsg.text}
                </div>
            )}

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Image Library</h1>
                    <p className="text-sm text-gray-500 mt-1">
                        Upload Ramana Maharshi &amp; Tiruvannamalai images used for contemplation cards.
                        Active images replace AI-generated ones.
                    </p>
                </div>
                <div className="flex gap-4 text-sm">
                    <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-center">
                        <div className="text-xl font-bold text-gray-800">{total}</div>
                        <div className="text-gray-500">Total</div>
                    </div>
                    <div className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-2 text-center">
                        <div className="text-xl font-bold text-orange-600">{activeCount}</div>
                        <div className="text-orange-600">Active</div>
                    </div>
                </div>
            </div>

            {/* Upload Zone */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
                <h2 className="font-semibold text-gray-800">Upload Images</h2>

                <div
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
                        ${dragging ? "border-orange-400 bg-orange-50" : "border-gray-300 hover:border-orange-300 hover:bg-gray-50"}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={e => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={e => {
                        e.preventDefault(); setDragging(false);
                        handleFiles(Array.from(e.dataTransfer.files));
                    }}
                >
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600 font-medium">
                        {uploading ? "Uploading…" : "Click or drag & drop images here"}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">JPG, PNG, WebP · Up to 10 images at a time · Max 10 MB each</p>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        multiple
                        className="hidden"
                        onChange={e => handleFiles(Array.from(e.target.files || []))}
                    />
                </div>

                <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">
                        Description (optional, applies to this batch)
                    </label>
                    <input
                        type="text"
                        value={description}
                        onChange={e => setDescription(e.target.value)}
                        placeholder="e.g. Arunachala sunrise, ashram courtyard…"
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                    />
                </div>
            </div>

            {/* Image Grid */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="font-semibold text-gray-800 mb-4">
                    Repository {total > 0 && <span className="text-gray-400 font-normal text-sm">({total} images)</span>}
                </h2>

                {loading ? (
                    <div className="flex justify-center py-12">
                        <div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : images.length === 0 ? (
                    <div className="text-center py-12 text-gray-400">
                        <ImageIcon className="w-10 h-10 mx-auto mb-3 opacity-40" />
                        <p className="text-sm">No images yet. Upload some to get started.</p>
                        <p className="text-xs mt-1">Until images are uploaded, contemplation cards use AI-generated imagery.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                        {images.map(img => (
                            <div
                                key={img.id}
                                className={`group relative rounded-xl overflow-hidden border-2 transition-all
                                    ${img.active ? "border-orange-300" : "border-gray-200 opacity-60"}`}
                            >
                                {/* Thumbnail */}
                                <div className="aspect-video bg-gray-100">
                                    {img.preview_url ? (
                                        <img
                                            src={img.preview_url}
                                            alt={img.filename}
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center">
                                            <ImageIcon className="w-6 h-6 text-gray-300" />
                                        </div>
                                    )}
                                </div>

                                {/* Active badge */}
                                <div className={`absolute top-2 left-2 text-xs font-semibold px-2 py-0.5 rounded-full
                                    ${img.active ? "bg-orange-500 text-white" : "bg-gray-400 text-white"}`}>
                                    {img.active ? "Active" : "Off"}
                                </div>

                                {/* Actions overlay */}
                                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={() => handleToggle(img.id)}
                                        title={img.active ? "Deactivate" : "Activate"}
                                        className="p-1.5 rounded-lg bg-white shadow text-gray-600 hover:text-orange-600 transition-colors"
                                    >
                                        {img.active ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                    </button>
                                    <button
                                        onClick={() => handleDelete(img.id, img.filename)}
                                        title="Delete"
                                        className="p-1.5 rounded-lg bg-white shadow text-gray-600 hover:text-red-600 transition-colors"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>

                                {/* Filename */}
                                <div className="p-2">
                                    <p className="text-xs text-gray-600 truncate" title={img.filename}>{img.filename}</p>
                                    {img.description && (
                                        <p className="text-xs text-gray-400 truncate mt-0.5" title={img.description}>{img.description}</p>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
