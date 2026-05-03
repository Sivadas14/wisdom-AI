import { ReactNode, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import UserMenu from "@/components/UserMenu";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";

interface MainLayoutProps {
    children: ReactNode;
}

const MainLayout = ({ children }: MainLayoutProps) => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    useEffect(() => {
        console.log('🏗️ [MainLayout] Mounted');
        return () => console.log('🏗️ [MainLayout] Unmounted');
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
                    {/* Right: LanguageSwitcher always; UserMenu mobile-only (sidebar already has it on desktop) */}
                    <div className="flex items-center gap-2">
                        <LanguageSwitcher variant="full" />
                        <div className="md:hidden"><UserMenu /></div>
                    </div>
                </header>
                {/* Main Content Area */}
                <main className="flex-1 h-full overflow-y-auto relative scroll-smooth">
                    {children}
                </main>
            </div>
        </div>
    );
};

export default MainLayout;
