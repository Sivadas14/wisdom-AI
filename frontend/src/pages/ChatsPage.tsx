import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Plus, MessageSquare, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { chatAPI } from "@/apis/api";
import { Conversation } from "@/apis/wire";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/use-toast";

const ChatsPage = () => {
    const navigate = useNavigate();
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");
    const [displayLimit, setDisplayLimit] = useState(10);

    // Rename state
    const [renamingChat, setRenamingChat] = useState<Conversation | null>(null);
    const [newTitle, setNewTitle] = useState("");
    const [isRenameOpen, setIsRenameOpen] = useState(false);

    // Delete state
    const [chatToDelete, setChatToDelete] = useState<Conversation | null>(null);
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);

    useEffect(() => {
        loadConversations();
    }, []);

    const loadConversations = async () => {
        try {
            setLoading(true);
            const response = await chatAPI.getConversations();
            setConversations(response.conversations);
        } catch (error) {
            console.error("Failed to fetch conversations:", error);
        } finally {
            setLoading(false);
        }
    };

    const getLastMessageTime = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

        if (diffInSeconds < 60) return "just now";
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;

        const diffInDays = Math.floor(diffInSeconds / 86400);
        if (diffInDays === 1) return "1 day ago";
        if (diffInDays < 30) return `${diffInDays} days ago`;
        if (diffInDays < 365) return `${Math.floor(diffInDays / 30)} months ago`;
        return `${Math.floor(diffInDays / 365)} years ago`;
    };

    const handleRenameClick = (e: React.MouseEvent, chat: Conversation) => {
        e.stopPropagation(); // Prevent navigation
        setRenamingChat(chat);
        setNewTitle(chat.title || "");
        setIsRenameOpen(true);
    };

    const handleSaveRename = async () => {
        if (!renamingChat || !newTitle.trim()) return;

        try {
            await chatAPI.updateConversationTitle(renamingChat.id, newTitle);

            // Update local state
            setConversations(conversations.map(c =>
                c.id === renamingChat.id ? { ...c, title: newTitle } : c
            ));

            setIsRenameOpen(false);
            toast({
                title: "Chat renamed",
                description: "The conversation title has been updated.",
            });
        } catch (error) {
            console.error("Failed to rename chat:", error);
            toast({
                title: "Error",
                description: "Failed to rename chat. Please try again.",
                variant: "destructive",
            });
        }
    };

    const handleDeleteClick = (e: React.MouseEvent, chat: Conversation) => {
        e.stopPropagation();
        setChatToDelete(chat);
        setIsDeleteOpen(true);
    };

    const handleConfirmDelete = async () => {
        if (!chatToDelete) return;

        try {
            await chatAPI.deleteConversation(chatToDelete.id);

            // Update local state by removing the deleted chat
            setConversations(conversations.filter(c => c.id !== chatToDelete.id));

            toast({
                title: "Chat deleted",
                description: "The conversation has been permanently deleted.",
            });
        } catch (error) {
            console.error("Failed to delete chat:", error);
            toast({
                title: "Error",
                description: "Failed to delete chat. Please try again.",
                variant: "destructive",
            });
        } finally {
            setIsDeleteOpen(false);
            setChatToDelete(null);
        }
    };

    const filteredConversations = conversations.filter(chat =>
        (chat.title || "Untitled Conversation").toLowerCase().includes(searchQuery.toLowerCase())
    );

    const displayedConversations = filteredConversations.slice(0, displayLimit);
    const hasMore = filteredConversations.length > displayLimit;

    const handleLoadMore = () => {
        setDisplayLimit(prev => prev + 10);
    };

    const handleNewChat = () => {
        navigate("/home");
    };

    return (
        <div className="flex flex-col h-full bg-[#F5F0EC]">
            <div className="max-w-4xl mx-auto w-full px-6 py-8">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <h1 className="text-3xl  text-[#1F1F1F]">Chats</h1>
                    <Button
                        onClick={handleNewChat}
                        className="bg-[#472B20] hover:bg-[#472B20] text-white rounded-md px-4 py-2 flex items-center gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        New chat
                    </Button>
                </div>

                {/* Search */}
                <div className="relative mb-6">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <Input
                        placeholder="Search your chats..."
                        className="pl-10 h-12 text-base bg-white border-transparent shadow-sm rounded-lg focus-visible:ring-1 focus-visible:ring-gray-300"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                {/* Stats */}
                {/* <div className="flex items-center gap-2 text-sm text-gray-500 mb-4 border-b border-gray-200/50 pb-4">
                    <span>{conversations.length} chats with ArunachalaSamudra</span>
                    <button className="text-blue-600 hover:underline">Select</button>
                </div> */}

                {/* Chat List */}
                <div className="space-y-1">
                    {loading ? (
                        <div className="text-center py-10 text-gray-500">Loading chats...</div>
                    ) : filteredConversations.length === 0 ? (
                        <div className="text-center py-10 text-gray-500">No chats found.</div>
                    ) : (
                        <>
                            {displayedConversations.map((chat) => (
                                <div
                                    key={chat.id}
                                    onClick={() => navigate(`/chat/${chat.id}`)}
                                    className="group relative py-4 px-4 -mx-4 rounded-lg hover:bg-[#ECE5DF] cursor-pointer flex flex-col gap-1 border-b border-gray-200/40 last:border-0 transition-colors"
                                >
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-medium text-[#472B20] truncate pr-8">
                                            {chat.title || "Untitled Conversation"}
                                        </h3>

                                        {/* Rename Button - Visible on hover or focused */}
                                        <div>

                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="opacity-0 group-hover:opacity-100 h-6 w-6 absolute right-4 top-4 transition-opacity"
                                                onClick={(e) => handleRenameClick(e, chat)}
                                                title="Rename chat"
                                            >
                                                <Pencil className="h-3.5 w-3.5 text-gray-500" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="opacity-0 group-hover:opacity-100 h-6 w-6 absolute right-12 top-4 transition-opacity hover:bg-red-100 hover:text-red-600"
                                                onClick={(e) => handleDeleteClick(e, chat)}
                                                title="Delete chat"
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                            </Button>
                                        </div>

                                    </div>
                                    <span className="text-sm text-gray-500">
                                        Last message {getLastMessageTime(chat.created_at)}
                                    </span>
                                </div>
                            ))}

                            {/* Show More Button */}
                            {hasMore && (
                                <div className="pt-4 flex justify-center">
                                    <Button
                                        variant="outline"
                                        onClick={handleLoadMore}
                                        className="text-gray-600 border-gray-200 hover:bg-white bg-transparent"
                                    >
                                        Show more
                                    </Button>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* Rename Dialog */}
            <Dialog open={isRenameOpen} onOpenChange={setIsRenameOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Rename chat</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <Input
                            id="name"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            className="col-span-3"
                            autoFocus
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsRenameOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSaveRename} className="bg-black text-white hover:bg-gray-800">
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Delete Chat?</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete this chat? This action cannot be undone.
                            All messages, audio, and video content associated with this conversation will be permanently removed from our database.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsDeleteOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleConfirmDelete}
                            className="bg-red-600 hover:bg-red-700 text-white"
                        >
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div >
    );
};

export default ChatsPage;
